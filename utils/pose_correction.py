"""A-pose conversion: transform T-pose VRM mesh to match male_07 A-pose directions.

VRM/VRC models use T-pose (arms horizontal).  HL2/GMod's male_07 skeleton
uses an A-pose (arms angled downward ~30-45°).  This directional mismatch
causes arm-spreading artifacts when HL2 animations play.

This module solves the problem by posing the Blender armature to match the
projected skeleton's (male_07) bone directions, then baking the deformation
into the mesh vertices and updating the rest pose.  Blender's native LBS
skinning handles joint deformation correctly (no "paper-thin" artifacts).

After A-pose conversion:
  - Mesh vertices are in A-pose positions
  - Bone rest positions are in A-pose
  - The projected skeleton (male_07 dir × VRM length) ≈ actual bone positions
  - Proportion Trick delta ≈ length differences only (clean)
  - Vertex correction offsets ≈ 0
"""

import math
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from ..data.bone_mapping import (
    VALVEBIPED_HIERARCHY,
    VALVEBIPED_BONE_ORDER,
    QC_ONLY_BONES,
    MALE07_REFERENCE_POSITIONS,
    MALE07_SMD_ROTATIONS,
)


def apply_a_pose(armature, mesh_obj):
    """Transform mesh and skeleton from T-pose to A-pose (male_07 directions).

    This is the main entry point.  It:
      1. Computes projected (male_07) world positions for direction targets
      2. Poses each bone so its direction matches the projected skeleton
      3. Bakes the deformed mesh vertex positions
      4. Updates the rest pose to match the A-pose
      5. Re-attaches the armature modifier

    Parameters
    ----------
    armature : bpy.types.Object
        Armature object (must have ValveBiped-named bones from bone_remap).
    mesh_obj : bpy.types.Object
        Mesh object (child of armature, with armature modifier).
    """
    # Ensure we start in object mode with armature selected
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # --- Step 1: Compute projected world positions (male_07 directions) ---
    projected_world, world_rotations = _compute_projected_world(armature)

    # --- Step 2: Build children map ---
    children_of = _build_children_map(armature)

    # --- Step 3: Enter pose mode and apply rotations ---
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')

    # Only correct arm bones (T-pose → A-pose).
    # Spine/neck/head/legs keep their VRM directions — correcting them
    # causes the model to hunch forward because VRM and male_07 have
    # slightly different torso angles.
    apose_correct_bones = {
        "ValveBiped.Bip01_L_Clavicle",
        "ValveBiped.Bip01_L_UpperArm",
        "ValveBiped.Bip01_L_Forearm",
        "ValveBiped.Bip01_L_Hand",
        "ValveBiped.Bip01_R_Clavicle",
        "ValveBiped.Bip01_R_UpperArm",
        "ValveBiped.Bip01_R_Forearm",
        "ValveBiped.Bip01_R_Hand",
    }

    # Process bones in VALVEBIPED_BONE_ORDER (parent-first guaranteed)
    for bone_name in VALVEBIPED_BONE_ORDER:
        bone = armature.data.bones.get(bone_name)
        if bone is None:
            continue
        if bone_name in QC_ONLY_BONES:
            continue
        if bone_name not in apose_correct_bones:
            continue

        pose_bone = armature.pose.bones.get(bone_name)
        if pose_bone is None:
            continue

        # Find primary child for direction computation
        child_name = _find_primary_child(bone_name, children_of, armature)
        if child_name is None:
            continue

        if bone_name not in projected_world or child_name not in projected_world:
            continue

        child_pose_bone = armature.pose.bones.get(child_name)
        if child_pose_bone is None:
            continue

        # Current direction (after parent poses have been applied)
        current_dir = (child_pose_bone.head - pose_bone.head)
        if current_dir.length < 0.001:
            continue
        current_dir = current_dir.normalized()

        # Target direction from projected skeleton
        target_dir = (projected_world[child_name] - projected_world[bone_name])
        if target_dir.length < 0.001:
            continue
        target_dir = target_dir.normalized()

        # Skip if directions already match (dot > 0.9999 ≈ < 0.8°)
        dot = current_dir.dot(target_dir)
        if dot > 0.9999:
            continue

        # Compute world-space rotation from current to target direction
        rot_quat = current_dir.rotation_difference(target_dir)

        # Apply rotation around the bone's head (pivot point)
        mat = pose_bone.matrix.copy()
        head = pose_bone.head.copy()
        rot_mat = rot_quat.to_matrix().to_4x4()
        new_mat = (
            Matrix.Translation(head)
            @ rot_mat
            @ Matrix.Translation(-head)
            @ mat
        )
        pose_bone.matrix = new_mat

        # Update depsgraph so children reflect new parent orientation
        bpy.context.view_layer.update()

    # Final update before baking
    bpy.context.view_layer.update()

    # --- Step 4: Bake deformed mesh positions ---
    bpy.ops.object.mode_set(mode='OBJECT')
    _bake_deformation(armature, mesh_obj)

    # --- Step 5: Remove armature modifier ---
    arm_mod_name = None
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE':
            arm_mod_name = mod.name
            mesh_obj.modifiers.remove(mod)
            break

    # --- Step 6: Apply pose as rest pose ---
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply()

    # --- Step 7: Return to object mode ---
    bpy.ops.object.mode_set(mode='OBJECT')

    # --- Step 8: Re-add armature modifier ---
    if arm_mod_name:
        new_mod = mesh_obj.modifiers.new(name=arm_mod_name, type='ARMATURE')
        new_mod.object = armature

    bpy.context.view_layer.update()


# ------------------------------------------------------------------ internals

def _compute_projected_world(armature):
    """Compute projected world positions and accumulated rotations.

    Uses the same algorithm as smd_export._compute_bone_offsets:
    projected_pos = parent_proj + parent_world_rot @ (male07_local × scale)
    where scale = VRM_length / male07_length.

    Returns
    -------
    projected_world : dict[str, Vector]
        Bone name → projected world position.
    world_rotations : dict[str, Matrix]
        Bone name → accumulated 3×3 rotation matrix.
    """
    projected_world = {}
    world_rotations = {}

    existing_bones = {b.name: b for b in armature.data.bones}

    for bone_name in VALVEBIPED_BONE_ORDER:
        bone = existing_bones.get(bone_name)

        ref_rot = MALE07_SMD_ROTATIONS.get(bone_name, (0.0, 0.0, 0.0))
        local_euler = Euler((ref_rot[0], ref_rot[1], ref_rot[2]), 'XYZ')
        local_mat = local_euler.to_matrix()

        parent_name = VALVEBIPED_HIERARCHY.get(bone_name, "")

        # Accumulate world rotation
        if parent_name and parent_name in world_rotations:
            world_rotations[bone_name] = world_rotations[parent_name] @ local_mat
        else:
            world_rotations[bone_name] = local_mat

        if bone is None:
            # QC-only or missing bone: use male_07 reference as-is
            ref_pos = MALE07_REFERENCE_POSITIONS.get(bone_name, (0.0, 0.0, 0.0))
            local_vec = Vector(ref_pos)
            if parent_name and parent_name in projected_world:
                parent_rot = world_rotations[parent_name]
                projected_world[bone_name] = (
                    projected_world[parent_name] + parent_rot @ local_vec
                )
            else:
                projected_world[bone_name] = local_vec
            continue

        if not parent_name or parent_name not in projected_world:
            # Root bone: use VRM world position
            projected_world[bone_name] = bone.head_local.copy()
            continue

        # Child bone: projected = parent_proj + parent_rot @ (male07_dir × VRM_len)
        parent_bone = existing_bones.get(parent_name)
        parent_wpos = (parent_bone.head_local.copy()
                       if parent_bone is not None
                       else Vector((0.0, 0.0, 0.0)))
        vrm_length = (bone.head_local - parent_wpos).length

        ref_pos = MALE07_REFERENCE_POSITIONS.get(bone_name, (0.0, 0.0, 0.0))
        male07_length = math.sqrt(
            ref_pos[0] ** 2 + ref_pos[1] ** 2 + ref_pos[2] ** 2
        )

        if male07_length > 0.001:
            scale = vrm_length / male07_length
            proj_local = Vector((
                ref_pos[0] * scale,
                ref_pos[1] * scale,
                ref_pos[2] * scale,
            ))
        else:
            proj_local = Vector(ref_pos)

        parent_rot = world_rotations[parent_name]
        projected_world[bone_name] = (
            projected_world[parent_name] + parent_rot @ proj_local
        )

    return projected_world, world_rotations


def _build_children_map(armature):
    """Build parent → [children] mapping, filtered to bones that exist in armature.

    Returns
    -------
    dict[str, list[str]]
        Parent bone name → list of child bone names (that exist in armature).
    """
    existing = {b.name for b in armature.data.bones}
    children_of = {}
    for child_name, parent_name in VALVEBIPED_HIERARCHY.items():
        if parent_name and child_name in existing and child_name not in QC_ONLY_BONES:
            children_of.setdefault(parent_name, []).append(child_name)
    return children_of


def _find_primary_child(bone_name, children_of, armature):
    """Find the primary child bone for direction computation.

    For bones with multiple children (e.g. Spine4 → Neck + Clavicles),
    prefer the "spine chain" child over branch children.

    Returns
    -------
    str or None
        Name of the primary child bone, or None if leaf bone.
    """
    children = children_of.get(bone_name, [])
    if not children:
        return None

    # Priority order for selecting primary child:
    # 1. Spine chain continuation (Spine → Spine1 → Spine2 → Spine4 → Neck → Head)
    # 2. First available child
    spine_chain = {
        "ValveBiped.Bip01_Pelvis": "ValveBiped.Bip01_Spine",
        "ValveBiped.Bip01_Spine": "ValveBiped.Bip01_Spine1",
        "ValveBiped.Bip01_Spine1": "ValveBiped.Bip01_Spine2",
        "ValveBiped.Bip01_Spine2": "ValveBiped.Bip01_Spine4",
        "ValveBiped.Bip01_Spine4": "ValveBiped.Bip01_Neck1",
        "ValveBiped.Bip01_Neck1": "ValveBiped.Bip01_Head1",
    }
    preferred = spine_chain.get(bone_name)
    if preferred and preferred in children:
        return preferred

    # For hand bones, prefer finger2 (middle finger) for direction
    if "Hand" in bone_name:
        for c in children:
            if "Finger2" in c and "Finger2" not in c.replace("Finger2", "", 1):
                return c

    return children[0]


def _bake_deformation(armature, mesh_obj):
    """Copy deformed (posed) vertex positions into the original mesh.

    Uses Blender's depsgraph evaluation to get the armature-deformed mesh,
    then writes those positions back to the original mesh data.  This
    preserves shape keys (only the Basis is modified; deltas stay intact).
    """
    # Make sure depsgraph is fully up to date
    depsgraph = bpy.context.evaluated_depsgraph_get()

    eval_obj = mesh_obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

    # Verify vertex count matches
    orig_mesh = mesh_obj.data
    if len(eval_mesh.vertices) != len(orig_mesh.vertices):
        eval_obj.to_mesh_clear()
        raise RuntimeError(
            f"Vertex count mismatch after pose evaluation: "
            f"orig={len(orig_mesh.vertices)}, eval={len(eval_mesh.vertices)}"
        )

    # Compute per-vertex displacement (deformed − original)
    displacements = []
    for i, vert in enumerate(orig_mesh.vertices):
        displacements.append(eval_mesh.vertices[i].co - vert.co)

    # Copy deformed positions back to original mesh
    for i, vert in enumerate(orig_mesh.vertices):
        vert.co = eval_mesh.vertices[i].co.copy()

    eval_obj.to_mesh_clear()

    # Apply the same displacement to ALL shape keys (not just Basis).
    # Without this, shape keys like blink retain T-pose vertex positions
    # and flex animations briefly snap the mesh back to T-pose.
    if orig_mesh.shape_keys and orig_mesh.shape_keys.key_blocks:
        for kb in orig_mesh.shape_keys.key_blocks:
            for i in range(len(kb.data)):
                kb.data[i].co = kb.data[i].co + displacements[i]
