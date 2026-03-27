"""Bone remapping operator: VRM humanoid bones → ValveBiped bones.

Handles:
  1. Spring/collider bone removal
  2. ThumbMetacarpal merge
  3. Missing spine bone insertion (including Spine4)
  4. VRM-specific bone removal (ponite, ear, tail, etc.) with weight transfer
  5. Bone renaming to ValveBiped names
  6. Hierarchy fix to match ValveBiped standard
"""

import bpy
from bpy.types import Operator

from ..data.bone_mapping import (
    VRM_TO_VALVEBIPED,
    VRM_MERGE_BONES,
    SPRING_BONE_PREFIXES,
    VALVEBIPED_HIERARCHY,
    VRM_EXCLUDE_PREFIXES,
)
from ..utils.bone_utils import (
    find_armature,
    get_vrm_humanoid_mapping,
    merge_vertex_groups,
    split_vertex_group_by_distance,
    cleanup_vertex_weights,
    insert_bone_between,
    simplify_finger_weights,
)


class VRM2GMOD_OT_BoneRemap(Operator):
    bl_idname = "vrm2gmod.bone_remap"
    bl_label = "ボーンリマップ"
    bl_description = "VRM/汎用ヒューマノイドボーンをValveBiped命名規則にリネーム"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        from ..utils.bone_utils import find_armature
        return find_armature(context) is not None

    def execute(self, context):
        armature = find_armature(context)
        if not armature:
            self.report({'ERROR'}, "アーマチュアが見つかりません")
            return {'CANCELLED'}

        # Get VRM humanoid mapping (supports VRM metadata + pattern guessing)
        vrm_mapping = get_vrm_humanoid_mapping(armature)
        if not vrm_mapping:
            self.report({'ERROR'},
                        "ヒューマノイドボーンを検出できませんでした。\n"
                        "VRMモデル、またはヒューマノイドボーン構造を持つモデルが必要です。\n"
                        "対応形式: VRM (VRoid/UniVRM), Cats Plugin, Mixamo, MMD, 汎用FBX")
            return {'CANCELLED'}

        # Check if this is a pattern-guessed mapping (no VRM metadata)
        has_vrm_ext = getattr(armature.data, 'vrm_addon_extension', None) is not None
        if has_vrm_ext:
            self.report({'INFO'}, f"VRMボーンマッピング検出: {len(vrm_mapping)}ボーン")
        else:
            self.report({'WARNING'},
                        f"VRMメタデータなし — パターン推測でボーン検出: {len(vrm_mapping)}ボーン "
                        f"(.blendファイルモード)")

        # Validate minimum required bones for Source Engine playermodel
        required_bones = {"hips", "spine", "head"}
        found_required = required_bones.intersection(vrm_mapping.keys())
        missing_required = required_bones - found_required
        if missing_required:
            self.report({'WARNING'},
                        f"一部の必須ボーンが未検出: {', '.join(missing_required)} "
                        f"— 変換結果に問題が出る可能性があります")

        # Store original mode
        original_mode = context.mode
        original_active = context.view_layer.objects.active

        # Ensure we're in object mode first
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Set armature as active
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = armature
        armature.select_set(True)

        # Collect mesh objects for vertex group operations
        mesh_objects = [obj for obj in context.scene.objects
                        if obj.type == 'MESH' and obj.parent == armature]

        # Step 1: ThumbMetacarpal handling
        # (Metacarpal is anatomically part of the palm, not the thumb)
        finger_mode = context.scene.vrm2gmod.finger_mode
        hand_bones = {
            "leftThumbMetacarpal": ("leftHand", "leftThumbProximal"),
            "rightThumbMetacarpal": ("rightHand", "rightThumbProximal"),
        }
        for merge_src, (hand_dst, finger_dst) in hand_bones.items():
            src_blender = vrm_mapping.get(merge_src, "")
            hand_blender = vrm_mapping.get(hand_dst, "")
            finger_blender = vrm_mapping.get(finger_dst, "")
            if src_blender and hand_blender:
                if finger_mode == 'DETAILED' and finger_blender:
                    # DETAILED: distance-based split between Hand and Finger0
                    for mesh_obj in mesh_objects:
                        split_vertex_group_by_distance(
                            mesh_obj, armature,
                            src_blender, hand_blender, finger_blender)
                    self.report({'INFO'},
                                f"ウェイト距離分配: {src_blender} → "
                                f"{hand_blender} / {finger_blender}")
                else:
                    # SIMPLE/FROZEN: merge ALL metacarpal weight into Hand
                    # Avoids thumb stretching from distance-based split
                    for mesh_obj in mesh_objects:
                        merge_vertex_groups(mesh_obj, src_blender, hand_blender)
                    self.report({'INFO'},
                                f"ウェイト統合: {src_blender} → {hand_blender}")

        # Step 2: Switch to edit mode for bone operations
        bpy.ops.object.mode_set(mode='EDIT')

        # Step 2.5: Restore absorbed root bone (FBX import quirk)
        # When FBX is imported, the root bone (e.g. "Hips") is often absorbed
        # into the armature object, leaving Spine/Legs as orphan roots.
        absorbed_hips = vrm_mapping.get("hips") == "__armature_as_hips__"
        if absorbed_hips:
            from mathutils import Vector
            hips_bone = armature.data.edit_bones.new("__restored_hips__")
            hips_bone.head = Vector((0, 0, 0))
            # Find first spine-like root for tail position
            spine_root = None
            for b in armature.data.edit_bones:
                if b.parent is None and "spine" in b.name.lower():
                    spine_root = b
                    break
            if not spine_root:
                for b in armature.data.edit_bones:
                    if b.parent is None:
                        spine_root = b
                        break
            hips_bone.tail = spine_root.head if spine_root else Vector((0, 0, 0.1))
            # Parent all orphan roots to restored hips
            for b in list(armature.data.edit_bones):
                if b.parent is None and b != hips_bone:
                    b.parent = hips_bone
                    b.use_connect = False
            vrm_mapping["hips"] = "__restored_hips__"
            self.report({'INFO'}, "FBXルートボーン復元: Hipsボーンを自動挿入")

        # Step 3: Remove spring bone / collider bones
        bones_to_remove = []
        for bone in armature.data.edit_bones:
            name_lower = bone.name.lower()
            if any(name_lower.startswith(prefix) or prefix in name_lower
                   for prefix in SPRING_BONE_PREFIXES):
                bones_to_remove.append(bone.name)
            # Also remove VRM-specific utility bones
            elif name_lower.startswith("j_sec_") or name_lower.startswith("j_adj_"):
                bones_to_remove.append(bone.name)

        for bone_name in bones_to_remove:
            bone = armature.data.edit_bones.get(bone_name)
            if bone:
                armature.data.edit_bones.remove(bone)

        if bones_to_remove:
            self.report({'INFO'}, f"スプリングボーン削除: {len(bones_to_remove)}本")

        # Remove merged metacarpal bones from armature
        for merge_src in VRM_MERGE_BONES:
            src_blender = vrm_mapping.get(merge_src, "")
            if src_blender:
                bone = armature.data.edit_bones.get(src_blender)
                if bone:
                    # Re-parent children to the bone's parent before removing
                    for child in bone.children:
                        child.parent = bone.parent
                    armature.data.edit_bones.remove(bone)

        # Step 4: Handle missing required bones (spine hierarchy + Spine4)
        self._ensure_spine_hierarchy(armature, vrm_mapping)

        # Step 5: Rename bones to ValveBiped names
        # Note: Blender automatically renames vertex groups on all child meshes
        # when an edit bone is renamed. No manual VG rename needed.
        rename_count = 0
        for vrm_name, valve_name in VRM_TO_VALVEBIPED.items():
            blender_name = vrm_mapping.get(vrm_name, "")
            if not blender_name:
                continue

            bone = armature.data.edit_bones.get(blender_name)
            if bone and bone.name != valve_name:
                bone.name = valve_name
                rename_count += 1

        self.report({'INFO'}, f"ボーンリネーム: {rename_count}本")

        # Step 6: Ensure correct parent-child relationships
        self._fix_hierarchy(armature)

        # Step 6.5: Rescue missing limb bones
        # When pattern detection misses arm/leg bones (.blend mode),
        # find unrenamed bones in the correct hierarchy position and
        # rename them before Step 7 removes all non-ValveBiped bones.
        rescued = self._rescue_missing_limb_bones(armature)
        if rescued > 0:
            self.report({'INFO'},
                        f"欠損ボーン復元: {rescued}本（パターン検出補完）")

        # Note: Bone orientations are NOT modified here. The SMD exporter
        # uses the "hybrid" approach: model positions + male_07 rotations.
        # This avoids the fundamental VRM↔ValveBiped axis mismatch.

        # Step 7: Remove VRM-specific bones and transfer weights
        # Must do this AFTER renaming so we can identify ValveBiped bones
        bpy.ops.object.mode_set(mode='OBJECT')
        vrm_removed = self._remove_vrm_specific_bones(armature, mesh_objects)
        if vrm_removed > 0:
            self.report({'INFO'}, f"VRM固有ボーン削除: {vrm_removed}本（ウェイト移譲済み）")

        # Step 8: Cleanup orphaned vertex groups
        # Spring bone removal (Step 3) deletes bones without transferring weights,
        # leaving orphaned vertex groups. Merge them into the nearest ValveBiped bone.
        orphan_count = self._cleanup_orphaned_vertex_groups(armature, mesh_objects)
        if orphan_count > 0:
            self.report({'INFO'}, f"孤立頂点グループ統合: {orphan_count}個→Head1等へ")

        # Step 9: Generate weights for inserted bones (Spine2, Spine4)
        # These bones were inserted during spine hierarchy setup but have no
        # vertex weights from the original VRM model.
        self._generate_spine_weights(armature, mesh_objects)

        # Step 9.5: Finger weight simplification
        finger_mode = context.scene.vrm2gmod.finger_mode
        if finger_mode != 'DETAILED':
            finger_merges = simplify_finger_weights(mesh_objects, finger_mode)
            mode_label = "簡略（1関節）" if finger_mode == 'SIMPLE' else "固定（パー）"
            self.report({'INFO'},
                        f"指ウェイト{mode_label}: {finger_merges}グループ統合")

        # Step 10: Weight cleanup — limit to 3 influences, remove micro-weights,
        # normalize to sum 1.0
        for mesh_obj in mesh_objects:
            cleanup_vertex_weights(mesh_obj, max_influences=3, min_weight=0.01)
        self.report({'INFO'}, "ウェイトクリーンアップ完了（3ボーン制限・正規化）")

        # Restore original state
        context.view_layer.objects.active = original_active or armature

        self.report({'INFO'}, "ボーンリマップ完了")
        return {'FINISHED'}

    def _ensure_spine_hierarchy(self, armature, vrm_mapping):
        """Insert missing spine bones if VRM doesn't have chest/upperChest/neck.

        Also inserts Spine4 between Spine2(upperChest) and Neck1/Clavicles.
        Spine4 is critical for HL2 animation compatibility.
        """
        edit_bones = armature.data.edit_bones

        # Get current bone names and verify they actually exist in edit mode
        def _get_valid(key):
            name = vrm_mapping.get(key, "")
            if name and edit_bones.get(name):
                return name
            return ""

        spine_blender = _get_valid("spine")
        chest_blender = _get_valid("chest")
        upper_chest_blender = _get_valid("upperChest")
        neck_blender = _get_valid("neck")
        head_blender = _get_valid("head")

        # Determine the chain: spine → chest → upperChest → neck → head
        # Fill in missing bones

        if not chest_blender and spine_blender:
            next_bone_name = upper_chest_blender or neck_blender or head_blender
            if next_bone_name:
                spine_bone = edit_bones.get(spine_blender)
                next_bone = edit_bones.get(next_bone_name)
                if spine_bone and next_bone:
                    new_bone = insert_bone_between(
                        armature, "__temp_chest__", spine_blender, next_bone_name
                    )
                    if new_bone:
                        vrm_mapping["chest"] = "__temp_chest__"
                        chest_blender = "__temp_chest__"

        if not upper_chest_blender and chest_blender:
            next_bone_name = neck_blender or head_blender
            if next_bone_name:
                new_bone = insert_bone_between(
                    armature, "__temp_upper_chest__", chest_blender, next_bone_name
                )
                if new_bone:
                    vrm_mapping["upperChest"] = "__temp_upper_chest__"
                    upper_chest_blender = "__temp_upper_chest__"

        if not neck_blender and head_blender:
            parent_name = upper_chest_blender or chest_blender or spine_blender
            if parent_name:
                new_bone = insert_bone_between(
                    armature, "__temp_neck__", parent_name, head_blender
                )
                if new_bone:
                    vrm_mapping["neck"] = "__temp_neck__"
                    neck_blender = "__temp_neck__"

        # Ensure shoulder bones exist
        for side, shoulder_key, upper_arm_key in [
            ("L", "leftShoulder", "leftUpperArm"),
            ("R", "rightShoulder", "rightUpperArm"),
        ]:
            shoulder_blender = vrm_mapping.get(shoulder_key, "")
            upper_arm_blender = vrm_mapping.get(upper_arm_key, "")
            if not shoulder_blender and upper_arm_blender:
                parent_name = upper_chest_blender or chest_blender or spine_blender
                if parent_name:
                    temp_name = f"__temp_clavicle_{side}__"
                    new_bone = insert_bone_between(
                        armature, temp_name, parent_name, upper_arm_blender
                    )
                    if new_bone:
                        vrm_mapping[shoulder_key] = temp_name

        # ★ Insert Spine4 between upperChest(Spine2) and neck/clavicles
        # VRM has no equivalent bone; Spine4 is needed for HL2 animation system
        self._insert_spine4(armature, vrm_mapping)

    def _insert_spine4(self, armature, vrm_mapping):
        """Insert Spine4 bone between Spine2(upperChest) and Neck1/Clavicles.

        Spine4 is the primary parent for the upper body in HL2 animations.
        Neck1 and both Clavicles are re-parented from Spine2 to Spine4.
        Spine2's vertex weights are split 50/50 with Spine4.
        """
        edit_bones = armature.data.edit_bones

        # Find the upperChest bone (will become Spine2 after rename)
        upper_chest_name = vrm_mapping.get("upperChest", "")
        neck_name = vrm_mapping.get("neck", "")

        if not upper_chest_name:
            return

        spine2_bone = edit_bones.get(upper_chest_name)
        if not spine2_bone:
            return

        # Find the next bone in chain (neck preferred, or first child)
        neck_bone = edit_bones.get(neck_name) if neck_name else None

        if not neck_bone:
            # Try to find any child that would be neck/clavicle
            for child in spine2_bone.children:
                neck_bone = child
                break

        if not neck_bone:
            return

        # Create Spine4 bone directly with ValveBiped name
        # (won't conflict with VRM rename step since it's not a VRM bone)
        spine4_name = "ValveBiped.Bip01_Spine4"
        spine4_bone = edit_bones.new(spine4_name)

        # Position Spine4 between Spine2 and Neck
        # Use 70% along the way from Spine2 to Neck (matching HL2 standard
        # proportions where Spine4 is closer to Neck than to Spine2)
        spine4_bone.head = spine2_bone.head + (neck_bone.head - spine2_bone.head) * 0.7
        spine4_bone.tail = neck_bone.head
        spine4_bone.parent = spine2_bone
        spine4_bone.use_connect = False

        # Re-parent all Spine2 children to Spine4
        # (Neck1, L_Clavicle, R_Clavicle, etc.)
        children_to_reparent = list(spine2_bone.children)
        for child in children_to_reparent:
            if child != spine4_bone:  # Don't reparent Spine4 to itself
                child.parent = spine4_bone
                child.use_connect = False

        # Vertex weight splitting will be done after switching to Object mode
        self._spine4_weight_source = upper_chest_name

    def _rescue_missing_limb_bones(self, armature):
        """Find and rename limb bones missed by pattern detection.

        When converting from .blend files (no VRM metadata), the pattern
        guesser may miss intermediate bones (UpperArm, Forearm, Thigh,
        Calf).  These bones keep their original names and would be deleted
        in Step 7.  This method finds them by their position in the
        hierarchy (between two successfully renamed ValveBiped bones) and
        renames them before removal.

        Must be called in Edit mode after Step 5 (rename) and Step 6
        (fix_hierarchy).

        Returns the number of rescued bones.
        """
        edit_bones = armature.data.edit_bones

        # Process in chain order: parent bone first, then child.
        # This ensures a rescued UpperArm is found before Forearm lookup.
        chains = [
            # (missing_bone_name, expected_parent_name)
            ("ValveBiped.Bip01_R_UpperArm", "ValveBiped.Bip01_R_Clavicle"),
            ("ValveBiped.Bip01_R_Forearm",  "ValveBiped.Bip01_R_UpperArm"),
            ("ValveBiped.Bip01_L_UpperArm", "ValveBiped.Bip01_L_Clavicle"),
            ("ValveBiped.Bip01_L_Forearm",  "ValveBiped.Bip01_L_UpperArm"),
            ("ValveBiped.Bip01_R_Thigh",    "ValveBiped.Bip01_Pelvis"),
            ("ValveBiped.Bip01_R_Calf",     "ValveBiped.Bip01_R_Thigh"),
            ("ValveBiped.Bip01_L_Thigh",    "ValveBiped.Bip01_Pelvis"),
            ("ValveBiped.Bip01_L_Calf",     "ValveBiped.Bip01_L_Thigh"),
        ]

        # Terminus bone for each chain — used to disambiguate when
        # the parent has multiple non-ValveBiped children (e.g. Pelvis).
        chain_terminus = {
            "ValveBiped.Bip01_R_UpperArm": "ValveBiped.Bip01_R_Hand",
            "ValveBiped.Bip01_R_Forearm":  "ValveBiped.Bip01_R_Hand",
            "ValveBiped.Bip01_L_UpperArm": "ValveBiped.Bip01_L_Hand",
            "ValveBiped.Bip01_L_Forearm":  "ValveBiped.Bip01_L_Hand",
            "ValveBiped.Bip01_R_Thigh":    "ValveBiped.Bip01_R_Foot",
            "ValveBiped.Bip01_R_Calf":     "ValveBiped.Bip01_R_Foot",
            "ValveBiped.Bip01_L_Thigh":    "ValveBiped.Bip01_L_Foot",
            "ValveBiped.Bip01_L_Calf":     "ValveBiped.Bip01_L_Foot",
        }

        rescued = 0
        for bone_name, parent_name in chains:
            if edit_bones.get(bone_name):
                continue  # Already exists — no rescue needed

            parent = edit_bones.get(parent_name)
            if not parent:
                continue  # Parent doesn't exist either

            terminus = chain_terminus.get(bone_name, "")
            candidate = self._find_chain_candidate(parent, terminus)

            if candidate:
                candidate.name = bone_name
                rescued += 1

        return rescued

    def _find_chain_candidate(self, parent, terminus_name):
        """Find the best non-ValveBiped child of *parent* that leads
        toward *terminus_name*.

        Returns the edit bone to rename, or None.
        """
        candidates = [c for c in parent.children
                      if not c.name.startswith("ValveBiped.")]

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        # Multiple candidates — pick the one whose subtree contains
        # the expected terminus bone.
        if terminus_name:
            for c in candidates:
                if self._subtree_contains(c, terminus_name):
                    return c

        # Fallback: first non-ValveBiped child
        return candidates[0]

    @staticmethod
    def _subtree_contains(bone, name):
        """Recursively check if *name* exists in *bone*'s subtree."""
        for child in bone.children:
            if child.name == name:
                return True
            if VRM2GMOD_OT_BoneRemap._subtree_contains(child, name):
                return True
        return False

    def _remove_vrm_specific_bones(self, armature, mesh_objects):
        """Remove VRM-specific bones (ponite, ear, tail, etc.) and transfer
        their vertex weights to the nearest ValveBiped bone.

        Must be called in Object mode after renaming is complete.
        """
        # Identify bones to remove
        valvebiped_bones = set(VALVEBIPED_HIERARCHY.keys())
        bones_to_remove = []

        for bone in armature.data.bones:
            if bone.name in valvebiped_bones:
                continue
            # Check if it's a VRM-specific bone by prefix
            name_lower = bone.name.lower()
            is_vrm_specific = any(
                name_lower.startswith(prefix.lower())
                for prefix in VRM_EXCLUDE_PREFIXES
            )
            # Also catch any non-ValveBiped bone
            if is_vrm_specific or not bone.name.startswith("ValveBiped."):
                bones_to_remove.append(bone.name)

        if not bones_to_remove:
            return 0

        # For each bone to remove, transfer its weights to the nearest parent
        # that IS a ValveBiped bone
        for bone_name in bones_to_remove:
            target_bone = self._find_nearest_valvebiped_parent(armature, bone_name)
            if target_bone:
                for mesh_obj in mesh_objects:
                    merge_vertex_groups(mesh_obj, bone_name, target_bone)

        # Also split Spine2 weights with Spine4 if Spine4 was inserted
        spine4_source = getattr(self, '_spine4_weight_source', None)
        if spine4_source:
            spine4_name = "ValveBiped.Bip01_Spine4"
            spine2_name = "ValveBiped.Bip01_Spine2"
            for mesh_obj in mesh_objects:
                self._split_weights(mesh_obj, spine2_name, spine4_name, ratio=0.5)

        # Remove the bones in edit mode
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')

        removed_count = 0
        for bone_name in bones_to_remove:
            bone = armature.data.edit_bones.get(bone_name)
            if bone:
                # Re-parent children to parent before removing
                for child in list(bone.children):
                    child.parent = bone.parent
                armature.data.edit_bones.remove(bone)
                removed_count += 1

        bpy.ops.object.mode_set(mode='OBJECT')
        return removed_count

    def _find_nearest_valvebiped_parent(self, armature, bone_name):
        """Walk up the bone hierarchy to find the nearest ValveBiped parent bone."""
        valvebiped_bones = set(VALVEBIPED_HIERARCHY.keys())
        bone = armature.data.bones.get(bone_name)
        if not bone:
            return "ValveBiped.Bip01_Head1"  # fallback

        current = bone.parent
        while current:
            if current.name in valvebiped_bones:
                return current.name
            current = current.parent

        return "ValveBiped.Bip01_Pelvis"  # ultimate fallback

    def _split_weights(self, mesh_obj, source_name, target_name, ratio=0.5):
        """Split vertex weights from source bone to target bone.

        Vertices weighted to source_name get `ratio` of their weight
        transferred to target_name.
        """
        source_vg = mesh_obj.vertex_groups.get(source_name)
        if not source_vg:
            return

        target_vg = mesh_obj.vertex_groups.get(target_name)
        if not target_vg:
            target_vg = mesh_obj.vertex_groups.new(name=target_name)

        for vert in mesh_obj.data.vertices:
            try:
                source_weight = source_vg.weight(vert.index)
            except RuntimeError:
                continue

            if source_weight > 0.001:
                split_amount = source_weight * ratio
                # Reduce source weight
                source_vg.add([vert.index], source_weight - split_amount, 'REPLACE')
                # Add to target
                try:
                    existing = target_vg.weight(vert.index)
                    target_vg.add([vert.index], existing + split_amount, 'REPLACE')
                except RuntimeError:
                    target_vg.add([vert.index], split_amount, 'REPLACE')

    def _cleanup_orphaned_vertex_groups(self, armature, mesh_objects):
        """Merge orphaned vertex groups into the nearest ValveBiped bone.

        After spring bone removal (which deletes bones without weight transfer)
        and VRM-specific bone removal, some vertex groups may be left without
        matching bones. These cause vertices to fall back to Pelvis (bone 0)
        during SMD export, producing severe mesh distortion.

        Heuristic for target bone:
          - Names containing 'hair', 'head', 'eye', 'ear', 'face' → Head1
          - Names containing 'tail' → Pelvis
          - Default → Head1 (most orphaned VRM bones are head-related)
        """
        bone_names = {bone.name for bone in armature.data.bones}
        merged_count = 0

        for mesh_obj in mesh_objects:
            orphaned = []
            for vg in mesh_obj.vertex_groups:
                if vg.name not in bone_names:
                    orphaned.append(vg.name)

            for vg_name in orphaned:
                name_lower = vg_name.lower()

                # Determine target ValveBiped bone
                if any(kw in name_lower for kw in ('tail', 'skirt', 'cloth')):
                    target = "ValveBiped.Bip01_Pelvis"
                elif any(kw in name_lower for kw in ('leg', 'knee', 'ankle', 'foot')):
                    target = "ValveBiped.Bip01_Pelvis"
                elif any(kw in name_lower for kw in ('arm', 'elbow', 'wrist')):
                    target = "ValveBiped.Bip01_Spine4"
                else:
                    # Default: head (hair, head_L/R, eye, ear, face, etc.)
                    target = "ValveBiped.Bip01_Head1"

                merge_vertex_groups(mesh_obj, vg_name, target)
                merged_count += 1

        return merged_count

    def _generate_spine_weights(self, armature, mesh_objects):
        """Generate vertex weights for Spine2 and Spine4 via spatial interpolation.

        These bones were inserted during spine hierarchy setup and have no
        vertex weights from the original VRM model. We create smooth weight
        transitions by spatially distributing weights from neighboring bones.

        Strategy:
          - Spine2 gets weight from Spine1 vertices above Spine2's head position
          - Spine4 gets weight from Spine2 vertices above Spine4's head position
          - Weight gradients are based on vertical distance for smooth transitions
        """
        from mathutils import Vector

        # Get bone positions in armature space
        spine1 = armature.data.bones.get("ValveBiped.Bip01_Spine1")
        spine2 = armature.data.bones.get("ValveBiped.Bip01_Spine2")
        spine4 = armature.data.bones.get("ValveBiped.Bip01_Spine4")
        neck1 = armature.data.bones.get("ValveBiped.Bip01_Neck1")

        if not all([spine1, spine2, spine4, neck1]):
            return

        # Bone head positions in armature world space
        arm_mat = armature.matrix_world
        spine1_z = (arm_mat @ spine1.head_local).z
        spine2_z = (arm_mat @ spine2.head_local).z
        spine4_z = (arm_mat @ spine4.head_local).z
        neck1_z = (arm_mat @ neck1.head_local).z

        for mesh_obj in mesh_objects:
            mesh_to_world = mesh_obj.matrix_world

            # Ensure vertex groups exist
            spine2_vg = mesh_obj.vertex_groups.get("ValveBiped.Bip01_Spine2")
            if not spine2_vg:
                spine2_vg = mesh_obj.vertex_groups.new(name="ValveBiped.Bip01_Spine2")

            spine4_vg = mesh_obj.vertex_groups.get("ValveBiped.Bip01_Spine4")
            if not spine4_vg:
                spine4_vg = mesh_obj.vertex_groups.new(name="ValveBiped.Bip01_Spine4")

            spine1_vg = mesh_obj.vertex_groups.get("ValveBiped.Bip01_Spine1")
            neck1_vg = mesh_obj.vertex_groups.get("ValveBiped.Bip01_Neck1")

            if not spine1_vg:
                continue

            # For each vertex, redistribute weights in the spine region
            for vert in mesh_obj.data.vertices:
                vert_z = (mesh_to_world @ vert.co).z

                # Only process vertices in the spine region
                if vert_z < spine1_z or vert_z > neck1_z:
                    continue

                # Get current Spine1 weight
                spine1_w = 0.0
                try:
                    spine1_w = spine1_vg.weight(vert.index)
                except RuntimeError:
                    pass

                # Get current Neck1 weight (if any)
                neck1_w = 0.0
                if neck1_vg:
                    try:
                        neck1_w = neck1_vg.weight(vert.index)
                    except RuntimeError:
                        pass

                # Only redistribute if this vertex has torso weight
                torso_weight = spine1_w + neck1_w
                if torso_weight < 0.01:
                    continue

                # Compute blend factor based on vertical position
                # spine1_z → spine2_z → spine4_z → neck1_z
                total_range = neck1_z - spine1_z
                if total_range < 0.001:
                    continue

                t = (vert_z - spine1_z) / total_range  # 0..1 through the region

                # Weight distribution:
                # t=0.0 (spine1_z): 100% Spine1
                # t=0.3 (spine2_z): ~50% Spine1, ~50% Spine2
                # t=0.7 (spine4_z): ~50% Spine2, ~50% Spine4
                # t=1.0 (neck1_z): 100% Neck1
                spine2_t = (spine2_z - spine1_z) / total_range
                spine4_t = (spine4_z - spine1_z) / total_range

                if t <= spine2_t:
                    # Spine1 → Spine2 transition
                    blend = t / spine2_t if spine2_t > 0 else 0
                    new_spine1 = spine1_w * (1.0 - blend * 0.5)
                    new_spine2 = spine1_w * (blend * 0.5)
                    new_spine4 = 0.0
                elif t <= spine4_t:
                    # Spine2 → Spine4 transition
                    blend = (t - spine2_t) / (spine4_t - spine2_t) if (spine4_t - spine2_t) > 0 else 0
                    new_spine1 = spine1_w * 0.5 * (1.0 - blend)
                    new_spine2 = spine1_w * 0.5
                    new_spine4 = spine1_w * 0.5 * blend
                else:
                    # Spine4 → Neck1 transition
                    blend = (t - spine4_t) / (1.0 - spine4_t) if (1.0 - spine4_t) > 0 else 1
                    new_spine1 = 0.0
                    new_spine2 = spine1_w * 0.5 * (1.0 - blend)
                    new_spine4 = spine1_w * 0.5
                    # Neck1 keeps its existing weight

                # Apply new weights (only modify Spine1's contribution)
                if new_spine1 > 0.001:
                    spine1_vg.add([vert.index], new_spine1, 'REPLACE')
                elif spine1_w > 0:
                    spine1_vg.add([vert.index], 0.0, 'REPLACE')

                if new_spine2 > 0.001:
                    spine2_vg.add([vert.index], new_spine2, 'REPLACE')

                if new_spine4 > 0.001:
                    spine4_vg.add([vert.index], new_spine4, 'REPLACE')

    def _fix_hierarchy(self, armature):
        """Fix parent-child relationships to match ValveBiped hierarchy.

        Only fixes bones that actually exist in the armature.
        Includes Spine4 re-parenting (Neck1/Clavicles → Spine4).
        """
        edit_bones = armature.data.edit_bones

        # Build a map including temp names → final names
        # At this point some bones may still have temp names
        for bone_name, expected_parent in VALVEBIPED_HIERARCHY.items():
            bone = edit_bones.get(bone_name)
            if not bone:
                continue

            if not expected_parent:
                # Root bone, should have no parent (or we leave it)
                continue

            parent = edit_bones.get(expected_parent)
            if parent and bone.parent != parent:
                bone.parent = parent
                bone.use_connect = False


classes = (VRM2GMOD_OT_BoneRemap,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
