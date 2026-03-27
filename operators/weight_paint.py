"""Weight paint quick-select operator for GMod bone editing."""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty

from ..utils.bone_utils import find_armature


class VRM2GMOD_OT_SelectBoneWeight(Operator):
    """指定ボーンのウェイトペイントモードに移行"""
    bl_idname = "vrm2gmod.select_bone_weight"
    bl_label = "ボーンウェイト選択"
    bl_description = "指定ボーンのウェイトペイントモードに移行"
    bl_options = {'REGISTER', 'UNDO'}

    bone_name: StringProperty(
        name="Bone Name",
        description="ValveBiped bone name to paint weights for",
        default="",
    )

    @classmethod
    def poll(cls, context):
        armature = find_armature(context)
        if armature is None:
            return False
        for obj in context.view_layer.objects:
            try:
                if obj.type == 'MESH' and obj.parent == armature:
                    return True
            except ReferenceError:
                continue
        return False

    def execute(self, context):
        armature = find_armature(context)
        bone_name = self.bone_name

        if not bone_name:
            self.report({'WARNING'}, "ボーン名が指定されていません")
            return {'CANCELLED'}

        # Find mesh child of armature
        mesh_obj = None
        for obj in context.view_layer.objects:
            try:
                if obj.type == 'MESH' and obj.parent == armature:
                    mesh_obj = obj
                    break
            except ReferenceError:
                continue

        if mesh_obj is None:
            self.report({'WARNING'}, "メッシュオブジェクトが見つかりません")
            return {'CANCELLED'}

        # Check vertex group exists
        vg = mesh_obj.vertex_groups.get(bone_name)
        if vg is None:
            self.report({'WARNING'},
                        f"頂点グループ '{bone_name}' が見つかりません")
            return {'CANCELLED'}

        # Return to object mode first
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Set mesh as active, select both mesh and armature
        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        armature.select_set(True)
        context.view_layer.objects.active = mesh_obj

        # Enter weight paint mode
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        # Set active vertex group
        mesh_obj.vertex_groups.active_index = vg.index

        # Highlight the bone in the armature
        if bone_name in armature.data.bones:
            armature.data.bones.active = armature.data.bones[bone_name]

        self.report({'INFO'}, f"ウェイトペイント: {bone_name}")
        return {'FINISHED'}


classes = (
    VRM2GMOD_OT_SelectBoneWeight,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
