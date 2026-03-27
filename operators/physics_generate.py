"""Physics model generation operator: creates simplified convex hulls for ragdoll.

Scaling strategy (2026-03-17):
  Each box has a "primary axis" along the bone chain (e.g. X for arms,
  Z for legs/spine).  The primary axis offset/size scales by the bone-
  length ratio (model_length / male_07_length), while cross-section
  axes scale by the global height ratio.  This prevents grossly
  oversized boxes on models with anime proportions.
"""

import bpy
import bmesh
from bpy.types import Operator
from mathutils import Vector

from ..data.physics_presets import (
    PHYSICS_BONES_MALE,
    PHYSICS_BONES_FEMALE,
    compute_bone_scale,
)
from ..data.bone_mapping import MALE07_REFERENCE_POSITIONS
from ..utils.bone_utils import find_armature


class VRM2GMOD_OT_PhysicsGenerate(Operator):
    bl_idname = "vrm2gmod.physics_generate"
    bl_label = "物理モデル生成"
    bl_description = "ラグドール用の簡略化物理メッシュを自動生成"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_armature(context) is not None

    def execute(self, context):
        armature = find_armature(context)
        if not armature:
            self.report({'ERROR'}, "アーマチュアが見つかりません")
            return {'CANCELLED'}

        props = context.scene.vrm2gmod
        body_type = props.body_type

        preset = PHYSICS_BONES_MALE if body_type == 'MALE' else PHYSICS_BONES_FEMALE

        # Create physics mesh collection
        phys_collection = bpy.data.collections.get("Physics")
        if not phys_collection:
            phys_collection = bpy.data.collections.new("Physics")
            context.scene.collection.children.link(phys_collection)

        # Remove existing physics meshes
        for obj in list(phys_collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        # Calculate global height-based scale factor
        mesh_obj = None
        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj.parent == armature:
                mesh_obj = obj
                break

        height_scale = 1.0
        if mesh_obj:
            height_scale = self._calculate_scale_factor(armature, mesh_obj)

        # Pre-compute per-bone length-based scale ratios
        bone_scales = {}   # bone_name -> (ratio, primary_axis)
        for bone_name, *_ in preset:
            result = compute_bone_scale(
                armature, bone_name, MALE07_REFERENCE_POSITIONS
            )
            if result is not None:
                bone_scales[bone_name] = result

        # Generate physics boxes
        created = 0
        for bone_name, ox, oy, oz, sx, sy, sz in preset:
            bone = armature.data.bones.get(bone_name)
            if not bone:
                continue

            # Per-axis scaling: primary axis by bone ratio, others by height
            offset, size = self._scale_box(
                bone_name, ox, oy, oz, sx, sy, sz,
                height_scale, bone_scales,
            )

            box = self._create_physics_box(
                context, bone_name,
                armature.matrix_world @ bone.head_local,
                offset, size,
            )

            # Add a vertex group matching the bone name so that
            # smd_export._physics_bone_index() can reliably map this
            # physics object to the correct bone.
            vg = box.vertex_groups.new(name=bone_name)
            vg.add(list(range(len(box.data.vertices))), 1.0, 'REPLACE')

            # Parent to armature with bone constraint
            box.parent = armature
            box.parent_type = 'BONE'
            box.parent_bone = bone_name

            # Move to physics collection
            for col in box.users_collection:
                col.objects.unlink(box)
            phys_collection.objects.link(box)

            created += 1

        self.report({'INFO'}, f"物理メッシュ生成完了: {created}個のコリジョンボックス")
        return {'FINISHED'}

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _scale_box(bone_name, ox, oy, oz, sx, sy, sz,
                   height_scale, bone_scales):
        """Scale a physics box with per-axis bone-length awareness.

        For bones in *bone_scales*, the primary axis (along the bone chain)
        is scaled by the bone-length ratio while the cross-section axes use
        the global height scale.  For other bones, uniform height scaling.

        Returns (offset: Vector, size: Vector).
        """
        info = bone_scales.get(bone_name)
        if info is None:
            # Uniform height scaling (Pelvis, Head, Hand, Foot, etc.)
            return (
                Vector((ox, oy, oz)) * height_scale,
                Vector((sx, sy, sz)) * height_scale,
            )

        bone_ratio, primary_axis = info

        # Build per-axis scale factors: [scale_x, scale_y, scale_z]
        scales = [height_scale, height_scale, height_scale]
        scales[primary_axis] = bone_ratio

        offset = Vector((ox * scales[0], oy * scales[1], oz * scales[2]))
        size = Vector((sx * scales[0], sy * scales[1], sz * scales[2]))

        return offset, size

    @staticmethod
    def _calculate_scale_factor(armature, mesh_obj):
        """Calculate scale factor based on model height vs standard HL2 height."""
        # Standard HL2 playermodel is ~72 units tall
        min_z = min(v.co.z for v in mesh_obj.data.vertices)
        max_z = max(v.co.z for v in mesh_obj.data.vertices)
        height = (max_z - min_z) * mesh_obj.scale.z

        if height <= 0:
            return 1.0

        # The preset sizes are designed for ~72 unit tall models
        return height / 72.0

    @staticmethod
    def _create_physics_box(context, name, position, offset, size):
        """Create a simple box mesh for physics collision."""
        bm = bmesh.new()

        # Create box centered on offset
        half = size / 2
        verts = [
            bm.verts.new((offset.x - half.x, offset.y - half.y, offset.z - half.z)),
            bm.verts.new((offset.x + half.x, offset.y - half.y, offset.z - half.z)),
            bm.verts.new((offset.x + half.x, offset.y + half.y, offset.z - half.z)),
            bm.verts.new((offset.x - half.x, offset.y + half.y, offset.z - half.z)),
            bm.verts.new((offset.x - half.x, offset.y - half.y, offset.z + half.z)),
            bm.verts.new((offset.x + half.x, offset.y - half.y, offset.z + half.z)),
            bm.verts.new((offset.x + half.x, offset.y + half.y, offset.z + half.z)),
            bm.verts.new((offset.x - half.x, offset.y + half.y, offset.z + half.z)),
        ]

        # Create faces
        bm.faces.new([verts[0], verts[1], verts[2], verts[3]])  # bottom
        bm.faces.new([verts[4], verts[7], verts[6], verts[5]])  # top
        bm.faces.new([verts[0], verts[4], verts[5], verts[1]])  # front
        bm.faces.new([verts[2], verts[6], verts[7], verts[3]])  # back
        bm.faces.new([verts[0], verts[3], verts[7], verts[4]])  # left
        bm.faces.new([verts[1], verts[5], verts[6], verts[2]])  # right

        mesh = bpy.data.meshes.new(f"phys_{name}")
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new(f"phys_{name}", mesh)
        context.collection.objects.link(obj)

        return obj


classes = (VRM2GMOD_OT_PhysicsGenerate,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
