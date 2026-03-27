"""Mesh preparation operator: join, limit weights, scale, triangulate."""

import bpy
from bpy.types import Operator

from ..utils.bone_utils import find_armature
from ..data.bone_mapping import MESH_EXCLUDE_KEYWORDS

# Source Engine uses inches internally; 1 Blender unit (meter) ≈ 39.3701 Source units
# Standard HL2 playermodel height is ~72 units (~183cm)
SOURCE_UNITS_PER_METER = 39.3701


class VRM2GMOD_OT_MeshPrepare(Operator):
    bl_idname = "vrm2gmod.mesh_prepare"
    bl_label = "メッシュ準備"
    bl_description = "メッシュの結合、ウェイト制限、スケール調整、三角面化を実行"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_armature(context) is not None

    def execute(self, context):
        armature = find_armature(context)
        if not armature:
            self.report({'ERROR'}, "アーマチュアが見つかりません")
            return {'CANCELLED'}

        # Collect mesh children of the armature, filtering out non-body meshes.
        all_meshes = [obj for obj in context.scene.objects
                      if obj.type == 'MESH' and obj.parent == armature]

        # Auto-adopt: find unparented meshes with humanoid vertex groups
        # and automatically parent them to the armature.
        # This handles FBX/VRC models where body parts are imported as
        # separate objects not yet parented to the armature.
        # We check both armature bone names AND common humanoid keywords
        # to handle cases where bone_remap has already renamed bones.
        bone_names = {bone.name for bone in armature.data.bones}
        # Also collect VG names from already-parented meshes (catches
        # pre-rename VRM names that aren't in the bone list anymore)
        parented_vg_names = set()
        for obj in all_meshes:
            parented_vg_names.update(vg.name for vg in obj.vertex_groups)
        known_names = bone_names | parented_vg_names

        adopted = []
        for obj in list(context.scene.objects):
            if obj.type != 'MESH':
                continue
            if obj.parent is not None:
                continue
            obj_vg_names = {vg.name for vg in obj.vertex_groups}
            # Match against bone names, parented mesh VGs, or humanoid keywords
            matching = obj_vg_names & known_names
            if not matching:
                matching = self._has_humanoid_vertex_groups(obj)
            if matching:
                obj.parent = armature
                obj.parent_type = 'ARMATURE'
                obj.matrix_parent_inverse = armature.matrix_world.inverted()
                all_meshes.append(obj)
                adopted.append(obj.name)

        if adopted:
            self.report({'INFO'},
                        f"未紐付けメッシュを自動結合: {len(adopted)}個 "
                        f"({', '.join(adopted[:5])})")

        if not all_meshes:
            self.report({'ERROR'}, "アーマチュアに紐づくメッシュが見つかりません")
            return {'CANCELLED'}

        mesh_objects = self._filter_body_meshes(all_meshes, armature)
        if not mesh_objects:
            self.report({'ERROR'}, "有効なボディメッシュが見つかりません")
            return {'CANCELLED'}

        # Ensure object mode
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        # Step 1: Remove shape key underscores (Source Engine doesn't support them well)
        for obj in mesh_objects:
            self._clean_shape_keys(obj)

        # Step 2: Apply all modifiers except armature
        for obj in mesh_objects:
            self._apply_non_armature_modifiers(context, obj)

        # Step 3: Join all meshes into one
        num_meshes = len(mesh_objects)
        combined = self._join_meshes(context, mesh_objects, armature)
        if not combined:
            self.report({'ERROR'}, "メッシュの結合に失敗しました")
            return {'CANCELLED'}

        # Force Blender to purge stale data-blocks from the join operation.
        # Without this, Source Tools (or other operators) may trip over deleted
        # StructRNA proxies when iterating bpy.data.objects / scene.objects.
        # bpy.data.orphans_purge() is a function (not operator) — no context needed.
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
        context.view_layer.update()

        self.report({'INFO'}, f"メッシュ結合完了: {num_meshes}個 → 1個")

        # Step 3.5: Remove orphaned vertex groups (no matching bone)
        # Mesh join brings VGs from all source meshes, including groups
        # for bones already removed (hair, spring, VRM-specific).
        orphan_count = self._cleanup_orphaned_vgs(combined, armature)
        if orphan_count > 0:
            self.report({'INFO'}, f"孤立頂点グループ削除: {orphan_count}個")

        # Step 4: Clean up material slots (remove empty ones)
        self._clean_material_slots(combined)

        # Step 5: Limit vertex weights to 3 bones per vertex
        self._limit_weights(context, combined, max_bones=3)

        # Step 6: Triangulate
        self._triangulate(context, combined)

        # Step 7: Scale to Source Engine units
        self._scale_model(context, armature, combined)

        # Make sure armature is active again
        bpy.ops.object.select_all(action='DESELECT')
        armature.select_set(True)
        combined.select_set(True)
        context.view_layer.objects.active = armature

        self.report({'INFO'}, "メッシュ準備完了")
        return {'FINISHED'}

    # Common keywords found in humanoid bone/vertex group names across
    # VRM, Unity, Mixamo, MMD, and ValveBiped naming conventions.
    _HUMANOID_VG_KEYWORDS = frozenset({
        'hips', 'spine', 'chest', 'neck', 'head', 'shoulder', 'arm',
        'hand', 'finger', 'leg', 'foot', 'toe', 'pelvis', 'clavicle',
        'thigh', 'j_bip', 'valvebiped', 'bip01', 'upperarm', 'forearm',
    })

    def _has_humanoid_vertex_groups(self, obj):
        """Check if a mesh has vertex groups with common humanoid bone keywords."""
        for vg in obj.vertex_groups:
            name_lower = vg.name.lower()
            if any(kw in name_lower for kw in self._HUMANOID_VG_KEYWORDS):
                return True
        return False

    def _filter_body_meshes(self, mesh_objects, armature):
        """Filter out non-body meshes (accessories, spheres, colliders, etc.).

        Filtering criteria (in order):
        1. Name-based: mesh name contains any keyword from MESH_EXCLUDE_KEYWORDS
        2. Weight-based: mesh has no vertex groups matching armature bones
        3. Geometry-based: mesh is disproportionately small compared to the
           largest mesh (likely an eye highlight, collider, or accessory)
        """
        bone_names = {bone.name for bone in armature.data.bones}
        candidates = []
        excluded_names = []

        for obj in mesh_objects:
            name_lower = obj.name.lower()

            # Filter 1: Name-based exclusion
            if any(kw.lower() in name_lower for kw in MESH_EXCLUDE_KEYWORDS):
                self.report(
                    {'INFO'},
                    f"メッシュ除外(名前): '{obj.name}' "
                    f"({len(obj.data.vertices)}頂点)"
                )
                excluded_names.append(obj.name)
                bpy.data.objects.remove(obj, do_unlink=True)
                continue

            # Filter 2: No matching bone weights
            matching_vgs = [
                vg for vg in obj.vertex_groups if vg.name in bone_names
            ]
            if not matching_vgs:
                self.report(
                    {'INFO'},
                    f"メッシュ除外(ウェイトなし): '{obj.name}' "
                    f"({len(obj.data.vertices)}頂点)"
                )
                excluded_names.append(obj.name)
                bpy.data.objects.remove(obj, do_unlink=True)
                continue

            candidates.append(obj)

        # Filter 3: Geometry-based — exclude disproportionately small meshes
        # A mesh with <1% of the largest mesh's vertex count is likely
        # an accessory (eye highlight sphere, collider, etc.)
        if len(candidates) > 1:
            max_verts = max(len(obj.data.vertices) for obj in candidates)
            threshold = max(max_verts * 0.01, 8)  # at least 8 verts

            valid_meshes = []
            for obj in candidates:
                vert_count = len(obj.data.vertices)
                if vert_count < threshold:
                    self.report(
                        {'INFO'},
                        f"メッシュ除外(小規模): '{obj.name}' "
                        f"({vert_count}頂点, 最大メッシュの"
                        f"{vert_count/max_verts*100:.1f}%)"
                    )
                    excluded_names.append(obj.name)
                    bpy.data.objects.remove(obj, do_unlink=True)
                else:
                    valid_meshes.append(obj)
        else:
            valid_meshes = candidates

        total_excluded = len(mesh_objects) - len(valid_meshes)
        if total_excluded > 0:
            self.report({'INFO'},
                        f"メッシュフィルタ: {total_excluded}個を除外 "
                        f"(残り{len(valid_meshes)}個)")

        return valid_meshes

    def _clean_shape_keys(self, obj):
        """Remove underscores from shape key names (Source Engine limitation)."""
        if not obj.data.shape_keys:
            return
        for key in obj.data.shape_keys.key_blocks:
            if "_" in key.name and key.name != "Basis":
                key.name = key.name.replace("_", "")

    def _apply_non_armature_modifiers(self, context, obj):
        """Apply all modifiers except Armature."""
        context.view_layer.objects.active = obj
        for mod in list(obj.modifiers):
            if mod.type != 'ARMATURE':
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except RuntimeError:
                    # Can't apply with shape keys, skip
                    pass

    def _join_meshes(self, context, mesh_objects, armature):
        """Join all mesh objects into a single mesh."""
        if len(mesh_objects) == 1:
            return mesh_objects[0]

        # Select all mesh objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in mesh_objects:
            obj.select_set(True)

        # Set one as active
        context.view_layer.objects.active = mesh_objects[0]

        # Join
        bpy.ops.object.join()

        # The active object is now the combined mesh
        combined = context.view_layer.objects.active
        combined.name = "body"

        return combined

    def _cleanup_orphaned_vgs(self, combined, armature):
        """Remove vertex groups that have no matching bone in the armature.

        After mesh join, VGs from all source meshes are combined, including
        groups for bones that were removed earlier (hair, spring, VRM-specific).
        These orphaned VGs cause vertices to fall back to Pelvis (bone 0)
        during SMD export. We merge their weights into the nearest ValveBiped bone.
        """
        from ..utils.bone_utils import merge_vertex_groups

        bone_names = {bone.name for bone in armature.data.bones}
        orphaned = [vg.name for vg in combined.vertex_groups if vg.name not in bone_names]

        for vg_name in orphaned:
            name_lower = vg_name.lower()
            # Determine target ValveBiped bone based on name heuristic
            if any(kw in name_lower for kw in ('tail', 'skirt', 'cloth')):
                target = "ValveBiped.Bip01_Pelvis"
            elif any(kw in name_lower for kw in ('leg', 'knee', 'ankle', 'foot')):
                target = "ValveBiped.Bip01_Pelvis"
            elif any(kw in name_lower for kw in ('arm', 'elbow', 'wrist')):
                target = "ValveBiped.Bip01_Spine4"
            else:
                # Default: head (hair, head_L/R, eye, ear, face, etc.)
                target = "ValveBiped.Bip01_Head1"

            merge_vertex_groups(combined, vg_name, target)

        return len(orphaned)

    def _clean_material_slots(self, obj):
        """Remove empty/unused material slots."""
        # Find used material indices
        used_slots = set()
        for poly in obj.data.polygons:
            used_slots.add(poly.material_index)

        # Remove unused from the end
        bpy.context.view_layer.objects.active = obj
        i = len(obj.material_slots) - 1
        while i >= 0:
            if i not in used_slots and not obj.material_slots[i].material:
                obj.active_material_index = i
                bpy.ops.object.material_slot_remove()
            i -= 1

    def _limit_weights(self, context, obj, max_bones=3):
        """Limit vertex weights to max_bones per vertex (Source Engine limit)."""
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        # Use Blender's built-in weight limit
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=max_bones)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"頂点ウェイトを{max_bones}ボーン以下に制限")

    def _triangulate(self, context, obj):
        """Triangulate the mesh (Source Engine requires triangles)."""
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"三角面化完了: {len(obj.data.polygons)}ポリゴン")

    def _scale_model(self, context, armature, mesh_obj):
        """Scale model to Source Engine units.

        Computes the scale factor dynamically based on actual mesh height.
        This handles VRM models with bone-mesh scale mismatches, which occur
        when VRM root bones (Armature/ALL_PARENT) have non-unit scale transforms
        that are lost when bone_remap removes them.

        Standard conversion: 1 meter = 39.3701 Source units.
        If the model appears much smaller than expected (e.g. bone scale at
        1/100 of mesh scale), a correction multiplier is applied automatically.
        """
        # Calculate current height from mesh bounding box
        # bound_box returns 8 corners as Vector-like tuples
        bb = mesh_obj.bound_box
        min_z = min(corner[2] for corner in bb)
        max_z = max(corner[2] for corner in bb)
        current_height = (max_z - min_z) * mesh_obj.scale[2]

        if current_height <= 0:
            self.report({'WARNING'}, "モデルの高さが0です。スケール調整をスキップ")
            return

        # Check for user-specified target height
        props = context.scene.vrm2gmod
        target_cm = getattr(props, 'target_height_cm', 0.0)

        if target_cm > 0:
            # User specified a target height — override automatic scaling
            target_source_units = (target_cm / 100.0) * SOURCE_UNITS_PER_METER
            scale_factor = target_source_units / current_height
            self.report(
                {'INFO'},
                f"目標身長: {target_cm:.0f}cm → "
                f"{target_source_units:.1f} Source units "
                f"(元の身長: {current_height * 100:.0f}cm, "
                f"スケール: x{scale_factor:.2f})")
        else:
            # Standard scale: meters → Source units
            scale_factor = SOURCE_UNITS_PER_METER

        expected_height = current_height * scale_factor

        # Bone-mesh scale mismatch detection (skip if user specified target)
        if target_cm <= 0:
            # Detect bone-mesh scale mismatch:
            # Some VRM models store bone positions at 1/100 scale relative to
            # mesh vertices. When bone_remap removes root bones that had a 100x
            # scale factor, the Armature modifier deforms the mesh to match the
            # tiny bone positions, effectively shrinking it by 100x.
            #
            # If standard scaling would produce a very small model (<10 Source
            # units for any humanoid), the data is in sub-meter units.
            if expected_height < 10.0:
                # Try 100x correction (most common VRM scale mismatch)
                corrected_height = current_height * 100 * SOURCE_UNITS_PER_METER
                if 15.0 <= corrected_height <= 150.0:
                    # Reasonable height after 100x correction
                    scale_factor = SOURCE_UNITS_PER_METER * 100
                    real_height_cm = current_height * 100 * 100
                    self.report(
                        {'INFO'},
                        f"ボーン/メッシュスケール不一致を検出 (100x)。"
                        f"推定身長: {real_height_cm:.0f}cm → "
                        f"{corrected_height:.1f} Source units"
                    )
                else:
                    # Unknown scale — use direct scaling to reasonable height
                    target_height = 55.0
                    scale_factor = target_height / current_height
                    self.report(
                        {'WARNING'},
                        f"モデルのスケールが不明 "
                        f"(高さ {current_height:.6f}, "
                        f"標準変換後 {expected_height:.2f}ユニット)。"
                        f"直接スケール調整: x{scale_factor:.2f}"
                    )
            else:
                self.report(
                    {'INFO'},
                    f"メートル単位検出。高さ {current_height:.3f}m → "
                    f"{expected_height:.1f} Source units"
                )

        # Select armature AND the combined mesh for transform_apply
        bpy.ops.object.select_all(action='DESELECT')
        armature.select_set(True)
        # Only select children that are still in the view layer
        view_layer_objects = set(context.view_layer.objects)
        for child in armature.children:
            if child in view_layer_objects:
                child.select_set(True)
        context.view_layer.objects.active = armature

        # Set scale on armature
        armature.scale = (scale_factor, scale_factor, scale_factor)

        # Apply scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        self.report({'INFO'}, f"スケール調整: x{scale_factor:.2f} (Source Engine単位)")


classes = (VRM2GMOD_OT_MeshPrepare,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
