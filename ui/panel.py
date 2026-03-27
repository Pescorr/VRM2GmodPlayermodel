import os
import bpy
from bpy.types import Panel, PropertyGroup, Operator
from bpy.props import (StringProperty, EnumProperty, BoolProperty,
                       FloatProperty, CollectionProperty)

from ..utils.bone_utils import find_armature
from ..data.bone_mapping import WEIGHT_PAINT_BONE_GROUPS
from ..data.flex_mapping import GMOD_FLEX_LIMIT, FLEX_TARGET_ITEMS


class VRM2GMOD_FlexItem(PropertyGroup):
    """Shape Key → flex export item."""
    name: StringProperty(
        name="Shape Key",
        description="Blender shape key name",
    )
    flex_target: EnumProperty(
        name="Flex Target",
        description="GMod上でのflex表情ターゲット",
        items=FLEX_TARGET_ITEMS,
        default='NONE',
    )
    custom_flex_name: StringProperty(
        name="Custom Name",
        description="カスタムflex名（flex_target=CUSTOMの場合）",
        default="",
    )
    is_standard: BoolProperty(
        name="VRM Standard",
        description="Matches a known VRM expression preset",
        default=False,
    )


class VRM2GMOD_MaterialItem(PropertyGroup):
    """Per-material texture status and override path."""
    blender_name: StringProperty(
        name="Material",
        description="Blender material name",
    )
    safe_name: StringProperty(
        name="Safe Name",
        description="Source Engine safe material name",
    )
    status: EnumProperty(
        name="Status",
        items=[
            ('OK', "OK", "Texture found and available"),
            ('MISSING', "不明", "Texture referenced but unavailable"),
            ('SOLID', "単色", "Solid-color fallback generated"),
            ('OVERRIDE', "手動", "User-specified texture file"),
        ],
        default='OK',
    )
    override_texture: StringProperty(
        name="テクスチャ",
        description="手動テクスチャファイルパス（PNG/JPG/TGA）",
        subtype='FILE_PATH',
    )
    base_color_r: FloatProperty(default=0.8, min=0.0, max=1.0)
    base_color_g: FloatProperty(default=0.8, min=0.0, max=1.0)
    base_color_b: FloatProperty(default=0.8, min=0.0, max=1.0)
    base_color_a: FloatProperty(default=1.0, min=0.0, max=1.0)


class VRM2GMOD_DiagnosticItem(PropertyGroup):
    """Single diagnostic result entry."""
    level: EnumProperty(
        name="Level",
        items=[
            ('ERROR', "Error", "Critical issue"),
            ('WARNING', "Warning", "Non-critical issue"),
            ('INFO', "Info", "Informational"),
        ],
        default='INFO',
    )
    message: StringProperty(name="Message", default="")


class VRM2GmodProperties(PropertyGroup):
    model_name: StringProperty(
        name="モデル名",
        description="GMod内でのモデル名（英数字とアンダースコアのみ）",
        default="my_model",
    )

    body_type: EnumProperty(
        name="体型",
        description="アニメーションと物理モデルの基準体型",
        items=[
            ('MALE', "Male", "男性体型（HL2 male アニメーション使用）"),
            ('FEMALE', "Female", "女性体型（HL2 female アニメーション使用）"),
        ],
        default='MALE',
    )

    output_path: StringProperty(
        name="出力先",
        description="変換結果の出力先フォルダ",
        subtype='DIR_PATH',
        default="",
    )

    auto_compile: BoolProperty(
        name="自動コンパイル",
        description="studiomdlで自動的にMDLをコンパイルする",
        default=True,
    )

    auto_vtf: BoolProperty(
        name="自動VTF変換",
        description="テクスチャをVTFに自動変換する",
        default=True,
    )

    copy_to_gmod: BoolProperty(
        name="GModにコピー",
        description="コンパイル後にGMod addonsフォルダに自動コピーする",
        default=False,
    )

    target_height_cm: bpy.props.FloatProperty(
        name="目標身長 (cm)",
        description=(
            "GMod内での目標身長をcmで指定。"
            "0 = モデルの元の身長をそのまま使用。"
            "HL2標準プレイヤーモデルは約183cm"
        ),
        default=0.0,
        min=0.0,
        max=300.0,
        step=500,  # 5cm刻み
        precision=0,
        subtype='NONE',
    )

    finger_mode: bpy.props.EnumProperty(
        name="指ウェイト",
        description="指ボーンのウェイト処理方式",
        items=[
            ('SIMPLE', "簡略（1関節）",
             "各指を1関節に統合。変形防止。デフォルト推奨"),
            ('DETAILED', "詳細（3関節）",
             "各指3関節。品質最高だが変形リスクあり"),
            ('FROZEN', "固定（パー）",
             "指を常に開いた状態で固定"),
        ],
        default='SIMPLE',
    )

    material_naming: bpy.props.EnumProperty(
        name="マテリアル命名",
        description="VMT/VTFのファイル名方式",
        items=[
            ('SEQUENTIAL', "連番 (推奨)",
             "mat_00, mat_01... 衝突なし、Unicode問題なし"),
            ('SANITIZE', "名前ベース (従来)",
             "マテリアル名を英数字化。日本語名で衝突の可能性あり"),
        ],
        default='SEQUENTIAL',
    )

    export_flex: BoolProperty(
        name="表情エクスポート (Flex)",
        description="VRMのShape KeyをSource Engine Flexアニメーションとしてエクスポート",
        default=False,
    )

    flex_items: CollectionProperty(
        type=VRM2GMOD_FlexItem,
        name="Flex Items",
        description="Shape Key → flex export mapping",
    )

    material_items: CollectionProperty(
        type=VRM2GMOD_MaterialItem,
        name="Material Items",
        description="Per-material texture status and override",
    )

    diagnostic_items: CollectionProperty(
        type=VRM2GMOD_DiagnosticItem,
        name="Diagnostic Items",
        description="Post-conversion diagnostic results",
    )


class VRM2GMOD_OT_AutoDetectPaths(Operator):
    """出力先パスからstudiomdl.exeとGMod addonsフォルダを自動検出"""
    bl_idname = "vrm2gmod.auto_detect_paths"
    bl_label = "パス自動検出"
    bl_description = "出力先パスからstudiomdl.exeとGMod addonsフォルダを自動検出"

    def execute(self, context):
        props = context.scene.vrm2gmod
        output = bpy.path.abspath(props.output_path)

        if not output:
            self.report({'WARNING'}, "出力先を先に設定してください")
            return {'CANCELLED'}

        try:
            prefs = context.preferences.addons[
                __package__.split('.')[0]].preferences
        except (KeyError, AttributeError):
            self.report({'ERROR'}, "アドオン設定にアクセスできません")
            return {'CANCELLED'}

        found = 0

        # Auto-detect studiomdl.exe
        path = os.path.normpath(output)
        while path and path != os.path.dirname(path):
            candidate = os.path.join(path, "bin", "studiomdl.exe")
            if os.path.isfile(candidate):
                prefs.studiomdl_path = candidate
                found += 1
                break
            path = os.path.dirname(path)

        # Auto-detect GMod addons folder
        path = os.path.normpath(output)
        while path and path != os.path.dirname(path):
            candidate = os.path.join(path, "garrysmod", "addons")
            if os.path.isdir(candidate):
                prefs.gmod_addons_path = candidate
                found += 1
                break
            path = os.path.dirname(path)

        if found > 0:
            self.report({'INFO'}, f"{found}個のパスを自動検出しました")
        else:
            self.report({'WARNING'},
                        "自動検出できませんでした。手動で設定してください")

        return {'FINISHED'}


class VRM2GMOD_PT_MainPanel(Panel):
    bl_label = "VRM to GMod"
    bl_idname = "VRM2GMOD_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRM2GMod"

    def draw(self, context):
        layout = self.layout
        props = context.scene.vrm2gmod

        # Header
        box = layout.box()
        box.label(text="VRM/.blend → GMod Playermodel 変換",
                  icon='ARMATURE_DATA')

        # Model settings
        layout.label(text="モデル設定", icon='MESH_DATA')
        layout.prop(props, "model_name")
        layout.prop(props, "body_type")
        layout.prop(props, "output_path")

        # Options
        layout.separator()
        layout.label(text="オプション", icon='PREFERENCES')

        # Target height with helper text
        row = layout.row(align=True)
        row.prop(props, "target_height_cm")
        if props.target_height_cm == 0:
            row.label(text="(元の身長)", icon='INFO')
        else:
            source_units = props.target_height_cm / 100 * 39.37
            row.label(text=f"({source_units:.0f} SU)", icon='ARROW_LEFTRIGHT')

        layout.prop(props, "finger_mode")
        layout.prop(props, "material_naming")
        layout.prop(props, "auto_vtf")
        layout.prop(props, "export_flex")
        layout.prop(props, "auto_compile")
        layout.prop(props, "copy_to_gmod")

        # Convert button
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 2.0
        row.operator("vrm2gmod.convert_full", text="変換開始", icon='EXPORT')

        # Re-export button (only active for converted .blend files)
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("vrm2gmod.re_export",
                      text="修正済み再出力", icon='FILE_REFRESH')

        # Individual step operators
        layout.separator()
        box = layout.box()
        box.label(text="個別ステップ", icon='TOOL_SETTINGS')
        col = box.column(align=True)
        col.operator("vrm2gmod.bone_remap",
                      text="1. ボーンリマップ", icon='BONE_DATA')
        col.operator("vrm2gmod.mesh_prepare",
                      text="2. メッシュ準備", icon='MESH_DATA')
        col.operator("vrm2gmod.material_convert",
                      text="3. マテリアル変換", icon='MATERIAL')
        col.operator("vrm2gmod.physics_generate",
                      text="4. 物理モデル生成", icon='PHYSICS')
        col.operator("vrm2gmod.qc_generate",
                      text="5. QC生成", icon='FILE_TEXT')


class VRM2GMOD_PT_PathSettings(Panel):
    """パス設定サブパネル（折りたたみ可能）"""
    bl_label = "パス設定"
    bl_idname = "VRM2GMOD_PT_paths"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRM2GMod"
    bl_parent_id = "VRM2GMOD_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        try:
            prefs = context.preferences.addons[
                __package__.split('.')[0]].preferences
        except (KeyError, AttributeError):
            layout.label(text="アドオン設定が読み込めません", icon='ERROR')
            return

        # Auto-detect button
        layout.operator("vrm2gmod.auto_detect_paths",
                         text="出力先から自動検出", icon='VIEWZOOM')
        layout.separator()

        # studiomdl.exe path with status icon
        row = layout.row(align=True)
        studiomdl_ok = (prefs.studiomdl_path
                        and os.path.isfile(
                            bpy.path.abspath(prefs.studiomdl_path)))
        row.label(text="", icon='CHECKMARK' if studiomdl_ok else 'X')
        row.prop(prefs, "studiomdl_path", text="studiomdl")

        # GMod addons path with status icon
        row = layout.row(align=True)
        addons_ok = (prefs.gmod_addons_path
                     and os.path.isdir(
                         bpy.path.abspath(prefs.gmod_addons_path)))
        row.label(text="", icon='CHECKMARK' if addons_ok else 'X')
        row.prop(prefs, "gmod_addons_path", text="addons")

        # VTFCmd path (optional)
        row = layout.row(align=True)
        vtfcmd_ok = (prefs.vtfcmd_path
                     and os.path.isfile(
                         bpy.path.abspath(prefs.vtfcmd_path)))
        icon = 'CHECKMARK' if vtfcmd_ok else 'REMOVE'
        row.label(text="", icon=icon)
        row.prop(prefs, "vtfcmd_path", text="VTFCmd")
        row.enabled = False  # VTFCmd is optional (built-in writer available)


class VRM2GMOD_PT_WeightPaint(Panel):
    """ウェイトペイント用ボーン選択サブパネル（折りたたみ可能）"""
    bl_label = "ウェイトペイント"
    bl_idname = "VRM2GMOD_PT_weight_paint"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRM2GMod"
    bl_parent_id = "VRM2GMOD_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        armature = find_armature(context)
        if armature is None:
            return False
        return "ValveBiped.Bip01_Pelvis" in armature.data.bones

    def draw(self, context):
        layout = self.layout
        armature = find_armature(context)

        # Find mesh child
        mesh_obj = None
        for obj in context.view_layer.objects:
            try:
                if obj.type == 'MESH' and obj.parent == armature:
                    mesh_obj = obj
                    break
            except ReferenceError:
                continue

        if mesh_obj is None:
            layout.label(text="メッシュが見つかりません", icon='ERROR')
            return

        for group_name, icon, bones in WEIGHT_PAINT_BONE_GROUPS:
            box = layout.box()
            box.label(text=group_name, icon=icon)
            col = box.column(align=True)
            for bone_name in bones:
                # Short display name: "ValveBiped.Bip01_R_Finger01" → "R_Finger01"
                short = bone_name.replace("ValveBiped.Bip01_", "")

                # Enable/disable based on vertex group existence
                has_vg = bone_name in mesh_obj.vertex_groups
                row = col.row(align=True)
                row.enabled = has_vg

                # Highlight currently active bone
                is_active = (context.mode == 'WEIGHT_PAINT'
                             and mesh_obj.vertex_groups.active
                             and mesh_obj.vertex_groups.active.name == bone_name)
                if is_active:
                    row.alert = True

                op = row.operator(
                    "vrm2gmod.select_bone_weight",
                    text=short,
                    icon='BONE_DATA' if has_vg else 'BLANK1')
                op.bone_name = bone_name


class VRM2GMOD_PT_FlexExport(Panel):
    """表情エクスポート設定サブパネル（折りたたみ可能）"""
    bl_label = "表情エクスポート (Flex)"
    bl_idname = "VRM2GMOD_PT_flex_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRM2GMod"
    bl_parent_id = "VRM2GMOD_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.vrm2gmod

        layout.prop(props, "export_flex")

        if not props.export_flex:
            layout.label(text="無効時は従来の出力（flexなし）", icon='INFO')
            return

        # Detect button
        layout.operator("vrm2gmod.detect_shape_keys",
                         text="Shape Key検出", icon='SHAPEKEY_DATA')

        if len(props.flex_items) == 0:
            layout.label(text="検出ボタンを押してください", icon='INFO')
            return

        # Count assigned items (flex_target != 'NONE')
        assigned_count = sum(1 for item in props.flex_items
                             if item.flex_target != 'NONE')
        total_count = len(props.flex_items)
        layout.label(
            text=f"検出: {total_count}個 / 割当済み: {assigned_count}個",
            icon='SHAPEKEY_DATA')

        if assigned_count > GMOD_FLEX_LIMIT:
            layout.label(
                text=f"GMod上限{GMOD_FLEX_LIMIT}個を超えています",
                icon='ERROR')

        # Batch buttons
        row = layout.row(align=True)
        row.operator("vrm2gmod.flex_deselect_all",
                      text="全解除", icon='CHECKBOX_DEHLT')
        row.operator("vrm2gmod.flex_select_standard",
                      text="VRM標準のみ", icon='CHECKMARK')
        row.operator("vrm2gmod.flex_assign_all",
                      text="全自動割当", icon='FILE_TICK')

        # Shape key list with dropdown
        for item in props.flex_items:
            box = layout.box()
            row = box.row(align=True)

            # Shape key name with icon
            if item.is_standard:
                row.label(text=item.name, icon='SHAPEKEY_DATA')
            else:
                row.label(text=item.name, icon='BLANK1')

            # Flex target dropdown
            row.prop(item, "flex_target", text="")

            # Custom name input (only when CUSTOM is selected)
            if item.flex_target == 'CUSTOM':
                box.prop(item, "custom_flex_name", text="名前")


class VRM2GMOD_OT_ScanMaterials(Operator):
    """マテリアルのテクスチャ状態をスキャン"""
    bl_idname = "vrm2gmod.scan_materials"
    bl_label = "テクスチャスキャン"
    bl_description = "全マテリアルのテクスチャ取得状態をスキャンして表示"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return find_armature(context) is not None

    def execute(self, context):
        from ..utils.material_names import (
            collect_materials_ordered,
            build_material_name_map,
            sanitize_name,
        )
        from ..utils.texture_utils import check_texture_status

        armature = find_armature(context)
        props = context.scene.vrm2gmod

        mesh_objects = [obj for obj in context.scene.objects
                        if obj.type == 'MESH' and obj.parent == armature]

        materials = collect_materials_ordered(mesh_objects)
        if not materials:
            self.report({'WARNING'}, "マテリアルが見つかりません")
            return {'CANCELLED'}

        model_name = sanitize_name(props.model_name) or "my_vrm_model"
        naming_mode = getattr(props, 'material_naming', 'SEQUENTIAL')
        mat_name_map = build_material_name_map(
            materials, model_name=model_name, naming_mode=naming_mode)

        # Preserve existing overrides
        existing_overrides = {}
        for item in props.material_items:
            if item.override_texture:
                existing_overrides[item.blender_name] = item.override_texture

        props.material_items.clear()

        ok_count = 0
        missing_count = 0
        solid_count = 0

        for mat in materials:
            item = props.material_items.add()
            item.blender_name = mat.name
            item.safe_name = mat_name_map[mat.name]

            # Restore existing override
            if mat.name in existing_overrides:
                override_path = existing_overrides[mat.name]
                abs_path = bpy.path.abspath(override_path)
                if abs_path and os.path.isfile(abs_path):
                    item.override_texture = override_path
                    item.status = 'OVERRIDE'
                    ok_count += 1
                    continue

            status, color = check_texture_status(mat)
            item.status = status
            if color:
                item.base_color_r = color[0]
                item.base_color_g = color[1]
                item.base_color_b = color[2]
                item.base_color_a = color[3] if len(color) > 3 else 1.0

            if status == 'OK':
                ok_count += 1
            elif status == 'MISSING':
                missing_count += 1
            elif status == 'SOLID':
                solid_count += 1

        self.report(
            {'INFO'},
            f"テクスチャスキャン完了: OK={ok_count}, 単色={solid_count}, "
            f"不明={missing_count}")
        return {'FINISHED'}


class VRM2GMOD_PT_MaterialOverview(Panel):
    """マテリアル概要サブパネル（テクスチャ状態表示・手動割り当て）"""
    bl_label = "マテリアル概要"
    bl_idname = "VRM2GMOD_PT_material_overview"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRM2GMod"
    bl_parent_id = "VRM2GMOD_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return find_armature(context) is not None

    def draw(self, context):
        layout = self.layout
        props = context.scene.vrm2gmod

        # Scan button
        layout.operator("vrm2gmod.scan_materials",
                         text="テクスチャスキャン", icon='VIEWZOOM')

        if len(props.material_items) == 0:
            layout.label(text="スキャンボタンを押してください", icon='INFO')
            return

        # Summary counts
        ok = sum(1 for i in props.material_items if i.status == 'OK')
        solid = sum(1 for i in props.material_items if i.status == 'SOLID')
        missing = sum(1 for i in props.material_items if i.status == 'MISSING')
        override = sum(1 for i in props.material_items
                       if i.status == 'OVERRIDE')
        total = len(props.material_items)

        row = layout.row()
        row.label(text=f"{total}個のマテリアル", icon='MATERIAL')

        # Status summary with color coding
        summary_parts = []
        if ok > 0:
            summary_parts.append(f"OK={ok}")
        if solid > 0:
            summary_parts.append(f"単色={solid}")
        if override > 0:
            summary_parts.append(f"手動={override}")
        if missing > 0:
            summary_parts.append(f"不明={missing}")
        if summary_parts:
            layout.label(text="  ".join(summary_parts))

        # Material list
        for item in props.material_items:
            box = layout.box()
            row = box.row(align=True)

            # Status icon
            if item.status == 'OK':
                icon = 'CHECKMARK'
            elif item.status == 'OVERRIDE':
                icon = 'FILE_IMAGE'
            elif item.status == 'SOLID':
                icon = 'COLORSET_01_VEC'
            else:  # MISSING
                icon = 'ERROR'

            # Material name: "safe_name (blender_name)"
            if item.safe_name:
                label = f"{item.safe_name} ({item.blender_name})"
            else:
                label = item.blender_name
            row.label(text=label, icon=icon)

            # Status label
            row.label(text=item.status)

            # Solid-color info
            if item.status == 'SOLID':
                r = int(item.base_color_r * 255)
                g = int(item.base_color_g * 255)
                b = int(item.base_color_b * 255)
                box.label(text=f"  色: #{r:02X}{g:02X}{b:02X} → 4x4 PNG生成")

            # Override texture path (for MISSING or user override)
            if item.status in ('MISSING', 'OVERRIDE', 'SOLID'):
                box.prop(item, "override_texture", text="手動指定")


class VRM2GMOD_PT_Diagnostics(Panel):
    """変換後診断レポートサブパネル"""
    bl_label = "診断レポート"
    bl_idname = "VRM2GMOD_PT_diagnostics"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRM2GMod"
    bl_parent_id = "VRM2GMOD_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, 'vrm2gmod', None)
        if not props:
            return False
        return hasattr(props, 'diagnostic_items') and len(props.diagnostic_items) > 0

    def draw(self, context):
        layout = self.layout
        props = context.scene.vrm2gmod

        errors = sum(1 for d in props.diagnostic_items if d.level == 'ERROR')
        warnings = sum(1 for d in props.diagnostic_items if d.level == 'WARNING')
        infos = sum(1 for d in props.diagnostic_items if d.level == 'INFO')

        # Summary
        if errors > 0:
            layout.label(text=f"エラー: {errors}  警告: {warnings}",
                         icon='ERROR')
        elif warnings > 0:
            layout.label(text=f"警告: {warnings}  情報: {infos}",
                         icon='INFO')
        else:
            layout.label(text="問題なし", icon='CHECKMARK')

        # Detail list
        for item in props.diagnostic_items:
            row = layout.row()
            if item.level == 'ERROR':
                row.label(text=item.message, icon='CANCEL')
            elif item.level == 'WARNING':
                row.label(text=item.message, icon='ERROR')
            else:
                row.label(text=item.message, icon='CHECKMARK')


classes = (
    VRM2GMOD_FlexItem,
    VRM2GMOD_MaterialItem,
    VRM2GMOD_DiagnosticItem,
    VRM2GmodProperties,
    VRM2GMOD_OT_AutoDetectPaths,
    VRM2GMOD_OT_ScanMaterials,
    VRM2GMOD_PT_MainPanel,
    VRM2GMOD_PT_PathSettings,
    VRM2GMOD_PT_WeightPaint,
    VRM2GMOD_PT_FlexExport,
    VRM2GMOD_PT_MaterialOverview,
    VRM2GMOD_PT_Diagnostics,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vrm2gmod = bpy.props.PointerProperty(type=VRM2GmodProperties)


def unregister():
    del bpy.types.Scene.vrm2gmod
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
