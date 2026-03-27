"""SMD exporter — writes Source Engine reference, physics, and proportion-trick meshes.

Replaces Blender Source Tools for SMD export, avoiding stale StructRNA
issues that occur when Source Tools iterates internal object caches after
mesh-join operations.

SMD format reference:
  https://developer.valvesoftware.com/wiki/Studiomdl_Data

Coordinate system:
  SMD uses the same coordinate system as Blender (X-right, Y-forward, Z-up).
  Character faces -Y in both Blender and SMD model space.
  No conversion needed — Blender Source Tools also writes coords directly.

Skeleton Strategy (2026-03-17 — "vertex correction" approach):
  ALL SMDs use the PROJECTED skeleton: male_07 bone directions scaled to
  VRM bone lengths.  This keeps the Proportion Trick delta PURELY ALONG
  BONE DIRECTION (no cross-axis components).

  To compensate for the positional offset between projected and VRM bone
  positions (which differ in bone *direction*), mesh vertex positions are
  ADJUSTED by the weighted bone offset:
      adjusted_vertex = VRM_vertex + sum(w_i * (projected_world_i - VRM_world_i))
  This preserves each vertex's bone-local position (vertex_bone_local) so
  that during animation the vertex follows its bone correctly, with zero
  rotation-dependent distortion.

  reference.smd uses pure male_07 data (positions + rotations).
"""

import math
import bpy
from mathutils import Euler, Matrix, Vector

from ..data.bone_mapping import (
    VALVEBIPED_HIERARCHY,
    VALVEBIPED_BONE_ORDER,
    QC_ONLY_BONES,
    MALE07_REFERENCE_POSITIONS,
    MALE07_SMD_ROTATIONS,
)

# SMD coordinate system = Blender coordinate system (X-right, Y-forward, Z-up).
# No conversion needed. Identity matrices kept to minimise code churn.
_COORD_CONV = Matrix.Identity(4)
_COORD_CONV_INV = Matrix.Identity(4)
_COORD_CONV_3 = Matrix.Identity(3)

# ---------------------------------------------------------------------------
# Arm helper bones that need proportional scaling in proportions.smd.
# Without scaling, VRMod and Source IK see helper bones at male_07 positions
# while main arm bones are at model proportions → inconsistent skeleton →
# VRMod IK solver fails (arms collapse / hands embed in shoulders).
# ---------------------------------------------------------------------------
_ARM_HELPER_BONES = {
    "ValveBiped.Bip01_R_Ulna",
    "ValveBiped.Bip01_R_Wrist",
    "ValveBiped.Bip01_R_Shoulder",
    "ValveBiped.Bip01_R_Bicep",
    "ValveBiped.Bip01_R_Elbow",
    "ValveBiped.Bip01_R_Trapezius",
    "ValveBiped.Bip01_L_Ulna",
    "ValveBiped.Bip01_L_Wrist",
    "ValveBiped.Bip01_L_Elbow",
    "ValveBiped.Bip01_L_Shoulder",
    "ValveBiped.Bip01_L_Bicep",
    "ValveBiped.Bip01_L_Trapezius",
}

# Primary child of each arm bone (for computing length ratio).
_ARM_PRIMARY_CHILD = {
    "ValveBiped.Bip01_R_Clavicle": "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_UpperArm": "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Forearm":  "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_L_Clavicle": "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_UpperArm": "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Forearm":  "ValveBiped.Bip01_L_Hand",
}


# ------------------------------------------------------------------ public API

def write_reference_smd(filepath, armature, mesh_obj, model_name="",
                        naming_mode="SEQUENTIAL"):
    """Export a reference (bind-pose) SMD file.

    Only ValveBiped bones are exported (non-ValveBiped bones filtered out).
    Bones are written in ValveBiped standard order (male_07 reference).
    QC-only bones (helpers, forward, etc.) are included in the skeleton
    but have no vertex weights.

    The skeleton uses the PROJECTED approach (male_07 directions × VRM
    lengths) for clean Proportion Trick deltas.  Mesh vertex positions
    are adjusted by the per-bone (projected − VRM) world offset so that
    each vertex's bone-local position is preserved exactly.

    Parameters
    ----------
    filepath : str
        Destination ``.smd`` path.
    armature : bpy.types.Object
        Armature object whose ``data.bones`` defines the skeleton.
    mesh_obj : bpy.types.Object
        Mesh object (should already be triangulated by mesh_prepare).
    model_name : str
        Model name for sequential material naming.
    naming_mode : str
        "SEQUENTIAL" or "SANITIZE" — must match material_convert.

    Returns
    -------
    bool
        True on success, False on failure.
    """
    # Build ordered bone list: only ValveBiped bones, in standard order
    ordered_bones, bone_idx = _build_ordered_bones(armature)

    # Compute per-bone world position offsets (projected − VRM)
    bone_offsets = _compute_bone_offsets(ordered_bones, bone_idx, armature)

    # Vertex-group index → bone index (mapped through our ordered list)
    vg_to_bone = {}
    for vg in mesh_obj.vertex_groups:
        idx = bone_idx.get(vg.name)
        if idx is not None:
            vg_to_bone[vg.index] = idx

    # Evaluated mesh (modifiers applied, final geometry)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    mesh.calc_loop_triangles()

    uv_layer = mesh.uv_layers.active

    # Transform: mesh object space → armature object space
    mesh_to_arm = armature.matrix_world.inverted() @ mesh_obj.matrix_world
    normal_mat = mesh_to_arm.to_3x3().normalized()

    try:
        with open(filepath, 'w', encoding='ascii', errors='replace') as f:
            f.write("version 1\n")
            _write_nodes_ordered(f, ordered_bones, bone_idx)

            # ★ Projected skeleton for clean Proportion Trick delta
            _write_skeleton_projected(f, ordered_bones, bone_idx, armature)

            f.write("triangles\n")

            # Build material name map using shared module (matches material_convert)
            from .material_names import build_material_name_map
            mesh_mats = [m for m in mesh.materials if m]
            mat_name_map = build_material_name_map(
                mesh_mats, model_name=model_name, naming_mode=naming_mode)

            for tri in mesh.loop_triangles:
                # Material name
                mat_name = _triangle_material(mesh, tri, mat_name_map)
                f.write(f"{mat_name}\n")

                for loop_idx in tri.loops:
                    _write_vertex(
                        f, mesh, loop_idx, mesh_to_arm, normal_mat,
                        uv_layer, vg_to_bone, bone_offsets,
                    )

            f.write("end\n")

    finally:
        eval_obj.to_mesh_clear()

    return True


def write_physics_smd(filepath, armature, phys_objects):
    """Export a physics (ragdoll collision hull) SMD file.

    Parameters
    ----------
    filepath : str
        Destination ``.smd`` path.
    armature : bpy.types.Object
        Armature the physics meshes relate to.
    phys_objects : list[bpy.types.Object]
        Convex-hull mesh objects for physics collision.

    Returns
    -------
    bool
        True on success.
    """
    ordered_bones, bone_idx = _build_ordered_bones(armature)

    # Scale arm helper bones to match proportions.smd for consistency.
    # Without this, helper bones in the physics skeleton would remain at
    # male_07 positions while main arm bones are at model proportions.
    helper_scales = _compute_helper_scales(ordered_bones, bone_idx, armature)

    # Compute per-bone world position offsets (projected − VRM)
    bone_offsets = _compute_bone_offsets(ordered_bones, bone_idx, armature)

    depsgraph = bpy.context.evaluated_depsgraph_get()

    with open(filepath, 'w', encoding='ascii', errors='replace') as f:
        f.write("version 1\n")
        _write_nodes_ordered(f, ordered_bones, bone_idx)

        # ★ Projected skeleton with scaled arm helpers (matches proportions.smd)
        _write_skeleton_projected(f, ordered_bones, bone_idx, armature,
                                  helper_scales=helper_scales)

        f.write("triangles\n")

        for phys_obj in phys_objects:
            eval_obj = phys_obj.evaluated_get(depsgraph)
            phys_mesh = eval_obj.to_mesh()
            phys_mesh.calc_loop_triangles()

            mesh_to_arm = armature.matrix_world.inverted() @ phys_obj.matrix_world
            normal_mat = mesh_to_arm.to_3x3().normalized()

            # Determine the bone this physics piece is bound to
            phys_bone = _physics_bone_index(phys_obj, bone_idx)

            # Get the offset for this physics bone
            phys_offset = bone_offsets.get(phys_bone, Vector((0, 0, 0)))

            for tri in phys_mesh.loop_triangles:
                f.write("phys_mesh\n")
                for loop_idx in tri.loops:
                    loop = phys_mesh.loops[loop_idx]
                    vert = phys_mesh.vertices[loop.vertex_index]

                    pos_arm = mesh_to_arm @ vert.co
                    sp = _COORD_CONV @ pos_arm

                    # Adjust physics vertex by bone offset
                    sp = sp + phys_offset

                    sn = _COORD_CONV_3 @ (normal_mat @ tri.normal)

                    f.write(
                        f"{phys_bone} "
                        f"{sp.x:.6f} {sp.y:.6f} {sp.z:.6f} "
                        f"{sn.x:.6f} {sn.y:.6f} {sn.z:.6f} "
                        f"0.000000 0.000000 0\n"
                    )

            eval_obj.to_mesh_clear()

        f.write("end\n")

    return True


def write_proportions_smd(filepath, armature):
    """Export proportions.smd for the Proportion Trick.

    Contains the model's skeleton with PROJECTED transforms: male_07 bone
    directions scaled to VRM bone lengths. The Proportion Trick delta between
    this and reference.smd (pure male_07) is purely along each bone's length
    direction, preventing cross-axis distortion during animation.

    Arm helper bones (Ulna, Wrist, Shoulder, Bicep, Elbow, Trapezius) are
    scaled proportionally to match the model's actual arm lengths. Without
    this, VRMod and Source IK see helper bones at male_07 positions while
    main arm bones are at model proportions, causing IK solver failures.

    Parameters
    ----------
    filepath : str
        Destination ``.smd`` path.
    armature : bpy.types.Object
        Armature with ValveBiped-named bones (post bone_remap).

    Returns
    -------
    bool
        True on success.
    """
    ordered_bones, bone_idx = _build_ordered_bones(armature)
    helper_scales = _compute_helper_scales(ordered_bones, bone_idx, armature)

    with open(filepath, 'w', encoding='ascii', errors='replace') as f:
        f.write("version 1\n")
        _write_nodes_ordered(f, ordered_bones, bone_idx)

        # ★ Projected skeleton with scaled arm helpers
        _write_skeleton_projected(f, ordered_bones, bone_idx, armature,
                                  helper_scales=helper_scales)

        f.write("triangles\n")
        f.write("end\n")

    return True


def write_reference_skeleton_smd(filepath, armature):
    """Export reference.smd for the Proportion Trick.

    Contains the male_07 standard skeleton (HL2 citizen, positions AND rotations).
    This is the "target" skeleton that HL2 animations are designed for.
    The delta between proportions.smd and this reference captures position
    differences, applied as a predelta autoplay sequence.

    Parameters
    ----------
    filepath : str
        Destination ``.smd`` path.
    armature : bpy.types.Object
        Armature with ValveBiped-named bones.

    Returns
    -------
    bool
        True on success.
    """
    ordered_bones, bone_idx = _build_ordered_bones(armature)

    with open(filepath, 'w', encoding='ascii', errors='replace') as f:
        f.write("version 1\n")
        _write_nodes_ordered(f, ordered_bones, bone_idx)

        # Pure male_07 positions + male_07 rotations (standard ValveBiped skeleton)
        f.write("skeleton\n")
        f.write("time 0\n")

        for smd_idx, (bone_name, bone) in enumerate(ordered_bones):
            # male_07 standard positions
            ref_pos = MALE07_REFERENCE_POSITIONS.get(bone_name)
            if ref_pos:
                px, py, pz = ref_pos
            elif bone is not None:
                # Fallback for bones not in male_07 data (shouldn't happen)
                px, py, pz = 0.0, 0.0, 0.0
            else:
                px, py, pz = 0.0, 0.0, 0.0

            # male_07 standard rotations (SMD RadianEuler format)
            ref_rot = MALE07_SMD_ROTATIONS.get(bone_name)
            if ref_rot is not None:
                rx, ry, rz = ref_rot
            else:
                rx, ry, rz = 0.0, 0.0, 0.0

            f.write(
                f"{smd_idx} "
                f"{px:.6f} {py:.6f} {pz:.6f} "
                f"{rx:.6f} {ry:.6f} {rz:.6f}\n"
            )

        f.write("end\n")

        f.write("triangles\n")
        f.write("end\n")

    return True


def write_flex_vta(filepath, armature, mesh_obj, flex_items):
    """Export a VTA (Valve Vertex Animation) file for flex/morph animation.

    The VTA file contains morph target data that must be vertex-order-
    synchronized with the reference SMD.  Both iterate loop_triangles
    in the same deterministic order.

    Parameters
    ----------
    filepath : str
        Destination ``.vta`` path.
    armature : bpy.types.Object
        Armature object.
    mesh_obj : bpy.types.Object
        Mesh object with shape keys.
    flex_items : iterable
        Collection of flex items with ``name``, ``flex_name``, ``enabled``
        attributes (from ``VRM2GMOD_FlexItem`` PropertyGroup).

    Returns
    -------
    tuple[bool, list[str]]
        (success, list_of_exported_flex_names).
        Returns (False, []) if no exportable shape keys exist.
    """
    # Collect assigned shape key names and flex names
    enabled = []
    for item in flex_items:
        if item.flex_target == 'NONE':
            continue
        if item.flex_target == 'CUSTOM':
            fname = item.custom_flex_name
            if not fname:
                continue
        else:
            fname = item.flex_target
        enabled.append((item.name, fname))
    if not enabled:
        return False, []

    # Verify shape keys exist on the mesh
    if not mesh_obj.data.shape_keys:
        return False, []

    key_blocks = mesh_obj.data.shape_keys.key_blocks
    # Basis shape key: try "Basis" first, fall back to first key block (index 0)
    basis = key_blocks.get("Basis")
    if basis is None and len(key_blocks) > 0:
        basis = key_blocks[0]  # VRC models often use "ベース" or other names
    if basis is None:
        return False, []

    # Filter to only shape keys that actually exist
    valid = []
    for sk_name, flex_name in enabled:
        kb = key_blocks.get(sk_name)
        if kb is not None and kb != basis:
            valid.append((sk_name, flex_name, kb))
    if not valid:
        return False, []

    # Build bone data (same as write_reference_smd)
    ordered_bones, bone_idx = _build_ordered_bones(armature)
    bone_offsets = _compute_bone_offsets(ordered_bones, bone_idx, armature)

    # Vertex-group index → bone index
    vg_to_bone = {}
    for vg in mesh_obj.vertex_groups:
        idx = bone_idx.get(vg.name)
        if idx is not None:
            vg_to_bone[vg.index] = idx

    # Evaluated mesh (same state as SMD export)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    mesh.calc_loop_triangles()

    # Transform: mesh object space → armature object space
    mesh_to_arm = armature.matrix_world.inverted() @ mesh_obj.matrix_world
    normal_mat = mesh_to_arm.to_3x3().normalized()
    rot_3x3 = mesh_to_arm.to_3x3()

    try:
        # Pass 1: Build reference vertex data in SMD triangle order
        # This must match write_reference_smd's iteration order EXACTLY.
        ref_positions = []   # VTA vertex idx → adjusted position (Vector)
        ref_normals = []     # VTA vertex idx → normal (Vector)
        vert_indices = []    # VTA vertex idx → Blender mesh vertex index

        for tri in mesh.loop_triangles:
            for loop_idx in tri.loops:
                loop = mesh.loops[loop_idx]
                vert = mesh.vertices[loop.vertex_index]

                # Position (same as _write_vertex)
                pos_arm = mesh_to_arm @ vert.co
                sp = _COORD_CONV @ pos_arm

                # Bone offset adjustment (same as _write_vertex)
                weights = _get_weights(vert, vg_to_bone)
                if bone_offsets is not None:
                    offset = Vector((0.0, 0.0, 0.0))
                    for bi, w in weights:
                        bo = bone_offsets.get(bi)
                        if bo is not None:
                            offset += w * bo
                    sp = sp + offset

                # Normal
                raw_normal = _get_loop_normal(mesh, loop_idx, vert,
                                              mesh.loop_triangles)
                norm_arm = normal_mat @ raw_normal
                sn = _COORD_CONV_3 @ norm_arm

                ref_positions.append(sp.copy())
                ref_normals.append(sn.copy())
                vert_indices.append(loop.vertex_index)

        total_verts = len(ref_positions)

        # Write VTA file
        with open(filepath, 'w', encoding='ascii', errors='replace') as f:
            f.write("version 1\n")
            _write_nodes_ordered(f, ordered_bones, bone_idx)
            _write_skeleton_projected(f, ordered_bones, bone_idx, armature,
                                      num_extra_frames=len(valid))

            f.write("vertexanimation\n")

            # Frame 0: reference (all vertices)
            f.write("time 0\n")
            for vi in range(total_verts):
                sp = ref_positions[vi]
                sn = ref_normals[vi]
                f.write(
                    f"{vi} "
                    f"{sp.x:.6f} {sp.y:.6f} {sp.z:.6f} "
                    f"{sn.x:.6f} {sn.y:.6f} {sn.z:.6f}\n"
                )

            # Frame N: one per enabled shape key (only changed vertices)
            exported_names = []
            for frame_idx, (sk_name, flex_name, kb) in enumerate(valid, start=1):
                f.write(f"time {frame_idx}\n")

                for vi in range(total_verts):
                    blender_vi = vert_indices[vi]

                    # Delta between shape key and basis in mesh local space
                    basis_co = basis.data[blender_vi].co
                    sk_co = kb.data[blender_vi].co
                    delta = sk_co - basis_co

                    if delta.length < 0.0001:
                        continue

                    # Rotate delta to armature space and add to reference pos
                    delta_arm = rot_3x3 @ delta
                    delta_smd = _COORD_CONV_3 @ delta_arm
                    final_pos = ref_positions[vi] + delta_smd

                    # Use reference normal (studiomdl recomputes normals)
                    sn = ref_normals[vi]

                    f.write(
                        f"{vi} "
                        f"{final_pos.x:.6f} {final_pos.y:.6f} {final_pos.z:.6f} "
                        f"{sn.x:.6f} {sn.y:.6f} {sn.z:.6f}\n"
                    )

                exported_names.append(flex_name)

            f.write("end\n")

    finally:
        eval_obj.to_mesh_clear()

    return True, exported_names


# ------------------------------------------------------------------ internals

def _compute_helper_scales(ordered_bones, bone_idx, armature):
    """Compute proportional scale ratios for arm helper bones.

    For each helper bone in ``_ARM_HELPER_BONES``:
      1. Find its parent bone (from ``VALVEBIPED_HIERARCHY``).
      2. Find the parent's primary non-helper child (from ``_ARM_PRIMARY_CHILD``).
      3. Compute scale = VRM_length / male_07_length for that bone chain.

    This ensures helper bones in proportions.smd are positioned consistently
    with the actual arm bones, so the Proportion Trick delta adjusts them
    together.  Without this, VRMod sees helper bones at male_07 positions
    while main arm bones are at model proportions → IK collapse.

    Returns
    -------
    dict[str, float]
        Mapping from helper bone name → scale ratio.
    """
    scales = {}
    existing_bones = {b.name: b for b in armature.data.bones}

    for helper_name in _ARM_HELPER_BONES:
        parent_name = VALVEBIPED_HIERARCHY.get(helper_name, "")
        if not parent_name:
            continue

        # Find the primary (non-helper) child of the parent bone
        primary_child = _ARM_PRIMARY_CHILD.get(parent_name)
        if not primary_child:
            continue

        # male_07 length: parent → primary child
        ref_pos = MALE07_REFERENCE_POSITIONS.get(primary_child)
        if not ref_pos:
            continue
        male07_length = math.sqrt(
            ref_pos[0] ** 2 + ref_pos[1] ** 2 + ref_pos[2] ** 2
        )
        if male07_length < 0.001:
            continue

        # VRM length: parent → primary child (from armature bone positions)
        parent_bone = existing_bones.get(parent_name)
        child_bone = existing_bones.get(primary_child)
        if parent_bone and child_bone:
            vrm_length = (child_bone.head_local - parent_bone.head_local).length
        else:
            # Bones don't exist in armature — no scaling needed
            continue

        if vrm_length < 0.001:
            continue

        scales[helper_name] = vrm_length / male07_length

    return scales


def _build_ordered_bones(armature):
    """Build an ordered list of (bone_name, bone_object) and index mapping.

    Only includes ValveBiped bones, in standard order (male_07 reference).
    QC-only bones (helpers etc.) are included with bone=None if not in armature.

    Returns
    -------
    ordered_bones : list[tuple[str, bpy.types.Bone | None]]
    bone_idx : dict[str, int]
    """
    existing_bones = {bone.name: bone for bone in armature.data.bones}
    ordered_bones = []
    bone_idx = {}

    for bone_name in VALVEBIPED_BONE_ORDER:
        bone = existing_bones.get(bone_name)
        # Include bone if it exists in armature OR if it's a QC-only bone
        # (QC-only bones need to be in SMD nodes/skeleton for studiomdl)
        if bone is not None or bone_name in QC_ONLY_BONES:
            idx = len(ordered_bones)
            ordered_bones.append((bone_name, bone))
            bone_idx[bone_name] = idx

    return ordered_bones, bone_idx


def _resolve_parent(bone_name, bone_idx):
    """Walk up the hierarchy to find the nearest ancestor that exists in bone_idx.

    If a bone's direct parent is missing (e.g. Finger01 absent when VRM
    lacks ThumbIntermediate), skip to the grandparent and so on.
    Returns -1 only if no ancestor is found (root bone).
    """
    current = bone_name
    for _ in range(20):  # guard against infinite loops
        parent_name = VALVEBIPED_HIERARCHY.get(current, "")
        if not parent_name:
            return -1
        if parent_name in bone_idx:
            return bone_idx[parent_name]
        current = parent_name
    return -1


def _write_nodes_ordered(f, ordered_bones, bone_idx):
    """Write the ``nodes`` section with ordered ValveBiped bones."""
    f.write("nodes\n")
    for i, (bone_name, bone) in enumerate(ordered_bones):
        pid = _resolve_parent(bone_name, bone_idx)
        f.write(f'{i} "{bone_name}" {pid}\n')
    f.write("end\n")


def _compute_bone_offsets(ordered_bones, bone_idx, armature,
                          max_delta=2.0):
    """Compute world position offsets: projected_world − VRM_world per bone.

    The projected skeleton places bones along male_07 directions at VRM
    lengths; VRM world positions are from armature bone data.  The offset
    is used to shift mesh vertices so that their bone-local positions are
    preserved when using the projected bind pose.

    To prevent mesh distortion (thin/flat arms) at joints where vertices
    are weighted to multiple bones with divergent offsets, the CHANGE in
    offset between each bone and its parent (delta) is limited to
    *max_delta* units.  This ensures smooth offset gradients across the
    bone hierarchy while allowing significant total correction to
    accumulate through the chain.

    Compared to a flat magnitude cap (which limits each bone independently
    and loses most correction), delta limiting preserves smooth gradients
    at joints — the key factor in preventing "paper-thin" mesh distortion
    — while allowing the offset to grow through the chain, providing
    meaningful animation correction at distal bones (hand, fingers).

    Parameters
    ----------
    max_delta : float
        Maximum allowed offset change between any bone and its parent,
        in Source Engine units.  Default 2.0 gives smooth joint gradients
        while allowing ~3-5 units total correction at the hand.

    Returns
    -------
    dict[int, Vector]
        Mapping from SMD bone index → smoothed offset vector in
        world/armature space.
    """
    offsets = {}
    projected_world = {}    # bone_name -> Vector (accumulated world position)
    world_rotations = {}    # bone_name -> Matrix3x3 (accumulated male_07 rotation)
    raw_offsets = {}        # bone_name -> Vector (raw unclamped offset)
    smoothed_offsets = {}   # bone_name -> Vector (delta-limited offset)

    for smd_idx, (bone_name, bone) in enumerate(ordered_bones):
        ref_rot = MALE07_SMD_ROTATIONS.get(bone_name, (0.0, 0.0, 0.0))
        local_euler = Euler((ref_rot[0], ref_rot[1], ref_rot[2]), 'XYZ')
        local_mat = local_euler.to_matrix()

        parent_name = VALVEBIPED_HIERARCHY.get(bone_name, "")

        if bone is None:
            # QC-only bone: no VRM data, offset = zero.
            if parent_name and parent_name in world_rotations:
                world_rotations[bone_name] = world_rotations[parent_name] @ local_mat
            else:
                world_rotations[bone_name] = local_mat

            ref_pos = MALE07_REFERENCE_POSITIONS.get(bone_name, (0.0, 0.0, 0.0))
            local_vec = Vector(ref_pos)
            if parent_name and parent_name in projected_world:
                parent_rot = world_rotations[parent_name]
                projected_world[bone_name] = (
                    projected_world[parent_name] + parent_rot @ local_vec
                )
            else:
                projected_world[bone_name] = local_vec

            raw_offsets[bone_name] = Vector((0.0, 0.0, 0.0))
            smoothed_offsets[bone_name] = Vector((0.0, 0.0, 0.0))
            offsets[smd_idx] = Vector((0.0, 0.0, 0.0))
            continue

        if not parent_name or parent_name not in bone_idx:
            # Root bone: projected = VRM (same world position for root).
            # Use estimated position if head_local is at origin.
            world_rotations[bone_name] = local_mat
            root_pos = bone.head_local.copy()
            if root_pos.length < 0.1:
                root_pos = _estimate_root_position(
                    bone, ordered_bones, bone_idx)
            # Clamp Pelvis XY to center — only keep Z (height).
            # VRM models can have Hips offset forward/sideways from origin,
            # which would shift the whole model off-center in Source Engine.
            root_pos.x = 0.0
            root_pos.y = 0.0
            projected_world[bone_name] = root_pos
            raw_offsets[bone_name] = Vector((0.0, 0.0, 0.0))
            smoothed_offsets[bone_name] = Vector((0.0, 0.0, 0.0))
            offsets[smd_idx] = Vector((0.0, 0.0, 0.0))
            continue

        # Accumulate world rotation.
        if parent_name in world_rotations:
            world_rotations[bone_name] = world_rotations[parent_name] @ local_mat
        else:
            world_rotations[bone_name] = local_mat

        # VRM world position (from armature).
        vrm_world = bone.head_local.copy()

        # Compute projected local position (male_07 direction × VRM length).
        parent_idx_val = bone_idx[parent_name]
        parent_bone_name, parent_bone = ordered_bones[parent_idx_val]

        # Use corrected root position if parent was at origin
        if parent_bone is not None and parent_bone.head_local.length < 0.1:
            parent_name_check = parent_bone_name
            parent_check = VALVEBIPED_HIERARCHY.get(parent_name_check, "")
            if not parent_check or parent_check not in bone_idx:
                parent_wpos = _estimate_root_position(
                    parent_bone, ordered_bones, bone_idx)
            else:
                parent_wpos = parent_bone.head_local.copy()
        elif parent_bone is not None:
            parent_wpos = parent_bone.head_local.copy()
        else:
            parent_wpos = Vector((0.0, 0.0, 0.0))
        vrm_length = (vrm_world - parent_wpos).length

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

        # Compute projected world position by accumulating through hierarchy.
        parent_rot = world_rotations[parent_name]
        proj_world = projected_world[parent_name] + parent_rot @ proj_local
        projected_world[bone_name] = proj_world

        # Raw offset = projected − VRM (unclamped).
        raw_offset = proj_world - vrm_world
        raw_offsets[bone_name] = raw_offset

        # Delta-limited smoothing: limit the CHANGE between this bone's
        # offset and its parent's raw offset.  This keeps the gradient
        # between adjacent bones smooth (preventing mesh compression at
        # joints) while allowing the total offset to accumulate through
        # the chain for meaningful animation correction.
        parent_raw = raw_offsets.get(parent_name, Vector((0.0, 0.0, 0.0)))
        parent_smooth = smoothed_offsets.get(parent_name, Vector((0.0, 0.0, 0.0)))

        delta = raw_offset - parent_raw
        delta_mag = delta.length
        if delta_mag > max_delta and delta_mag > 0.001:
            delta = delta * (max_delta / delta_mag)

        smoothed = parent_smooth + delta
        smoothed_offsets[bone_name] = smoothed
        offsets[smd_idx] = smoothed

    return offsets


def _estimate_root_position(root_bone, ordered_bones, bone_idx):
    """Estimate the root bone (Pelvis) world position when head_local is at origin.

    Some VRM models have the Hips bone head at the armature origin (0,0,0)
    with the actual hip height implied by the bone's tail and child bones.
    When bone_remap removes root/ALL_PARENT bones, the Hips-mapped Pelvis
    retains this origin position.

    Uses ``tail_local`` as the hip joint position — this is where child
    bones (Spine, Thighs) connect from.  Falls back to Thigh averages
    or head_local if tail is also at origin.
    """
    # Primary: use bone's tail (the hip joint / connection point)
    if root_bone.tail_local.length > 0.1:
        return root_bone.tail_local.copy()

    # Fallback: average of thigh positions
    thigh_names = [
        "ValveBiped.Bip01_R_Thigh",
        "ValveBiped.Bip01_L_Thigh",
    ]
    thigh_positions = []
    for name in thigh_names:
        if name in bone_idx:
            idx = bone_idx[name]
            _, thigh_bone = ordered_bones[idx]
            if thigh_bone is not None:
                thigh_positions.append(thigh_bone.head_local.copy())

    if thigh_positions:
        avg = Vector((0.0, 0.0, 0.0))
        for pos in thigh_positions:
            avg += pos
        avg /= len(thigh_positions)
        return avg

    # Last resort: use head_local as-is
    return root_bone.head_local.copy()


def _write_skeleton_projected(f, ordered_bones, bone_idx, armature,
                              helper_scales=None, num_extra_frames=0):
    """Write skeleton section using VRM bone lengths along male_07 directions.

    For each real bone (present in armature):
      - Computes VRM bone length (world distance from parent to child)
      - Scales the male_07 parent-relative position by (VRM_len / male07_len)
      - Uses male_07 rotation unchanged

    For QC-only bones (helpers, not in armature):
      - Pure male_07 reference data (positions + rotations)
      - If *helper_scales* is provided, arm helper bone positions are scaled
        to match the model's actual arm proportions.  This ensures the
        Proportion Trick delta adjusts helper bones consistently with main
        arm bones, preventing VRMod IK failures.

    This ensures the Proportion Trick delta (this minus reference.smd) is
    purely along each bone's length direction. No cross-axis components means
    no arm stretching/swinging when animations rotate bones away from T-pose.
    """
    # Pre-compute root bone position override.
    # Some VRM models have Pelvis head_local at origin (0,0,0) because
    # the VRM Hips bone starts at the armature origin. Detect this and
    # estimate the actual hip position from child bones.
    root_pos_override = {}
    for bone_name, bone in ordered_bones:
        if bone is None:
            continue
        parent_name = VALVEBIPED_HIERARCHY.get(bone_name, "")
        if not parent_name or parent_name not in bone_idx:
            # This is a root bone — clamp XY to center, keep Z (height)
            head_pos = bone.head_local.copy()
            if head_pos.length < 0.1:
                head_pos = _estimate_root_position(
                    bone, ordered_bones, bone_idx)
            head_pos.x = 0.0
            head_pos.y = 0.0
            root_pos_override[bone_name] = head_pos

    # Build bone data lines first (needed for VTA extra frames)
    bone_lines = []

    for smd_idx, (bone_name, bone) in enumerate(ordered_bones):
        if bone is None:
            # QC-only bone (helper/attachment).
            ref_pos = MALE07_REFERENCE_POSITIONS.get(bone_name, (0.0, 0.0, 0.0))
            ref_rot = MALE07_SMD_ROTATIONS.get(bone_name, (0.0, 0.0, 0.0))

            # Scale arm helper bones to match model's actual arm proportions.
            scale = 1.0
            if helper_scales and bone_name in helper_scales:
                scale = helper_scales[bone_name]

            bone_lines.append(
                f"{smd_idx} "
                f"{ref_pos[0] * scale:.6f} {ref_pos[1] * scale:.6f} {ref_pos[2] * scale:.6f} "
                f"{ref_rot[0]:.6f} {ref_rot[1]:.6f} {ref_rot[2]:.6f}\n"
            )
            continue

        # male_07 rotation (always used for all real bones)
        ref_rot = MALE07_SMD_ROTATIONS.get(bone_name, (0.0, 0.0, 0.0))

        parent_name = VALVEBIPED_HIERARCHY.get(bone_name, "")
        if not parent_name or parent_name not in bone_idx:
            # Root bone (Pelvis): use VRM world position, male_07 rotation.
            root_pos = root_pos_override.get(bone_name, bone.head_local.copy())
            bone_lines.append(
                f"{smd_idx} "
                f"{root_pos.x:.6f} {root_pos.y:.6f} {root_pos.z:.6f} "
                f"{ref_rot[0]:.6f} {ref_rot[1]:.6f} {ref_rot[2]:.6f}\n"
            )
            continue

        # Child bone: scale male_07 position to VRM bone length.
        parent_idx_val = bone_idx[parent_name]
        parent_bone_name, parent_bone = ordered_bones[parent_idx_val]

        child_wpos = bone.head_local.copy()
        if parent_bone_name in root_pos_override:
            parent_wpos = root_pos_override[parent_bone_name]
        elif parent_bone is not None:
            parent_wpos = parent_bone.head_local.copy()
        else:
            parent_wpos = Vector((0.0, 0.0, 0.0))

        vrm_length = (child_wpos - parent_wpos).length

        ref_pos = MALE07_REFERENCE_POSITIONS.get(bone_name, (0.0, 0.0, 0.0))
        male07_length = math.sqrt(
            ref_pos[0] ** 2 + ref_pos[1] ** 2 + ref_pos[2] ** 2
        )

        if male07_length > 0.001:
            scale = vrm_length / male07_length
            px = ref_pos[0] * scale
            py = ref_pos[1] * scale
            pz = ref_pos[2] * scale
        else:
            px, py, pz = ref_pos

        bone_lines.append(
            f"{smd_idx} "
            f"{px:.6f} {py:.6f} {pz:.6f} "
            f"{ref_rot[0]:.6f} {ref_rot[1]:.6f} {ref_rot[2]:.6f}\n"
        )

    # Write skeleton section
    f.write("skeleton\n")
    f.write("time 0\n")
    f.writelines(bone_lines)

    # For VTA files: studiomdl's Grab_Animation sets endframe from the
    # skeleton section's highest time marker.  The vertexanimation section's
    # time markers must not exceed this endframe, or studiomdl will abort
    # with "Frame MdlError".  Duplicate the bone data for each flex frame.
    for extra_t in range(1, num_extra_frames + 1):
        f.write(f"time {extra_t}\n")
        f.writelines(bone_lines)

    f.write("end\n")


def _write_vertex(f, mesh, loop_idx, mesh_to_arm, normal_mat, uv_layer,
                  vg_to_bone, bone_offsets=None):
    """Write a single vertex line inside a triangle block.

    If *bone_offsets* is provided (dict mapping bone index → Vector offset),
    the vertex position is adjusted by the weighted bone offset so that
    bone-local positions are preserved with the projected skeleton.
    """
    loop = mesh.loops[loop_idx]
    vert = mesh.vertices[loop.vertex_index]

    # Position (mesh space → armature space → SMD space)
    pos_arm = mesh_to_arm @ vert.co
    sp = _COORD_CONV @ pos_arm

    # Normal — prefer per-corner (split) normals for correct shading
    raw_normal = _get_loop_normal(mesh, loop_idx, vert, mesh.loop_triangles)
    norm_arm = normal_mat @ raw_normal
    sn = _COORD_CONV_3 @ norm_arm

    # UV
    u, v = 0.0, 0.0
    if uv_layer:
        uv = uv_layer.data[loop_idx].uv
        u, v = uv[0], uv[1]

    # Bone weights
    weights = _get_weights(vert, vg_to_bone)

    # Adjust vertex position by weighted bone offset.
    # adjusted = VRM_pos + sum(w_i * (projected_world_i - VRM_world_i))
    # This preserves bone-local position: the vertex's offset from each
    # weighted bone is the same as with the original VRM bind pose.
    if bone_offsets is not None:
        offset = Vector((0.0, 0.0, 0.0))
        for bi, w in weights:
            bo = bone_offsets.get(bi)
            if bo is not None:
                offset += w * bo
        sp = sp + offset

    parent = weights[0][0]

    f.write(
        f"{parent} "
        f"{sp.x:.6f} {sp.y:.6f} {sp.z:.6f} "
        f"{sn.x:.6f} {sn.y:.6f} {sn.z:.6f} "
        f"{u:.6f} {v:.6f} "
        f"{len(weights)}"
    )
    for bi, w in weights:
        f.write(f" {bi} {w:.6f}")
    f.write("\n")


def _get_loop_normal(mesh, loop_idx, vert, loop_triangles):
    """Return the best available normal for the given loop.

    Blender 4.1+ provides ``mesh.corner_normals``; older versions
    require ``calc_normals_split()`` + ``loop.normal``.  We fall
    back to the vertex or face normal if neither is available.
    """
    # Modern API (Blender 4.1+)
    if hasattr(mesh, 'corner_normals') and len(mesh.corner_normals) > loop_idx:
        cn = mesh.corner_normals[loop_idx]
        vec = cn.vector if hasattr(cn, 'vector') else Vector(cn)
        if vec.length_squared > 0.001:
            return vec

    # Fallback: vertex normal (smooth) or face normal (flat)
    return vert.normal


def _get_weights(vert, vg_to_bone, max_bones=3):
    """Return normalised ``[(bone_index, weight), ...]`` for a vertex."""
    raw = []
    for g in vert.groups:
        bi = vg_to_bone.get(g.group)
        if bi is not None and g.weight > 0.001:
            raw.append((bi, g.weight))

    if not raw:
        return [(0, 1.0)]

    raw.sort(key=lambda x: x[1], reverse=True)
    raw = raw[:max_bones]
    total = sum(w for _, w in raw)
    return [(b, w / total) for b, w in raw] if total > 0 else [(0, 1.0)]


def _triangle_material(mesh, tri, mat_name_map=None):
    """Return the SMD-safe material name for a triangle."""
    from .material_names import sanitize_name
    if tri.material_index < len(mesh.materials) and mesh.materials[tri.material_index]:
        name = mesh.materials[tri.material_index].name
        if mat_name_map and name in mat_name_map:
            return mat_name_map[name]
    else:
        name = "default"
    return sanitize_name(name)


def _physics_bone_index(phys_obj, bone_idx):
    """Determine which bone a physics object is bound to.

    Checks (in priority order):
      1. parent_bone (set by physics_generate when parenting to armature)
      2. Vertex groups matching a ValveBiped bone name
      3. Object name matching a bone name (with ``phys_`` prefix stripped)
      4. Fallback: root bone (index 0)
    """
    # First: check parent_bone (most reliable — set by physics_generate.py)
    if hasattr(phys_obj, 'parent_bone') and phys_obj.parent_bone:
        idx = bone_idx.get(phys_obj.parent_bone)
        if idx is not None:
            return idx

    # Second: check vertex groups
    for vg in phys_obj.vertex_groups:
        idx = bone_idx.get(vg.name)
        if idx is not None:
            return idx

    # Third: try matching the object name to a bone name
    obj_name = phys_obj.name
    idx = bone_idx.get(obj_name)
    if idx is not None:
        return idx

    # Strip common prefixes ("phys_", "physics_") and retry
    for prefix in ("phys_", "physics_"):
        if obj_name.startswith(prefix):
            stripped = obj_name[len(prefix):]
            idx = bone_idx.get(stripped)
            if idx is not None:
                return idx

    # Fallback: root bone
    return 0
