"""Material conversion operator: extract textures, generate VMT, convert to VTF."""

import os
import re
import bpy
from bpy.types import Operator
from pathlib import Path

from ..data.vmt_templates import generate_vmt
from ..utils.bone_utils import find_armature
from ..utils.material_names import (
    sanitize_name,
    collect_materials_ordered,
    build_material_name_map,
)
from ..utils.texture_utils import (
    extract_base_color,
    generate_solid_color_png,
    search_texture_nearby,
)
from ..utils.vtf_convert import convert_to_vtf
from ..utils.vtf_writer import png_to_vtf_blender


class VRM2GMOD_OT_MaterialConvert(Operator):
    bl_idname = "vrm2gmod.material_convert"
    bl_label = "マテリアル変換"
    bl_description = "テクスチャ抽出、VMT生成、VTF変換を実行"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_armature(context) is not None

    def execute(self, context):
        armature = find_armature(context)
        props = context.scene.vrm2gmod
        model_name = sanitize_name(props.model_name) or "my_vrm_model"

        output_base = bpy.path.abspath(props.output_path)
        if not output_base:
            output_base = os.path.join(os.path.dirname(bpy.data.filepath or os.getcwd()),
                                       "vrm2gmod_output")

        # Directories
        compile_dir = os.path.join(output_base, "compile")
        tex_dir = os.path.join(compile_dir, "textures")
        materials_dir = os.path.join(output_base, "materials", "models", "player", model_name)
        os.makedirs(tex_dir, exist_ok=True)
        os.makedirs(materials_dir, exist_ok=True)

        cdmaterials = f"models/player/{model_name}"

        # Collect mesh objects
        mesh_objects = [obj for obj in context.scene.objects
                        if obj.type == 'MESH' and obj.parent == armature]

        if not mesh_objects:
            self.report({'ERROR'}, "メッシュオブジェクトが見つかりません")
            return {'CANCELLED'}

        # Gather all materials in deterministic slot order
        materials = collect_materials_ordered(mesh_objects)

        if not materials:
            self.report({'WARNING'}, "マテリアルが見つかりません")
            return {'CANCELLED'}

        # Build unique material name map (shared with SMD exporter)
        naming_mode = getattr(props, 'material_naming', 'SEQUENTIAL')
        mat_name_map = build_material_name_map(
            materials, model_name=model_name, naming_mode=naming_mode)

        # Build texture override map from UI material_items
        override_map = {}
        if hasattr(props, 'material_items'):
            for item in props.material_items:
                if item.override_texture:
                    abs_path = bpy.path.abspath(item.override_texture)
                    if abs_path and os.path.isfile(abs_path):
                        override_map[item.blender_name] = abs_path

        # Process each material
        vmt_count = 0
        tex_count = 0
        vtf_count = 0
        solid_count = 0
        try:
            prefs = context.preferences.addons[__package__.split('.')[0]].preferences
            vtfcmd_path = prefs.vtfcmd_path
        except (KeyError, AttributeError):
            # Addon loaded via direct import (headless mode) — no addon prefs
            vtfcmd_path = ""

        material_statuses = {}
        for mat in materials:
            mat_name = mat_name_map[mat.name]
            override = override_map.get(mat.name)
            result = self._process_material(
                mat, mat_name, tex_dir, materials_dir, cdmaterials,
                vtfcmd_path, props.auto_vtf, texture_override=override,
            )
            tex_count += result['textures']
            vmt_count += result['vmts']
            vtf_count += result['vtfs']
            status = result.get('tex_status', 'OK')
            material_statuses[mat.name] = status
            if status == 'SOLID':
                solid_count += 1

        # Update material_items for UI status display
        if hasattr(props, 'material_items'):
            # Preserve override paths
            existing_overrides = {}
            for item in props.material_items:
                if item.override_texture:
                    existing_overrides[item.blender_name] = item.override_texture
            props.material_items.clear()
            for mat in materials:
                item = props.material_items.add()
                item.blender_name = mat.name
                item.safe_name = mat_name_map[mat.name]
                item.status = material_statuses.get(mat.name, 'OK')
                if mat.name in existing_overrides:
                    item.override_texture = existing_overrides[mat.name]

        status_msg = f"VMT={vmt_count}, テクスチャ={tex_count}, VTF={vtf_count}"
        if solid_count > 0:
            status_msg += f", 単色生成={solid_count}"
        self.report({'INFO'}, f"マテリアル変換完了: {status_msg}")
        return {'FINISHED'}

    def _process_material(self, mat, mat_name, tex_dir, materials_dir,
                          cdmaterials, vtfcmd_path, auto_vtf,
                          texture_override=None):
        """Process a single Blender material: extract textures, generate VMT.

        Texture resolution order for base texture:
          1. User-specified override file (from material overview panel)
          2. Image texture extracted from shader nodes
          3. Solid-color fallback generated from material's base color
        """
        import shutil
        result = {'textures': 0, 'vmts': 0, 'vtfs': 0, 'tex_status': 'OK'}

        # --- Determine alpha mode (even for non-node or override materials) ---
        alpha_mode = self._detect_alpha_mode(mat)

        if not mat.use_nodes and not texture_override:
            # Non-node material: generate solid-color PNG
            color = extract_base_color(mat) or (0.8, 0.8, 0.8, 1.0)
            base_name = mat_name
            png_path = os.path.join(tex_dir, f"{base_name}.png")
            if generate_solid_color_png(color, png_path):
                result['textures'] += 1
                result['tex_status'] = 'SOLID'
                r, g, b = int(color[0]*255), int(color[1]*255), int(color[2]*255)
                self.report({'INFO'},
                            f"単色テクスチャ生成: {mat_name} (#{r:02X}{g:02X}{b:02X})")
                if auto_vtf:
                    ok = self._convert_vtf(
                        vtfcmd_path, tex_dir, materials_dir, base_name)
                    if ok:
                        result['vtfs'] += 1
            vmt_content = generate_vmt(
                texture_name=base_name, cdmaterials=cdmaterials,
                alpha_mode=alpha_mode)
            vmt_path = os.path.join(materials_dir, f"{mat_name}.vmt")
            with open(vmt_path, 'w', encoding='utf-8') as f:
                f.write(vmt_content)
            result['vmts'] += 1
            return result

        node_tree = mat.node_tree if mat.use_nodes else None

        # Find texture nodes
        base_tex = None
        normal_tex = None
        emission_tex = None

        if node_tree:
            for node in node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    # Base Color
                    base_input = node.inputs.get('Base Color')
                    if base_input and base_input.is_linked:
                        linked = base_input.links[0].from_node
                        base_tex = self._find_image_node(linked)

                    # Normal
                    normal_input = node.inputs.get('Normal')
                    if normal_input and normal_input.is_linked:
                        linked = normal_input.links[0].from_node
                        normal_tex = self._find_image_node(linked)

                    # Emission
                    emission_input = node.inputs.get('Emission Color')
                    if not emission_input:
                        emission_input = node.inputs.get('Emission')
                    if emission_input and emission_input.is_linked:
                        linked = emission_input.links[0].from_node
                        emission_tex = self._find_image_node(linked)

                elif node.type == 'GROUP':
                    # MToon shader group node
                    base_tex, normal_tex, emission_tex, alpha_mode = \
                        self._extract_mtoon_textures(node, base_tex, normal_tex,
                                                     emission_tex, alpha_mode)

        # Save textures as PNG
        base_name = ""
        normal_name = ""
        emission_name = ""

        # --- Base texture: override → node → solid-color fallback ---

        # 1. User-specified texture override
        if not base_name and texture_override and os.path.isfile(texture_override):
            base_name = mat_name
            dst = os.path.join(tex_dir, f"{base_name}.png")
            try:
                shutil.copy2(texture_override, dst)
                result['textures'] += 1
                result['tex_status'] = 'OVERRIDE'
                self.report({'INFO'},
                            f"テクスチャオーバーライド適用: {mat_name}")
                if auto_vtf:
                    ok = self._convert_vtf(
                        vtfcmd_path, tex_dir, materials_dir, base_name)
                    if ok:
                        result['vtfs'] += 1
            except Exception as e:
                self.report({'WARNING'},
                            f"オーバーライドコピー失敗 '{mat_name}': {e}")
                base_name = ""

        # 2. Extract from shader node tree
        if not base_name and base_tex and base_tex.image:
            base_name = mat_name
            if self._save_texture(base_tex.image, tex_dir, base_name):
                result['textures'] += 1
                result['tex_status'] = 'OK'
                if auto_vtf:
                    ok = self._convert_vtf(
                        vtfcmd_path, tex_dir, materials_dir, base_name)
                    if ok:
                        result['vtfs'] += 1
            else:
                base_name = ""

        # 3. Solid-color fallback
        if not base_name:
            color = extract_base_color(mat)
            if not color:
                color = (0.8, 0.8, 0.8, 1.0)  # Default gray
            base_name = mat_name
            png_path = os.path.join(tex_dir, f"{base_name}.png")
            if generate_solid_color_png(color, png_path):
                result['textures'] += 1
                result['tex_status'] = 'SOLID'
                r, g, b = int(color[0]*255), int(color[1]*255), int(color[2]*255)
                self.report({'INFO'},
                            f"単色テクスチャ生成: {mat_name} (#{r:02X}{g:02X}{b:02X})")
                if auto_vtf:
                    ok = self._convert_vtf(
                        vtfcmd_path, tex_dir, materials_dir, base_name)
                    if ok:
                        result['vtfs'] += 1
            else:
                base_name = ""
                result['tex_status'] = 'MISSING'

        # --- Normal map ---
        if normal_tex and normal_tex.image:
            normal_name = f"{mat_name}_n"
            if self._save_texture(normal_tex.image, tex_dir, normal_name):
                result['textures'] += 1
                if auto_vtf:
                    ok = self._convert_vtf(
                        vtfcmd_path, tex_dir, materials_dir, normal_name,
                        is_normal_map=True)
                    if ok:
                        result['vtfs'] += 1
            else:
                normal_name = ""

        # --- Emission map ---
        if emission_tex and emission_tex.image:
            emission_name = f"{mat_name}_e"
            if self._save_texture(emission_tex.image, tex_dir, emission_name):
                result['textures'] += 1
                if auto_vtf:
                    ok = self._convert_vtf(
                        vtfcmd_path, tex_dir, materials_dir, emission_name)
                    if ok:
                        result['vtfs'] += 1
            else:
                emission_name = ""

        # Generate VMT
        vmt_content = generate_vmt(
            texture_name=base_name or mat_name,
            cdmaterials=cdmaterials,
            alpha_mode=alpha_mode,
            has_normal=bool(normal_name),
            normal_name=normal_name,
            has_emission=bool(emission_name),
            emission_name=emission_name,
        )

        vmt_path = os.path.join(materials_dir, f"{mat_name}.vmt")
        with open(vmt_path, 'w', encoding='utf-8') as f:
            f.write(vmt_content)
        result['vmts'] += 1

        return result

    def _detect_alpha_mode(self, mat):
        """Detect the alpha/transparency mode from material properties."""
        alpha_mode = "OPAQUE"

        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    alpha_input = node.inputs.get('Alpha')
                    if alpha_input and alpha_input.is_linked:
                        if (hasattr(mat, 'blend_method')
                                and mat.blend_method == 'CLIP'):
                            alpha_mode = "MASK"
                        else:
                            alpha_mode = "BLEND"
                    elif alpha_input and alpha_input.default_value < 1.0:
                        alpha_mode = "BLEND"
                    break

        # VRM extension alpha mode (takes priority)
        if hasattr(mat, 'vrm_addon_extension'):
            try:
                mtoon = mat.vrm_addon_extension.mtoon1
                if hasattr(mtoon, 'extensions'):
                    alpha = mtoon.extensions.get('alphaMode', 'OPAQUE')
                    if alpha == 'MASK':
                        alpha_mode = "MASK"
                    elif alpha == 'BLEND':
                        alpha_mode = "BLEND"
            except (AttributeError, KeyError):
                pass

        return alpha_mode

    def _find_image_node(self, node):
        """Recursively find an image texture node."""
        if node.type == 'TEX_IMAGE':
            return node
        # Follow links backwards
        for input_socket in node.inputs:
            if input_socket.is_linked:
                linked_node = input_socket.links[0].from_node
                result = self._find_image_node(linked_node)
                if result:
                    return result
        return None

    def _extract_mtoon_textures(self, group_node, base_tex, normal_tex,
                                 emission_tex, alpha_mode):
        """Try to extract textures from MToon shader group node."""
        if not group_node.node_tree:
            return base_tex, normal_tex, emission_tex, alpha_mode

        for node in group_node.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                name_lower = node.label.lower() if node.label else node.name.lower()
                if 'base' in name_lower or 'main' in name_lower or 'lit' in name_lower:
                    if not base_tex:
                        base_tex = node
                elif 'normal' in name_lower or 'bump' in name_lower:
                    if not normal_tex:
                        normal_tex = node
                elif 'emiss' in name_lower:
                    if not emission_tex:
                        emission_tex = node

        return base_tex, normal_tex, emission_tex, alpha_mode

    def _convert_vtf(self, vtfcmd_path, tex_dir, materials_dir, name,
                      is_normal_map=False):
        """Convert a PNG texture to VTF, using VTFCmd if available,
        otherwise falling back to the pure-Python writer."""
        png_path = os.path.join(tex_dir, f"{name}.png")
        vtf_path = os.path.join(materials_dir, f"{name}.vtf")

        # Try VTFCmd first (produces DXT5 — smaller files)
        if vtfcmd_path:
            ok, _ = convert_to_vtf(
                vtfcmd_path, png_path, materials_dir, is_normal_map)
            if ok:
                return True

        # Fallback: pure-Python BGRA8888 VTF writer
        ok, _ = png_to_vtf_blender(png_path, vtf_path, is_normal_map)
        return ok

    def _save_texture(self, image, output_dir, name):
        """Save a Blender image as PNG with automatic recovery.

        VRM images may exist in Blender's data but not have pixel data loaded
        (packed inside .glb binary, external reference, etc.).  This method
        attempts multiple recovery strategies before giving up.

        Returns True on success, False on failure.
        """
        import shutil

        filepath = os.path.join(output_dir, f"{name}.png")

        # --- Ensure image data is loaded in memory ---
        if not image.has_data:
            # Strategy 1: image is packed inside the .blend/.glb — unpack it
            try:
                if image.packed_file:
                    image.unpack(method='USE_LOCAL')
                    image.reload()
            except Exception:
                pass

        if not image.has_data:
            # Strategy 2: image has a filepath — reload from disk
            try:
                image.reload()
            except Exception:
                pass

        if not image.has_data:
            # Strategy 3: force pack then unpack (triggers data loading)
            try:
                image.pack()
                image.unpack(method='USE_LOCAL')
                image.reload()
            except Exception:
                pass

        if not image.has_data:
            # Strategy 4: direct file copy (background mode fallback)
            # In Blender --background mode, image pixel data often can't be
            # loaded via API. If the source file exists on disk, copy it
            # directly. This handles external PNG/JPG references.
            source_path = bpy.path.abspath(image.filepath)
            if source_path and os.path.isfile(source_path):
                try:
                    ext = os.path.splitext(source_path)[1].lower()
                    if ext in ('.png', '.jpg', '.jpeg', '.tga', '.bmp'):
                        shutil.copy2(source_path, filepath)
                        self.report(
                            {'INFO'},
                            f"テクスチャ直接コピー: '{image.name}' → {name}.png")
                        return True
                except Exception as e:
                    self.report(
                        {'WARNING'},
                        f"テクスチャコピー失敗 '{image.name}': {e}")

        if not image.has_data:
            # Strategy 5: search nearby directories for the texture file
            found_path = search_texture_nearby(image)
            if found_path:
                try:
                    shutil.copy2(found_path, filepath)
                    self.report(
                        {'INFO'},
                        f"テクスチャ発見（近隣検索）: '{image.name}' → {name}.png")
                    return True
                except Exception as e:
                    self.report(
                        {'WARNING'},
                        f"テクスチャコピー失敗（近隣検索）'{image.name}': {e}")

        if not image.has_data:
            self.report(
                {'WARNING'},
                f"テクスチャ '{image.name}' にデータがありません（スキップ）")
            return False

        # --- Save as PNG ---
        original_path = image.filepath_raw
        original_format = image.file_format
        try:
            image.filepath_raw = filepath
            image.file_format = 'PNG'
            image.save()
        except RuntimeError as e:
            self.report(
                {'WARNING'},
                f"テクスチャ保存失敗 '{image.name}': {e}")
            return False
        finally:
            image.filepath_raw = original_path
            image.file_format = original_format

        return True


classes = (VRM2GMOD_OT_MaterialConvert,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
