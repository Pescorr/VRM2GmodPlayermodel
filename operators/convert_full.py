"""Full conversion and re-export operators for VRM → GMod playermodel pipeline."""

import os
import shutil
import bpy
from bpy.types import Operator

from ..utils.bone_utils import find_armature
from ..utils.pose_correction import apply_a_pose
from ..utils.smd_export import (
    write_reference_smd,
    write_physics_smd,
    write_proportions_smd,
    write_reference_skeleton_smd,
    write_flex_vta,
)
from ..utils.studiomdl_compile import compile_model
from ..utils.lua_generate import generate_playermodel_lua


# ------------------------------------------------------------------ Mixin
# Shared helper methods used by both ConvertFull (one-click VRM conversion)
# and ReExport (re-export from a manually edited .blend).

class _ConvertMixin:
    """Export / compile helpers shared between convert_full and re_export."""

    def _export_smd(self, context, armature, compile_dir, model_name):
        """Export the reference mesh as SMD using our built-in exporter."""
        try:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            mesh_obj = None
            for obj in context.view_layer.objects:
                try:
                    if obj.type == 'MESH' and obj.parent == armature:
                        mesh_obj = obj
                        break
                except ReferenceError:
                    continue

            if not mesh_obj:
                self.report({'WARNING'}, "エクスポート対象のメッシュが見つかりません")
                return False

            smd_path = os.path.join(compile_dir, f"{model_name}.smd")
            props = context.scene.vrm2gmod
            naming_mode = getattr(props, 'material_naming', 'SEQUENTIAL')
            ok = write_reference_smd(smd_path, armature, mesh_obj,
                                     model_name=model_name,
                                     naming_mode=naming_mode)

            if ok and os.path.isfile(smd_path):
                size_kb = os.path.getsize(smd_path) / 1024
                self.report({'INFO'},
                            f"SMDエクスポート成功: {model_name}.smd ({size_kb:.0f} KB)")
                return True

            self.report({'WARNING'}, "SMDファイルの書き出しに失敗しました")
            return False

        except Exception as e:
            self.report({'ERROR'}, f"SMDエクスポートエラー: {str(e)}")
            return False

    def _export_flex_vta(self, context, armature, compile_dir, model_name):
        """Export VTA flex animation file if enabled and shape keys exist."""
        props = context.scene.vrm2gmod
        if not props.export_flex:
            return

        # Auto-detect shape keys if flex_items is empty
        if len(props.flex_items) == 0:
            try:
                bpy.ops.vrm2gmod.detect_shape_keys()
            except Exception:
                pass

            # Auto-assign all detected shape keys (recognized → standard,
            # unknown → CUSTOM). This mirrors the batch script behavior
            # so the GUI pipeline is fully automatic.
            if len(props.flex_items) > 0:
                from ..data.flex_mapping import auto_assign_all
                for item in props.flex_items:
                    target, custom_name = auto_assign_all(item.name)
                    if target != 'NONE' and item.flex_target == 'NONE':
                        item.flex_target = target
                        if target == 'CUSTOM':
                            item.custom_flex_name = custom_name

        enabled_count = sum(1 for item in props.flex_items
                            if item.flex_target != 'NONE')
        if enabled_count == 0:
            self.report({'INFO'}, "有効なShape Keyがありません。VTAスキップ")
            return

        # Find mesh
        mesh_obj = None
        for obj in context.view_layer.objects:
            try:
                if obj.type == 'MESH' and obj.parent == armature:
                    mesh_obj = obj
                    break
            except ReferenceError:
                continue

        if not mesh_obj:
            self.report({'WARNING'}, "VTAエクスポート: メッシュが見つかりません")
            return

        vta_path = os.path.join(compile_dir, f"{model_name}_flex.vta")
        try:
            ok, flex_names = write_flex_vta(
                vta_path, armature, mesh_obj, props.flex_items)
            if ok:
                size_kb = os.path.getsize(vta_path) / 1024
                self.report({'INFO'},
                            f"VTAエクスポート成功: {len(flex_names)}個のflex "
                            f"({size_kb:.0f} KB)")
            else:
                self.report({'INFO'},
                            "Shape Keyデータなし。VTAスキップ")
        except Exception as e:
            self.report({'WARNING'}, f"VTAエクスポートエラー（続行）: {str(e)}")

    def _export_proportion_smds(self, context, armature, compile_dir):
        """Export SMDs for the Proportion Trick."""
        try:
            prop_path = os.path.join(compile_dir, "proportions.smd")
            ok = write_proportions_smd(prop_path, armature)
            if ok:
                self.report({'INFO'}, "proportions.smd 生成成功")
            else:
                self.report({'WARNING'}, "proportions.smd 生成に失敗")

            ref_path = os.path.join(compile_dir, "reference.smd")
            ok = write_reference_skeleton_smd(ref_path, armature)
            if ok:
                self.report({'INFO'}, "reference.smd 生成成功")
            else:
                self.report({'WARNING'}, "reference.smd 生成に失敗")

        except Exception as e:
            self.report({'WARNING'}, f"Proportion Trick SMD生成エラー: {str(e)}")

    def _export_physics_smd(self, context, armature, compile_dir):
        """Export physics collision meshes as SMD."""
        phys_collection = bpy.data.collections.get("Physics")
        if not phys_collection or not phys_collection.objects:
            return

        try:
            phys_objects = [obj for obj in phys_collection.objects
                           if obj.type == 'MESH']
            if not phys_objects:
                return

            smd_path = os.path.join(compile_dir, "physics.smd")
            ok = write_physics_smd(smd_path, armature, phys_objects)

            if ok:
                self.report({'INFO'}, "物理SMDエクスポート成功")
            else:
                self.report({'WARNING'}, "物理SMDエクスポートをスキップ")

        except Exception as e:
            self.report({'WARNING'}, f"物理メッシュエクスポートエラー: {str(e)}")

    def _find_studiomdl(self, search_path):
        """Auto-detect studiomdl.exe by walking up from a given path."""
        path = os.path.normpath(search_path)
        while path and path != os.path.dirname(path):
            candidate = os.path.join(path, "bin", "studiomdl.exe")
            if os.path.isfile(candidate):
                return candidate
            path = os.path.dirname(path)
        return ""

    def _compile(self, context, compile_dir, model_name, models_dir):
        """Compile the model using studiomdl."""
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        studiomdl_path = prefs.studiomdl_path

        if not studiomdl_path or not os.path.isfile(studiomdl_path):
            studiomdl_path = self._find_studiomdl(compile_dir)
            if studiomdl_path:
                self.report({'INFO'},
                            f"studiomdl.exe 自動検出: {studiomdl_path}")
            else:
                self.report({'WARNING'},
                            "studiomdl.exeのパスが設定されていません。"
                            "アドオン設定で指定するか、GarrysMod内に"
                            "出力先を設定してください")
                return False

        qc_path = os.path.join(compile_dir, f"{model_name}.qc")

        game_dir = ""
        studiomdl_dir = os.path.dirname(studiomdl_path)
        parent_dir = os.path.dirname(studiomdl_dir)
        potential_game_dir = os.path.join(parent_dir, "garrysmod")
        if os.path.isdir(potential_game_dir):
            game_dir = potential_game_dir

        success, log = compile_model(studiomdl_path, qc_path, game_dir)

        if success:
            self.report({'INFO'}, "MDLコンパイル成功")
            studiomdl_output = os.path.join(game_dir, "models", "player", model_name)
            for ext in ('.mdl', '.dx90.vtx', '.dx80.vtx', '.sw.vtx', '.vvd', '.phy'):
                src = os.path.join(studiomdl_output, f"{model_name}{ext}")
                if os.path.isfile(src):
                    dst = os.path.join(models_dir, f"{model_name}{ext}")
                    shutil.copy2(src, dst)
        else:
            self.report({'WARNING'}, f"コンパイルエラー:\n{log[-2000:]}")

        return success

    def _generate_lua(self, output_base, model_name):
        """Generate Lua playermodel registration script in the output directory."""
        lua_dir = os.path.join(output_base, "lua", "autorun")
        os.makedirs(lua_dir, exist_ok=True)

        lua_path = os.path.join(lua_dir, f"{model_name}_playermodel.lua")
        lua_content = generate_playermodel_lua(model_name)

        try:
            with open(lua_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(lua_content)
            self.report({'INFO'},
                        f"Lua登録スクリプト生成: {model_name}_playermodel.lua")
        except Exception as e:
            self.report({'WARNING'}, f"Lua生成エラー: {e}")

    def _copy_to_gmod(self, context, output_base, model_name):
        """Copy output files to GMod addons folder."""
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        gmod_addons = bpy.path.abspath(prefs.gmod_addons_path)

        if not gmod_addons or not os.path.isdir(gmod_addons):
            self.report({'WARNING'}, "GMod addonsフォルダが設定されていないか存在しません")
            return

        addon_dir = os.path.join(gmod_addons, f"vrm_{model_name}")

        # Copy models
        src_models = os.path.join(output_base, "models")
        dst_models = os.path.join(addon_dir, "models")
        if os.path.isdir(src_models):
            if os.path.isdir(dst_models):
                shutil.rmtree(dst_models)
            shutil.copytree(src_models, dst_models)

        # Copy materials
        src_materials = os.path.join(output_base, "materials")
        dst_materials = os.path.join(addon_dir, "materials")
        if os.path.isdir(src_materials):
            if os.path.isdir(dst_materials):
                shutil.rmtree(dst_materials)
            shutil.copytree(src_materials, dst_materials)

        # Copy Lua registration script
        src_lua = os.path.join(output_base, "lua")
        dst_lua = os.path.join(addon_dir, "lua")
        if os.path.isdir(src_lua):
            if os.path.isdir(dst_lua):
                shutil.rmtree(dst_lua)
            shutil.copytree(src_lua, dst_lua)

        # Create addon.json for GMod workshop
        addon_json = os.path.join(addon_dir, "addon.json")
        if not os.path.isfile(addon_json):
            import json
            addon_info = {
                "title": f"VRM Playermodel: {model_name}",
                "type": "model",
                "tags": ["model"],
                "ignore": ["*.psd", "*.smd", "*.dmx", "*.qc"],
            }
            with open(addon_json, 'w', encoding='utf-8') as f:
                json.dump(addon_info, f, indent=2)

        self.report({'INFO'}, f"GModにコピー完了: {addon_dir}")

    def _run_export_pipeline(self, context, armature, output_base,
                             compile_dir, models_dir, model_name):
        """Run Steps 3-8 + Lua + Gmod copy (shared between full and re-export)."""

        # Step 3: Export SMD
        self.report({'INFO'}, "SMDエクスポート...")
        export_ok = self._export_smd(context, armature, compile_dir, model_name)
        if not export_ok:
            self.report({'ERROR'}, "SMDエクスポートに失敗しました")
            return {'CANCELLED'}

        # Step 3.5: Export VTA (flex animation)
        self._export_flex_vta(context, armature, compile_dir, model_name)

        # Step 4: Export Proportion Trick SMDs
        self.report({'INFO'}, "Proportion Trick SMD生成...")
        self._export_proportion_smds(context, armature, compile_dir)

        # Step 5: Material conversion
        self.report({'INFO'}, "マテリアル変換...")
        try:
            result = bpy.ops.vrm2gmod.material_convert()
            if result != {'FINISHED'}:
                self.report({'WARNING'}, "マテリアル変換で一部エラーが発生しました")
        except Exception as e:
            self.report({'WARNING'}, f"マテリアル変換エラー（続行）: {str(e)}")

        # Step 6: Physics model generation / export
        self.report({'INFO'}, "物理モデル生成...")
        phys_collection = bpy.data.collections.get("Physics")
        if phys_collection and phys_collection.objects:
            # Physics objects already exist (re-export case) — just export SMD
            self._export_physics_smd(context, armature, compile_dir)
        else:
            # Generate physics from scratch (first conversion)
            try:
                result = bpy.ops.vrm2gmod.physics_generate()
                if result == {'FINISHED'}:
                    self._export_physics_smd(context, armature, compile_dir)
            except Exception as e:
                self.report({'WARNING'},
                            f"物理モデル生成エラー（続行）: {str(e)}")

        # Step 7: QC generation
        self.report({'INFO'}, "QCファイル生成...")
        try:
            result = bpy.ops.vrm2gmod.qc_generate()
            if result != {'FINISHED'}:
                self.report({'WARNING'}, "QCファイル生成に失敗しました（続行）")
        except Exception as e:
            self.report({'WARNING'}, f"QCファイル生成エラー（続行）: {str(e)}")

        # Save .blend
        self.report({'INFO'}, ".blend ファイルを保存中...")
        blend_path = os.path.join(compile_dir, f"{model_name}.blend")
        try:
            bpy.ops.wm.save_as_mainfile(filepath=blend_path, copy=True)
            self.report({'INFO'}, f".blend 保存完了: {blend_path}")
        except Exception as e:
            self.report({'WARNING'}, f".blend 保存エラー（続行）: {str(e)}")

        # Step 8: Compile with studiomdl (if enabled)
        props = context.scene.vrm2gmod
        if props.auto_compile:
            self.report({'INFO'}, "MDLコンパイル...")
            compile_ok = self._compile(context, compile_dir, model_name, models_dir)
            if not compile_ok:
                self.report({'WARNING'},
                            "MDLコンパイルに失敗しました。"
                            "studiomdl.exeのパスを確認するか、"
                            "Crowbarで手動コンパイルしてください")
        else:
            self.report({'INFO'}, "自動コンパイルはスキップ")

        # Generate Lua
        self._generate_lua(output_base, model_name)

        # Copy to GMod addons (if enabled)
        if props.copy_to_gmod:
            self._copy_to_gmod(context, output_base, model_name)

        # Run post-conversion diagnostics
        self._run_diagnostics(context, armature, model_name)

        return {'FINISHED'}

    def _run_diagnostics(self, context, armature, model_name):
        """Run post-conversion diagnostics and store results."""
        try:
            from ..utils.conversion_diagnostics import run_diagnostics

            props = context.scene.vrm2gmod
            body_type = getattr(props, 'body_type', 'MALE')
            mesh_objects = [obj for obj in context.scene.objects
                            if obj.type == 'MESH' and obj.parent == armature]

            diag_results = run_diagnostics(
                armature, mesh_objects, model_name, body_type)

            # Store results in scene property for UI display
            if hasattr(props, 'diagnostic_items'):
                props.diagnostic_items.clear()
                for item in diag_results:
                    d = props.diagnostic_items.add()
                    d.level = item['level']
                    d.message = item['message']

            # Report summary
            errors = sum(1 for r in diag_results if r['level'] == 'ERROR')
            warnings = sum(1 for r in diag_results if r['level'] == 'WARNING')
            if errors > 0:
                self.report({'WARNING'},
                            f"診断レポート: {errors}個のエラー, "
                            f"{warnings}個の警告")
            elif warnings > 0:
                self.report({'INFO'},
                            f"診断レポート: {warnings}個の警告")
            else:
                self.report({'INFO'}, "診断レポート: 問題なし")

        except Exception as e:
            self.report({'WARNING'}, f"診断レポートエラー（続行）: {e}")


# -------------------------------------------------------------- Full convert

class VRM2GMOD_OT_ConvertFull(_ConvertMixin, Operator):
    bl_idname = "vrm2gmod.convert_full"
    bl_label = "VRM → GMod 変換"
    bl_description = "VRM/.blendモデルをGModプレイヤーモデルにワンクリック変換"
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
        model_name = props.model_name.lower().replace(' ', '_')

        # Validate output path
        output_base = bpy.path.abspath(props.output_path)
        if not output_base:
            output_base = os.path.join(
                os.path.dirname(bpy.data.filepath or os.getcwd()),
                "vrm2gmod_output")

        compile_dir = os.path.join(output_base, "compile")
        models_dir = os.path.join(output_base, "models", "player", model_name)
        materials_dir = os.path.join(
            output_base, "materials", "models", "player", model_name)
        os.makedirs(compile_dir, exist_ok=True)
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(materials_dir, exist_ok=True)

        # Step 1: Bone remapping
        self.report({'INFO'}, "Step 1/8: ボーンリマッピング...")
        result = bpy.ops.vrm2gmod.bone_remap()
        if result != {'FINISHED'}:
            self.report({'ERROR'}, "ボーンリマッピングに失敗しました")
            return {'CANCELLED'}

        # Step 2: Mesh preparation
        self.report({'INFO'}, "Step 2/8: メッシュ準備...")
        result = bpy.ops.vrm2gmod.mesh_prepare()
        if result != {'FINISHED'}:
            self.report({'ERROR'}, "メッシュ準備に失敗しました")
            return {'CANCELLED'}

        # Refresh references after mesh_prepare
        context.view_layer.update()
        armature = find_armature(context)
        if not armature:
            self.report({'ERROR'}, "メッシュ準備後にアーマチュアが見つかりません")
            return {'CANCELLED'}

        # Step 2.5: A-pose conversion
        self.report({'INFO'}, "Step 2.5: A-pose変換...")
        mesh_obj = None
        for obj in context.view_layer.objects:
            try:
                if obj.type == 'MESH' and obj.parent == armature:
                    mesh_obj = obj
                    break
            except ReferenceError:
                continue

        try:
            if mesh_obj:
                apply_a_pose(armature, mesh_obj)
                self.report({'INFO'}, "A-pose変換完了")
            else:
                self.report({'WARNING'},
                            "A-pose変換: メッシュが見つかりません（スキップ）")
        except Exception as e:
            self.report({'WARNING'}, f"A-pose変換エラー（続行）: {str(e)}")

        # Auto-enable flex export if model has shape keys
        if (mesh_obj and not props.export_flex
                and mesh_obj.data.shape_keys
                and len(mesh_obj.data.shape_keys.key_blocks) > 1):
            props.export_flex = True
            self.report({'INFO'},
                        f"Shape Keys検出 → 表情エクスポートを自動有効化 "
                        f"({len(mesh_obj.data.shape_keys.key_blocks) - 1}個)")

        # Steps 3-8 + Lua + Gmod copy
        result = self._run_export_pipeline(
            context, armature, output_base, compile_dir, models_dir, model_name)

        if result == {'FINISHED'}:
            self.report({'INFO'}, f"変換完了！出力先: {output_base}")
        return result


# ---------------------------------------------------------------- Re-export

class VRM2GMOD_OT_ReExport(_ConvertMixin, Operator):
    bl_idname = "vrm2gmod.re_export"
    bl_label = "修正済みモデル再出力"
    bl_description = (
        "変換済み.blendを手動修正後、SMD・マテリアル・コンパイルのみ再実行"
        "（ボーンリマップ・メッシュ準備・A-pose変換はスキップ）"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Only enable when the scene contains a converted armature."""
        armature = find_armature(context)
        if armature is None:
            return False
        # Check for ValveBiped.Bip01_Pelvis — proof that bone_remap ran
        return "ValveBiped.Bip01_Pelvis" in armature.data.bones

    def execute(self, context):
        armature = find_armature(context)
        if not armature:
            self.report({'ERROR'}, "アーマチュアが見つかりません")
            return {'CANCELLED'}

        if "ValveBiped.Bip01_Pelvis" not in armature.data.bones:
            self.report({'ERROR'},
                        "ValveBipedボーンが見つかりません。"
                        "変換済み.blendファイルで使用してください")
            return {'CANCELLED'}

        props = context.scene.vrm2gmod
        model_name = props.model_name.lower().replace(' ', '_')

        output_base = bpy.path.abspath(props.output_path)
        if not output_base:
            output_base = self._detect_output_base(model_name)

        compile_dir = os.path.join(output_base, "compile")
        models_dir = os.path.join(output_base, "models", "player", model_name)
        materials_dir = os.path.join(
            output_base, "materials", "models", "player", model_name)
        os.makedirs(compile_dir, exist_ok=True)
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(materials_dir, exist_ok=True)

        self.report({'INFO'},
                    f"再出力開始 出力先: {output_base}")

        result = self._run_export_pipeline(
            context, armature, output_base, compile_dir, models_dir, model_name)

        if result == {'FINISHED'}:
            self.report({'INFO'}, f"再出力完了！出力先: {output_base}")
        return result

    def _detect_output_base(self, model_name):
        """Detect output_base from the current .blend file location.

        If the .blend is inside a compile/ directory (saved during conversion),
        use the parent of compile/ as output_base. Otherwise fall back to
        creating a vrm2gmod_output directory next to the .blend.
        """
        blend_path = bpy.data.filepath
        if not blend_path:
            return os.path.join(os.getcwd(), "vrm2gmod_output")

        blend_dir = os.path.dirname(blend_path)
        dir_name = os.path.basename(blend_dir)

        # If .blend is inside a "compile" folder, output_base is one level up
        if dir_name.lower() == "compile":
            parent = os.path.dirname(blend_dir)
            if parent:
                self.report({'INFO'},
                            f"compile/内の.blendから出力先を検出: {parent}")
                return parent

        return os.path.join(blend_dir, "vrm2gmod_output")


classes = (VRM2GMOD_OT_ConvertFull, VRM2GMOD_OT_ReExport)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
