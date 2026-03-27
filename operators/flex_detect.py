"""Shape Key detection and flex selection operators."""

import bpy
from bpy.types import Operator

from ..utils.bone_utils import find_armature
from ..data.flex_mapping import get_flex_target, GMOD_FLEX_LIMIT


class VRM2GMOD_OT_DetectShapeKeys(Operator):
    """メッシュのShape Keysを検出してflex_itemsに登録"""
    bl_idname = "vrm2gmod.detect_shape_keys"
    bl_label = "Shape Key検出"
    bl_description = "メッシュのShape Keysを検出し、flexエクスポート対象を設定"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        armature = find_armature(context)
        if armature is None:
            return False

        def _has_mesh_descendant(obj):
            for child in obj.children:
                try:
                    if child.type == 'MESH':
                        return True
                    if _has_mesh_descendant(child):
                        return True
                except ReferenceError:
                    continue
            return False

        return _has_mesh_descendant(armature)

    def _find_mesh_with_shape_keys(self, armature):
        """アーマチュア配下の全階層からShape Keysを持つメッシュを探す"""
        def _descendants(obj):
            for child in obj.children:
                yield child
                yield from _descendants(child)

        # まず直接の子メッシュからShape Keysを持つものを探す
        for obj in _descendants(armature):
            try:
                if (obj.type == 'MESH'
                        and obj.data.shape_keys
                        and len(obj.data.shape_keys.key_blocks) > 1):
                    return obj
            except ReferenceError:
                continue

        # Shape Keysを持つメッシュがなければ、最初のメッシュを返す
        for obj in _descendants(armature):
            try:
                if obj.type == 'MESH':
                    return obj
            except ReferenceError:
                continue
        return None

    def execute(self, context):
        armature = find_armature(context)
        props = context.scene.vrm2gmod

        # Find mesh with shape keys (search all descendants)
        mesh_obj = self._find_mesh_with_shape_keys(armature)

        if mesh_obj is None:
            self.report({'WARNING'}, "メッシュが見つかりません")
            return {'CANCELLED'}

        if not mesh_obj.data.shape_keys:
            self.report({'INFO'}, "Shape Keysが見つかりません")
            props.flex_items.clear()
            return {'FINISHED'}

        # Clear existing items
        props.flex_items.clear()

        standard_count = 0
        for kb in mesh_obj.data.shape_keys.key_blocks:
            if kb.name == "Basis":
                continue

            flex_target, is_standard = get_flex_target(kb.name)

            item = props.flex_items.add()
            item.name = kb.name
            item.flex_target = flex_target
            item.is_standard = is_standard

            if is_standard:
                standard_count += 1

        total = len(props.flex_items)
        self.report({'INFO'},
                    f"Shape Keys検出: {total}個 "
                    f"(VRM標準: {standard_count}個を自動選択)")

        if total > GMOD_FLEX_LIMIT:
            self.report({'WARNING'},
                        f"Shape Keysが{total}個検出されました。"
                        f"GMod上限は{GMOD_FLEX_LIMIT}個です。")

        return {'FINISHED'}


class VRM2GMOD_OT_FlexDeselectAll(Operator):
    """全てのflex項目をスキップに設定"""
    bl_idname = "vrm2gmod.flex_deselect_all"
    bl_label = "全解除"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for item in context.scene.vrm2gmod.flex_items:
            item.flex_target = 'NONE'
        return {'FINISHED'}


class VRM2GMOD_OT_FlexSelectStandard(Operator):
    """VRM標準表情のみ自動割当、他はスキップ"""
    bl_idname = "vrm2gmod.flex_select_standard"
    bl_label = "VRM標準のみ"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for item in context.scene.vrm2gmod.flex_items:
            target, is_std = get_flex_target(item.name)
            item.flex_target = target
        return {'FINISHED'}


class VRM2GMOD_OT_FlexAssignAll(Operator):
    """全Shape Keyを自動割当（認識可能=標準flex、その他=カスタム名）"""
    bl_idname = "vrm2gmod.flex_assign_all"
    bl_label = "全自動割当"
    bl_description = (
        "認識可能なShape Keyは標準flexに、"
        "それ以外はカスタム名として割当（Base/Basisはスキップ）"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..data.flex_mapping import auto_assign_all, GMOD_FLEX_LIMIT

        assigned = 0
        custom = 0
        for item in context.scene.vrm2gmod.flex_items:
            target, custom_name = auto_assign_all(item.name)
            item.flex_target = target
            if target == 'CUSTOM':
                item.custom_flex_name = custom_name
                custom += 1
            if target != 'NONE':
                assigned += 1

        self.report({'INFO'},
                    f"全自動割当完了: {assigned}個割当 "
                    f"(カスタム: {custom}個)")

        if assigned > GMOD_FLEX_LIMIT:
            self.report({'WARNING'},
                        f"GMod上限{GMOD_FLEX_LIMIT}個を超えています "
                        f"({assigned}個)")

        return {'FINISHED'}


classes = (
    VRM2GMOD_OT_DetectShapeKeys,
    VRM2GMOD_OT_FlexDeselectAll,
    VRM2GMOD_OT_FlexSelectStandard,
    VRM2GMOD_OT_FlexAssignAll,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
