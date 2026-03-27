"""Bone manipulation utilities for VRM → ValveBiped conversion."""

import bpy
from mathutils import Vector
from typing import Optional


def find_armature(context: bpy.types.Context) -> Optional[bpy.types.Object]:
    """Find the armature object in the scene. Prefers the active object if it's an armature."""
    if context.active_object and context.active_object.type == 'ARMATURE':
        return context.active_object
    for obj in context.scene.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None


def get_vrm_humanoid_mapping(armature: bpy.types.Object) -> dict[str, str]:
    """Extract VRM humanoid bone mapping from the armature's custom properties.

    VRM Addon for Blender stores humanoid bone mapping as PropertyGroup
    attributes on armature.data.vrm_addon_extension. This function reads
    them and returns a dict of vrm_bone_name → actual_blender_bone_name.

    For .blend files without VRM metadata (or with stale/partial VRM data),
    pattern guessing is used to supplement the mapping.
    """
    existing_bones = {bone.name for bone in armature.data.bones}

    # Step 1: Try VRM metadata first
    vrm_mapping = {}
    ext = getattr(armature.data, 'vrm_addon_extension', None)
    if ext is not None:
        vrm_mapping = _try_vrm1_mapping(ext) or _try_vrm0_mapping(ext) or {}
        # Remove entries pointing to bones that no longer exist in the armature
        # (common when .blend was saved after bone renaming)
        stale = [k for k, v in vrm_mapping.items() if v not in existing_bones]
        for k in stale:
            del vrm_mapping[k]

    # Step 2: Always supplement with pattern guessing for unmapped bones
    guessed = _guess_vrm_bones(armature)
    already_mapped_bones = set(vrm_mapping.values())
    for key, value in guessed.items():
        # Only add if this VRM bone isn't already mapped AND
        # the Blender bone isn't already used by another mapping
        if key not in vrm_mapping and value not in already_mapped_bones:
            vrm_mapping[key] = value
            already_mapped_bones.add(value)

    return vrm_mapping


def _try_vrm1_mapping(ext) -> dict[str, str]:
    """Try to extract bone mapping from VRM 1.0 PropertyGroup."""
    mapping = {}

    try:
        vrm1 = getattr(ext, 'vrm1', None)
        if not vrm1:
            return {}

        humanoid = getattr(vrm1, 'humanoid', None)
        if not humanoid:
            return {}

        human_bones = getattr(humanoid, 'human_bones', None)
        if not human_bones:
            return {}

        # VRM 1.0: each bone is an attribute of human_bones PropertyGroup
        # e.g., human_bones.hips.node.bone_name
        vrm1_bone_names = [
            "hips", "spine", "chest", "upper_chest", "neck", "head",
            "left_upper_leg", "left_lower_leg", "left_foot", "left_toes",
            "right_upper_leg", "right_lower_leg", "right_foot", "right_toes",
            "left_shoulder", "left_upper_arm", "left_lower_arm", "left_hand",
            "right_shoulder", "right_upper_arm", "right_lower_arm", "right_hand",
            "left_thumb_metacarpal", "left_thumb_proximal", "left_thumb_distal",
            "left_index_proximal", "left_index_intermediate", "left_index_distal",
            "left_middle_proximal", "left_middle_intermediate", "left_middle_distal",
            "left_ring_proximal", "left_ring_intermediate", "left_ring_distal",
            "left_little_proximal", "left_little_intermediate", "left_little_distal",
            "right_thumb_metacarpal", "right_thumb_proximal", "right_thumb_distal",
            "right_index_proximal", "right_index_intermediate", "right_index_distal",
            "right_middle_proximal", "right_middle_intermediate", "right_middle_distal",
            "right_ring_proximal", "right_ring_intermediate", "right_ring_distal",
            "right_little_proximal", "right_little_intermediate", "right_little_distal",
            "left_eye", "right_eye", "jaw",
        ]

        # VRM Addon uses snake_case internally but our mapping uses camelCase
        snake_to_camel = {
            "upper_chest": "upperChest",
            "left_upper_leg": "leftUpperLeg",
            "left_lower_leg": "leftLowerLeg",
            "left_foot": "leftFoot",
            "left_toes": "leftToes",
            "right_upper_leg": "rightUpperLeg",
            "right_lower_leg": "rightLowerLeg",
            "right_foot": "rightFoot",
            "right_toes": "rightToes",
            "left_shoulder": "leftShoulder",
            "left_upper_arm": "leftUpperArm",
            "left_lower_arm": "leftLowerArm",
            "left_hand": "leftHand",
            "right_shoulder": "rightShoulder",
            "right_upper_arm": "rightUpperArm",
            "right_lower_arm": "rightLowerArm",
            "right_hand": "rightHand",
            "left_thumb_metacarpal": "leftThumbMetacarpal",
            "left_thumb_proximal": "leftThumbProximal",
            "left_thumb_distal": "leftThumbDistal",
            "left_index_proximal": "leftIndexProximal",
            "left_index_intermediate": "leftIndexIntermediate",
            "left_index_distal": "leftIndexDistal",
            "left_middle_proximal": "leftMiddleProximal",
            "left_middle_intermediate": "leftMiddleIntermediate",
            "left_middle_distal": "leftMiddleDistal",
            "left_ring_proximal": "leftRingProximal",
            "left_ring_intermediate": "leftRingIntermediate",
            "left_ring_distal": "leftRingDistal",
            "left_little_proximal": "leftLittleProximal",
            "left_little_intermediate": "leftLittleIntermediate",
            "left_little_distal": "leftLittleDistal",
            "right_thumb_metacarpal": "rightThumbMetacarpal",
            "right_thumb_proximal": "rightThumbProximal",
            "right_thumb_distal": "rightThumbDistal",
            "right_index_proximal": "rightIndexProximal",
            "right_index_intermediate": "rightIndexIntermediate",
            "right_index_distal": "rightIndexDistal",
            "right_middle_proximal": "rightMiddleProximal",
            "right_middle_intermediate": "rightMiddleIntermediate",
            "right_middle_distal": "rightMiddleDistal",
            "right_ring_proximal": "rightRingProximal",
            "right_ring_intermediate": "rightRingIntermediate",
            "right_ring_distal": "rightRingDistal",
            "right_little_proximal": "rightLittleProximal",
            "right_little_intermediate": "rightLittleIntermediate",
            "right_little_distal": "rightLittleDistal",
            "left_eye": "leftEye",
            "right_eye": "rightEye",
        }

        for snake_name in vrm1_bone_names:
            bone_prop = getattr(human_bones, snake_name, None)
            if bone_prop is None:
                continue

            node = getattr(bone_prop, 'node', None)
            if node is None:
                continue

            bone_name = getattr(node, 'bone_name', '')
            if not bone_name:
                # Try 'value' attribute (some versions)
                bone_name = getattr(node, 'value', '')

            if bone_name:
                camel_name = snake_to_camel.get(snake_name, snake_name)
                mapping[camel_name] = bone_name

    except (AttributeError, TypeError) as e:
        print(f"[VRM2Gmod] VRM 1.0 mapping extraction error: {e}")

    return mapping


def _try_vrm0_mapping(ext) -> dict[str, str]:
    """Try to extract bone mapping from VRM 0.x PropertyGroup."""
    mapping = {}

    try:
        vrm0 = getattr(ext, 'vrm0', None)
        if not vrm0:
            return {}

        humanoid = getattr(vrm0, 'humanoid', None)
        if not humanoid:
            return {}

        human_bones = getattr(humanoid, 'human_bones', None)
        if not human_bones:
            return {}

        # VRM 0.x: human_bones is a collection (list-like)
        for bone_entry in human_bones:
            vrm_name = getattr(bone_entry, 'bone', '')
            node = getattr(bone_entry, 'node', None)
            if node:
                bone_name = getattr(node, 'bone_name', '')
                if not bone_name:
                    bone_name = getattr(node, 'value', '')
            else:
                bone_name = ''

            if vrm_name and bone_name:
                mapping[vrm_name] = bone_name

    except (AttributeError, TypeError) as e:
        print(f"[VRM2Gmod] VRM 0.x mapping extraction error: {e}")

    return mapping


def _guess_vrm_bones(armature: bpy.types.Object) -> dict[str, str]:
    """Guess humanoid bone names from common naming patterns.

    Supports:
    - VRoid Studio (J_Bip_C_Hips, J_Bip_L_UpperArm, ...)
    - Unity underscore L/R (hip, shoulder_L, upper_arm_L, ...)
    - Mixamo (Hips, LeftArm, LeftForeArm, ...)
    - Unity Humanoid / Cats Blender Plugin (Hips, Left arm, Left elbow, ...)
    - Japanese bone names (上半身, 左腕, ...)
    - Generic / FBX humanoid (hips, spine, chest, ...)
    """
    bones = armature.data.bones

    # All pattern sets to try, in priority order
    all_pattern_sets = [
        _vroid_patterns(),
        _underscore_lr_patterns(),
        _unity_mecanim_patterns(),
        _unity_cats_patterns(),
        _mixamo_patterns(),
        _japanese_patterns(),
        _generic_patterns(),
    ]

    best_mapping = {}
    best_score = 0

    for patterns in all_pattern_sets:
        # Build case-insensitive lookup
        lower_patterns = {k.lower(): (k, v) for k, v in patterns.items()}

        mapping = {}
        for bone in bones:
            name = bone.name
            # Exact match first
            if name in patterns:
                mapping[patterns[name]] = name
            # Case-insensitive match
            elif name.lower() in lower_patterns:
                _, vrm_name = lower_patterns[name.lower()]
                mapping[vrm_name] = name
            else:
                # Try stripping Blender auto-numbering suffixes (.001, .002, ...)
                # e.g. "hand_L.001" → try matching "hand_L"
                stripped = _strip_blender_suffix(name)
                if stripped != name:
                    if stripped in patterns:
                        vrm_name = patterns[stripped]
                        if vrm_name not in mapping:
                            mapping[vrm_name] = name
                    elif stripped.lower() in lower_patterns:
                        _, vrm_name = lower_patterns[stripped.lower()]
                        if vrm_name not in mapping:
                            mapping[vrm_name] = name

        # FBX root bone absorption fix:
        # When FBX is imported, the root bone (e.g. "Hips") can be absorbed
        # into the armature object, leaving Spine/LeftUpperLeg/RightUpperLeg
        # as orphan roots. Detect this and treat armature name as hips.
        if "hips" not in mapping:
            arm_name_lower = armature.name.lower()
            _COMMON_ROOT_NAMES = {
                "hips", "root", "pelvis", "hip", "armature_hips",
            }
            if arm_name_lower in _COMMON_ROOT_NAMES:
                root_bones = [b for b in bones if b.parent is None]
                child_names = {b.name.lower() for b in root_bones}
                has_spine_child = any("spine" in n for n in child_names)
                has_leg_child = any(
                    "leg" in n or "thigh" in n for n in child_names)
                if has_spine_child or has_leg_child:
                    mapping["hips"] = "__armature_as_hips__"

        # Validate: need at least some core bones
        has_hips = "hips" in mapping
        has_spine = "spine" in mapping
        has_head = "head" in mapping
        has_limbs = any(k in mapping for k in (
            "leftUpperArm", "rightUpperArm", "leftUpperLeg", "rightUpperLeg"))

        # Score this match (prefer more complete mappings)
        if has_hips and (has_spine or has_head):
            score = len(mapping) + (10 if has_limbs else 0)
            if score > best_score:
                best_mapping = mapping
                best_score = score

    return best_mapping


def _strip_blender_suffix(name: str) -> str:
    """Strip Blender auto-numbering suffix (.001, .002, ...) from a bone name."""
    import re
    return re.sub(r'\.\d{3}$', '', name)


def _vroid_patterns() -> dict[str, str]:
    """VRoid Studio bone naming: J_Bip_C_Hips, J_Bip_L_UpperArm, etc."""
    return {
        "J_Bip_C_Hips": "hips",
        "J_Bip_C_Spine": "spine",
        "J_Bip_C_Chest": "chest",
        "J_Bip_C_UpperChest": "upperChest",
        "J_Bip_C_Neck": "neck",
        "J_Bip_C_Head": "head",
        "J_Bip_L_Shoulder": "leftShoulder",
        "J_Bip_L_UpperArm": "leftUpperArm",
        "J_Bip_L_LowerArm": "leftLowerArm",
        "J_Bip_L_Hand": "leftHand",
        "J_Bip_R_Shoulder": "rightShoulder",
        "J_Bip_R_UpperArm": "rightUpperArm",
        "J_Bip_R_LowerArm": "rightLowerArm",
        "J_Bip_R_Hand": "rightHand",
        "J_Bip_L_UpperLeg": "leftUpperLeg",
        "J_Bip_L_LowerLeg": "leftLowerLeg",
        "J_Bip_L_Foot": "leftFoot",
        "J_Bip_L_ToeBase": "leftToes",
        "J_Bip_R_UpperLeg": "rightUpperLeg",
        "J_Bip_R_LowerLeg": "rightLowerLeg",
        "J_Bip_R_Foot": "rightFoot",
        "J_Bip_R_ToeBase": "rightToes",
        # Fingers
        "J_Bip_L_Thumb1": "leftThumbMetacarpal",
        "J_Bip_L_Thumb2": "leftThumbProximal",
        "J_Bip_L_Thumb3": "leftThumbDistal",
        "J_Bip_L_Index1": "leftIndexProximal",
        "J_Bip_L_Index2": "leftIndexIntermediate",
        "J_Bip_L_Index3": "leftIndexDistal",
        "J_Bip_L_Middle1": "leftMiddleProximal",
        "J_Bip_L_Middle2": "leftMiddleIntermediate",
        "J_Bip_L_Middle3": "leftMiddleDistal",
        "J_Bip_L_Ring1": "leftRingProximal",
        "J_Bip_L_Ring2": "leftRingIntermediate",
        "J_Bip_L_Ring3": "leftRingDistal",
        "J_Bip_L_Little1": "leftLittleProximal",
        "J_Bip_L_Little2": "leftLittleIntermediate",
        "J_Bip_L_Little3": "leftLittleDistal",
        "J_Bip_R_Thumb1": "rightThumbMetacarpal",
        "J_Bip_R_Thumb2": "rightThumbProximal",
        "J_Bip_R_Thumb3": "rightThumbDistal",
        "J_Bip_R_Index1": "rightIndexProximal",
        "J_Bip_R_Index2": "rightIndexIntermediate",
        "J_Bip_R_Index3": "rightIndexDistal",
        "J_Bip_R_Middle1": "rightMiddleProximal",
        "J_Bip_R_Middle2": "rightMiddleIntermediate",
        "J_Bip_R_Middle3": "rightMiddleDistal",
        "J_Bip_R_Ring1": "rightRingProximal",
        "J_Bip_R_Ring2": "rightRingIntermediate",
        "J_Bip_R_Ring3": "rightRingDistal",
        "J_Bip_R_Little1": "rightLittleProximal",
        "J_Bip_R_Little2": "rightLittleIntermediate",
        "J_Bip_R_Little3": "rightLittleDistal",
    }


def _underscore_lr_patterns() -> dict[str, str]:
    """Underscore _L/_R suffix naming (common in Unity exports for VRChat).

    Very common in VRChat .blend files where bone names use
    underscore + uppercase L/R: shoulder_L, upper_arm_L, etc.
    """
    return {
        # Core
        "hip": "hips",
        "hips": "hips",
        "spine": "spine",
        "chest": "chest",
        "upper_chest": "upperChest",
        "neck": "neck",
        "head": "head",
        # Left arm
        "shoulder_L": "leftShoulder",
        "upper_arm_L": "leftUpperArm",
        "arm_L": "leftLowerArm",
        "lower_arm_L": "leftLowerArm",
        "forearm_L": "leftLowerArm",
        "hand_L": "leftHand",
        "wrist_L": "leftHand",
        # Right arm
        "shoulder_R": "rightShoulder",
        "upper_arm_R": "rightUpperArm",
        "arm_R": "rightLowerArm",
        "lower_arm_R": "rightLowerArm",
        "forearm_R": "rightLowerArm",
        "hand_R": "rightHand",
        "wrist_R": "rightHand",
        # Left leg
        "upper_leg_L": "leftUpperLeg",
        "leg_L": "leftLowerLeg",
        "lower_leg_L": "leftLowerLeg",
        "knee_L": "leftLowerLeg",
        "foot_L": "leftFoot",
        "ankle_L": "leftFoot",
        "toe_L": "leftToes",
        # Right leg
        "upper_leg_R": "rightUpperLeg",
        "leg_R": "rightLowerLeg",
        "lower_leg_R": "rightLowerLeg",
        "knee_R": "rightLowerLeg",
        "foot_R": "rightFoot",
        "ankle_R": "rightFoot",
        "toe_R": "rightToes",
        # Left fingers
        "thumb_01_L": "leftThumbMetacarpal",
        "thumb_02_L": "leftThumbProximal",
        "thumb_03_L": "leftThumbDistal",
        "thumb_1_L": "leftThumbMetacarpal",
        "thumb_2_L": "leftThumbProximal",
        "thumb_3_L": "leftThumbDistal",
        "index_01_L": "leftIndexProximal",
        "index_02_L": "leftIndexIntermediate",
        "index_03_L": "leftIndexDistal",
        "index_1_L": "leftIndexProximal",
        "index_2_L": "leftIndexIntermediate",
        "index_3_L": "leftIndexDistal",
        "middle_01_L": "leftMiddleProximal",
        "middle_02_L": "leftMiddleIntermediate",
        "middle_03_L": "leftMiddleDistal",
        "middle_1_L": "leftMiddleProximal",
        "middle_2_L": "leftMiddleIntermediate",
        "middle_3_L": "leftMiddleDistal",
        "ring_01_L": "leftRingProximal",
        "ring_02_L": "leftRingIntermediate",
        "ring_03_L": "leftRingDistal",
        "ring_1_L": "leftRingProximal",
        "ring_2_L": "leftRingIntermediate",
        "ring_3_L": "leftRingDistal",
        "little_01_L": "leftLittleProximal",
        "little_02_L": "leftLittleIntermediate",
        "little_03_L": "leftLittleDistal",
        "little_1_L": "leftLittleProximal",
        "little_2_L": "leftLittleIntermediate",
        "little_3_L": "leftLittleDistal",
        "pinky_01_L": "leftLittleProximal",
        "pinky_02_L": "leftLittleIntermediate",
        "pinky_03_L": "leftLittleDistal",
        "pinky_1_L": "leftLittleProximal",
        "pinky_2_L": "leftLittleIntermediate",
        "pinky_3_L": "leftLittleDistal",
        # Right fingers
        "thumb_01_R": "rightThumbMetacarpal",
        "thumb_02_R": "rightThumbProximal",
        "thumb_03_R": "rightThumbDistal",
        "thumb_1_R": "rightThumbMetacarpal",
        "thumb_2_R": "rightThumbProximal",
        "thumb_3_R": "rightThumbDistal",
        "index_01_R": "rightIndexProximal",
        "index_02_R": "rightIndexIntermediate",
        "index_03_R": "rightIndexDistal",
        "index_1_R": "rightIndexProximal",
        "index_2_R": "rightIndexIntermediate",
        "index_3_R": "rightIndexDistal",
        "middle_01_R": "rightMiddleProximal",
        "middle_02_R": "rightMiddleIntermediate",
        "middle_03_R": "rightMiddleDistal",
        "middle_1_R": "rightMiddleProximal",
        "middle_2_R": "rightMiddleIntermediate",
        "middle_3_R": "rightMiddleDistal",
        "ring_01_R": "rightRingProximal",
        "ring_02_R": "rightRingIntermediate",
        "ring_03_R": "rightRingDistal",
        "ring_1_R": "rightRingProximal",
        "ring_2_R": "rightRingIntermediate",
        "ring_3_R": "rightRingDistal",
        "little_01_R": "rightLittleProximal",
        "little_02_R": "rightLittleIntermediate",
        "little_03_R": "rightLittleDistal",
        "little_1_R": "rightLittleProximal",
        "little_2_R": "rightLittleIntermediate",
        "little_3_R": "rightLittleDistal",
        "pinky_01_R": "rightLittleProximal",
        "pinky_02_R": "rightLittleIntermediate",
        "pinky_03_R": "rightLittleDistal",
        "pinky_1_R": "rightLittleProximal",
        "pinky_2_R": "rightLittleIntermediate",
        "pinky_3_R": "rightLittleDistal",
        # Eyes
        "eye_L": "leftEye",
        "eye_R": "rightEye",
        "jaw": "jaw",
    }


def _unity_mecanim_patterns() -> dict[str, str]:
    """Unity Mecanim / VRC PascalCase naming (no spaces, no prefix).

    Common in VRC models exported from Unity, where bone names follow the
    Unity Humanoid Mecanim convention. Also covers common aliases like
    LeftKnee (VRC) for LeftLowerLeg (Mecanim) and LeftForeArm (Mixamo).
    """
    return {
        # Core body
        "Hips": "hips",
        "Spine": "spine",
        "Chest": "chest",
        "UpperChest": "upperChest",
        "Neck": "neck",
        "Head": "head",
        # Arms
        "LeftShoulder": "leftShoulder",
        "LeftUpperArm": "leftUpperArm",
        "LeftLowerArm": "leftLowerArm",
        "LeftForeArm": "leftLowerArm",  # Mixamo alias
        "LeftHand": "leftHand",
        "RightShoulder": "rightShoulder",
        "RightUpperArm": "rightUpperArm",
        "RightLowerArm": "rightLowerArm",
        "RightForeArm": "rightLowerArm",  # Mixamo alias
        "RightHand": "rightHand",
        # Legs
        "LeftUpperLeg": "leftUpperLeg",
        "LeftLowerLeg": "leftLowerLeg",
        "LeftKnee": "leftLowerLeg",  # VRC alias
        "LeftFoot": "leftFoot",
        "LeftToe": "leftToes",
        "LeftToeBase": "leftToes",
        "RightUpperLeg": "rightUpperLeg",
        "RightLowerLeg": "rightLowerLeg",
        "RightKnee": "rightLowerLeg",  # VRC alias
        "RightFoot": "rightFoot",
        "RightToe": "rightToes",
        "RightToeBase": "rightToes",
        # Eyes
        "LeftEye": "leftEye",
        "RightEye": "rightEye",
        # Fingers (VRC style: LeftThumb1, LeftIndex1, etc.)
        "LeftThumb1": "leftThumbProximal",
        "LeftThumb2": "leftThumbIntermediate",
        "LeftThumb3": "leftThumbDistal",
        "LeftIndex1": "leftIndexProximal",
        "LeftIndex2": "leftIndexIntermediate",
        "LeftIndex3": "leftIndexDistal",
        "LeftMiddle1": "leftMiddleProximal",
        "LeftMiddle2": "leftMiddleIntermediate",
        "LeftMiddle3": "leftMiddleDistal",
        "LeftRing1": "leftRingProximal",
        "LeftRing2": "leftRingIntermediate",
        "LeftRing3": "leftRingDistal",
        "LeftPinky1": "leftLittleProximal",
        "LeftPinky2": "leftLittleIntermediate",
        "LeftPinky3": "leftLittleDistal",
        "RightThumb1": "rightThumbProximal",
        "RightThumb2": "rightThumbIntermediate",
        "RightThumb3": "rightThumbDistal",
        "RightIndex1": "rightIndexProximal",
        "RightIndex2": "rightIndexIntermediate",
        "RightIndex3": "rightIndexDistal",
        "RightMiddle1": "rightMiddleProximal",
        "RightMiddle2": "rightMiddleIntermediate",
        "RightMiddle3": "rightMiddleDistal",
        "RightRing1": "rightRingProximal",
        "RightRing2": "rightRingIntermediate",
        "RightRing3": "rightRingDistal",
        "RightPinky1": "rightLittleProximal",
        "RightPinky2": "rightLittleIntermediate",
        "RightPinky3": "rightLittleDistal",
    }


def _unity_cats_patterns() -> dict[str, str]:
    """Unity Humanoid / Cats Blender Plugin naming.

    Common in VRChat .blend files processed by Cats plugin.
    """
    return {
        # Cats plugin uses these names after "Fix Model"
        "Hips": "hips",
        "Spine": "spine",
        "Chest": "chest",
        "Upper Chest": "upperChest",
        "Neck": "neck",
        "Head": "head",
        "Left shoulder": "leftShoulder",
        "Left arm": "leftUpperArm",
        "Left elbow": "leftLowerArm",
        "Left wrist": "leftHand",
        "Right shoulder": "rightShoulder",
        "Right arm": "rightUpperArm",
        "Right elbow": "rightLowerArm",
        "Right wrist": "rightHand",
        "Left leg": "leftUpperLeg",
        "Left knee": "leftLowerLeg",
        "Left ankle": "leftFoot",
        "Left toe": "leftToes",
        "Right leg": "rightUpperLeg",
        "Right knee": "rightLowerLeg",
        "Right ankle": "rightFoot",
        "Right toe": "rightToes",
        # Cats finger names
        "Thumb0_L": "leftThumbMetacarpal",
        "Thumb1_L": "leftThumbProximal",
        "Thumb2_L": "leftThumbDistal",
        "IndexFinger1_L": "leftIndexProximal",
        "IndexFinger2_L": "leftIndexIntermediate",
        "IndexFinger3_L": "leftIndexDistal",
        "MiddleFinger1_L": "leftMiddleProximal",
        "MiddleFinger2_L": "leftMiddleIntermediate",
        "MiddleFinger3_L": "leftMiddleDistal",
        "RingFinger1_L": "leftRingProximal",
        "RingFinger2_L": "leftRingIntermediate",
        "RingFinger3_L": "leftRingDistal",
        "LittleFinger1_L": "leftLittleProximal",
        "LittleFinger2_L": "leftLittleIntermediate",
        "LittleFinger3_L": "leftLittleDistal",
        "Thumb0_R": "rightThumbMetacarpal",
        "Thumb1_R": "rightThumbProximal",
        "Thumb2_R": "rightThumbDistal",
        "IndexFinger1_R": "rightIndexProximal",
        "IndexFinger2_R": "rightIndexIntermediate",
        "IndexFinger3_R": "rightIndexDistal",
        "MiddleFinger1_R": "rightMiddleProximal",
        "MiddleFinger2_R": "rightMiddleIntermediate",
        "MiddleFinger3_R": "rightMiddleDistal",
        "RingFinger1_R": "rightRingProximal",
        "RingFinger2_R": "rightRingIntermediate",
        "RingFinger3_R": "rightRingDistal",
        "LittleFinger1_R": "rightLittleProximal",
        "LittleFinger2_R": "rightLittleIntermediate",
        "LittleFinger3_R": "rightLittleDistal",
        # Eye/Jaw
        "Eye_L": "leftEye",
        "Eye_R": "rightEye",
        "Jaw": "jaw",
    }


def _mixamo_patterns() -> dict[str, str]:
    """Mixamo / standard FBX humanoid naming."""
    return {
        "mixamorig:Hips": "hips",
        "mixamorig:Spine": "spine",
        "mixamorig:Spine1": "chest",
        "mixamorig:Spine2": "upperChest",
        "mixamorig:Neck": "neck",
        "mixamorig:Head": "head",
        "mixamorig:LeftShoulder": "leftShoulder",
        "mixamorig:LeftArm": "leftUpperArm",
        "mixamorig:LeftForeArm": "leftLowerArm",
        "mixamorig:LeftHand": "leftHand",
        "mixamorig:RightShoulder": "rightShoulder",
        "mixamorig:RightArm": "rightUpperArm",
        "mixamorig:RightForeArm": "rightLowerArm",
        "mixamorig:RightHand": "rightHand",
        "mixamorig:LeftUpLeg": "leftUpperLeg",
        "mixamorig:LeftLeg": "leftLowerLeg",
        "mixamorig:LeftFoot": "leftFoot",
        "mixamorig:LeftToeBase": "leftToes",
        "mixamorig:RightUpLeg": "rightUpperLeg",
        "mixamorig:RightLeg": "rightLowerLeg",
        "mixamorig:RightFoot": "rightFoot",
        "mixamorig:RightToeBase": "rightToes",
        # Without prefix (sometimes stripped)
        "Hips": "hips",
        "Spine": "spine",
        "Spine1": "chest",
        "Spine2": "upperChest",
        "Neck": "neck",
        "Head": "head",
        "LeftShoulder": "leftShoulder",
        "LeftArm": "leftUpperArm",
        "LeftForeArm": "leftLowerArm",
        "LeftHand": "leftHand",
        "RightShoulder": "rightShoulder",
        "RightArm": "rightUpperArm",
        "RightForeArm": "rightLowerArm",
        "RightHand": "rightHand",
        "LeftUpLeg": "leftUpperLeg",
        "LeftLeg": "leftLowerLeg",
        "LeftFoot": "leftFoot",
        "LeftToeBase": "leftToes",
        "RightUpLeg": "rightUpperLeg",
        "RightLeg": "rightLowerLeg",
        "RightFoot": "rightFoot",
        "RightToeBase": "rightToes",
    }


def _japanese_patterns() -> dict[str, str]:
    """Japanese bone names (MMD / Japanese VRChat models)."""
    return {
        # PMX/MMD style Japanese names
        "下半身": "hips",
        "センター": "hips",
        "上半身": "spine",
        "上半身2": "chest",
        "上半身3": "upperChest",
        "首": "neck",
        "頭": "head",
        "左肩": "leftShoulder",
        "左腕": "leftUpperArm",
        "左ひじ": "leftLowerArm",
        "左手首": "leftHand",
        "右肩": "rightShoulder",
        "右腕": "rightUpperArm",
        "右ひじ": "rightLowerArm",
        "右手首": "rightHand",
        "左足": "leftUpperLeg",
        "左ひざ": "leftLowerLeg",
        "左足首": "leftFoot",
        "左つま先": "leftToes",
        "右足": "rightUpperLeg",
        "右ひざ": "rightLowerLeg",
        "右足首": "rightFoot",
        "右つま先": "rightToes",
        # Finger names
        "左親指０": "leftThumbMetacarpal",
        "左親指１": "leftThumbProximal",
        "左親指２": "leftThumbDistal",
        "左人指１": "leftIndexProximal",
        "左人指２": "leftIndexIntermediate",
        "左人指３": "leftIndexDistal",
        "左中指１": "leftMiddleProximal",
        "左中指２": "leftMiddleIntermediate",
        "左中指３": "leftMiddleDistal",
        "左薬指１": "leftRingProximal",
        "左薬指２": "leftRingIntermediate",
        "左薬指３": "leftRingDistal",
        "左小指１": "leftLittleProximal",
        "左小指２": "leftLittleIntermediate",
        "左小指３": "leftLittleDistal",
        "右親指０": "rightThumbMetacarpal",
        "右親指１": "rightThumbProximal",
        "右親指２": "rightThumbDistal",
        "右人指１": "rightIndexProximal",
        "右人指２": "rightIndexIntermediate",
        "右人指３": "rightIndexDistal",
        "右中指１": "rightMiddleProximal",
        "右中指２": "rightMiddleIntermediate",
        "右中指３": "rightMiddleDistal",
        "右薬指１": "rightRingProximal",
        "右薬指２": "rightRingIntermediate",
        "右薬指３": "rightRingDistal",
        "右小指１": "rightLittleProximal",
        "右小指２": "rightLittleIntermediate",
        "右小指３": "rightLittleDistal",
    }


def _generic_patterns() -> dict[str, str]:
    """Generic / lowercased humanoid names (last resort)."""
    return {
        "hips": "hips",
        "hip": "hips",
        "pelvis": "hips",
        "spine": "spine",
        "spine1": "chest",
        "spine.001": "chest",
        "chest": "chest",
        "spine2": "upperChest",
        "spine.002": "upperChest",
        "upper_chest": "upperChest",
        "neck": "neck",
        "head": "head",
        "shoulder.l": "leftShoulder",
        "shoulder.r": "rightShoulder",
        "upper_arm.l": "leftUpperArm",
        "upper_arm.r": "rightUpperArm",
        "forearm.l": "leftLowerArm",
        "forearm.r": "rightLowerArm",
        "hand.l": "leftHand",
        "hand.r": "rightHand",
        "thigh.l": "leftUpperLeg",
        "thigh.r": "rightUpperLeg",
        "shin.l": "leftLowerLeg",
        "shin.r": "rightLowerLeg",
        "foot.l": "leftFoot",
        "foot.r": "rightFoot",
        "toe.l": "leftToes",
        "toe.r": "rightToes",
    }


def merge_vertex_groups(obj: bpy.types.Object, source_name: str, target_name: str):
    """Merge source vertex group into target vertex group, then remove source."""
    source_vg = obj.vertex_groups.get(source_name)
    target_vg = obj.vertex_groups.get(target_name)

    if not source_vg:
        return

    if not target_vg:
        # Just rename source to target
        source_vg.name = target_name
        return

    # Add source weights to target
    for vert in obj.data.vertices:
        source_weight = 0.0
        try:
            source_weight = source_vg.weight(vert.index)
        except RuntimeError:
            pass

        if source_weight > 0:
            try:
                existing = target_vg.weight(vert.index)
                target_vg.add([vert.index], existing + source_weight, 'REPLACE')
            except RuntimeError:
                target_vg.add([vert.index], source_weight, 'REPLACE')

    obj.vertex_groups.remove(source_vg)


def split_vertex_group_by_distance(
    obj: bpy.types.Object,
    armature: bpy.types.Object,
    source_name: str,
    target_a_name: str,
    target_b_name: str,
):
    """Split a vertex group's weights between two targets based on distance.

    For each vertex with weight in *source_name*, distribute the weight
    between *target_a* and *target_b* proportionally to how close the vertex
    is to each target bone.  After splitting, the source group is removed.

    Typical use: ThumbMetacarpal → split between Hand (palm) and Finger0 (thumb).
    """
    import mathutils

    source_vg = obj.vertex_groups.get(source_name)
    if not source_vg:
        return

    # Get bone head positions in world space
    bone_a = armature.data.bones.get(target_a_name)
    bone_b = armature.data.bones.get(target_b_name)
    if not bone_a or not bone_b:
        # Fallback: simple merge into target_a
        merge_vertex_groups(obj, source_name, target_a_name)
        return

    pos_a = armature.matrix_world @ bone_a.head_local
    pos_b = armature.matrix_world @ bone_b.head_local

    # Ensure target vertex groups exist
    vg_a = obj.vertex_groups.get(target_a_name)
    if not vg_a:
        vg_a = obj.vertex_groups.new(name=target_a_name)
    vg_b = obj.vertex_groups.get(target_b_name)
    if not vg_b:
        vg_b = obj.vertex_groups.new(name=target_b_name)

    mesh_world = obj.matrix_world
    for vert in obj.data.vertices:
        try:
            src_w = source_vg.weight(vert.index)
        except RuntimeError:
            continue
        if src_w <= 0:
            continue

        # Distance from vertex to each target bone
        vert_world = mesh_world @ vert.co
        dist_a = (vert_world - pos_a).length
        dist_b = (vert_world - pos_b).length
        total = dist_a + dist_b
        if total < 1e-6:
            ratio_a = 0.5
        else:
            # Closer to A → more weight to A (inverse distance)
            ratio_a = 1.0 - (dist_a / total)

        w_a = src_w * ratio_a
        w_b = src_w * (1.0 - ratio_a)

        # Add to targets
        try:
            existing = vg_a.weight(vert.index)
            vg_a.add([vert.index], existing + w_a, 'REPLACE')
        except RuntimeError:
            vg_a.add([vert.index], w_a, 'REPLACE')

        try:
            existing = vg_b.weight(vert.index)
            vg_b.add([vert.index], existing + w_b, 'REPLACE')
        except RuntimeError:
            vg_b.add([vert.index], w_b, 'REPLACE')

    obj.vertex_groups.remove(source_vg)


def cleanup_vertex_weights(obj: bpy.types.Object, max_influences: int = 3,
                           min_weight: float = 0.01):
    """Clean up vertex weights: limit influences and normalize.

    Parameters
    ----------
    obj : bpy.types.Object
        Mesh object.
    max_influences : int
        Maximum bone influences per vertex (Source Engine recommends 3).
    min_weight : float
        Minimum weight threshold; smaller weights are removed.
    """
    for vert in obj.data.vertices:
        # Collect all (vg_index, weight) for this vertex
        weights = []
        for g in vert.groups:
            w = g.weight
            if w >= min_weight:
                weights.append((g.group, w))

        if not weights:
            continue

        # Sort by weight descending, keep top max_influences
        weights.sort(key=lambda x: x[1], reverse=True)
        kept = weights[:max_influences]

        # Normalize so they sum to 1.0
        total = sum(w for _, w in kept)
        if total <= 0:
            continue

        # Build set of kept group indices
        kept_indices = {gi for gi, _ in kept}

        # Apply: set kept weights (normalized), remove the rest
        for g in vert.groups:
            if g.group in kept_indices:
                # Find this group's kept weight
                for gi, w in kept:
                    if gi == g.group:
                        g.weight = w / total
                        break
            else:
                g.weight = 0.0

        # Remove zero-weight entries
        groups_to_remove = [g.group for g in vert.groups if g.weight <= 0]
        for gi in groups_to_remove:
            vg = obj.vertex_groups[gi]
            try:
                vg.remove([vert.index])
            except RuntimeError:
                pass


def insert_bone_between(armature: bpy.types.Object, new_bone_name: str,
                        parent_name: str, child_name: str):
    """Insert a new bone between parent and child in edit mode.

    The new bone is positioned at the midpoint between parent head and child head.
    Must be called while armature is in edit mode.
    """
    edit_bones = armature.data.edit_bones

    parent_bone = edit_bones.get(parent_name)
    child_bone = edit_bones.get(child_name)

    if not parent_bone or not child_bone:
        return None

    new_bone = edit_bones.new(new_bone_name)
    new_bone.head = (parent_bone.head + child_bone.head) / 2
    new_bone.tail = child_bone.head
    new_bone.parent = parent_bone
    new_bone.use_connect = False

    # Re-parent child to new bone
    child_bone.parent = new_bone

    return new_bone


def orient_bones_to_valvebiped(armature: bpy.types.Object):
    """Reorient edit bones so our SMD export produces male_07-compatible rotations.

    For each ValveBiped bone we know the *desired* parent-relative SMD
    rotation (stored in ``MALE07_SMD_ROTATIONS``, from the HL2 male_07
    standard citizen model).

    Our export pipeline is::

        smd_rot = (_COORD_CONV @ blender_parent_relative @ _COORD_CONV_INV)
                  .to_euler('XYZ')

    So the required Blender parent-relative rotation is::

        blender_local_rot = _COORD_CONV_INV @ smd_rot_mat @ _COORD_CONV

    We accumulate world (armature-space) rotations from root to leaves
    and set each edit bone's tail direction + roll accordingly.

    **Head positions are preserved** — only tail and roll change.
    This means the mesh vertices (stored in armature/world space) remain
    correct, while the skeleton section of every exported SMD now carries
    male_07-compatible rotations.

    Must be called while armature is in edit mode.
    """
    import math
    from mathutils import Matrix, Euler
    from ..data.bone_mapping import (
        MALE07_SMD_ROTATIONS,
        VALVEBIPED_BONE_ORDER,
        VALVEBIPED_HIERARCHY,
    )

    # SMD coords = Blender coords — no conversion needed
    _CCV = Matrix.Identity(3)
    _CCV_INV = Matrix.Identity(3)

    edit_bones = armature.data.edit_bones

    # Pass 1: compute desired armature-space 3×3 rotation for every bone
    #          in the hierarchy (even bones not present in the armature,
    #          because a missing parent's rotation is still needed to
    #          derive the child's armature-space rotation).
    arm_rot = {}  # bone_name → Matrix 3×3 (armature-space rotation)

    for bone_name in VALVEBIPED_BONE_ORDER:
        smd_rot = MALE07_SMD_ROTATIONS.get(bone_name)
        if smd_rot is None:
            continue

        # Parent-relative Blender rotation that produces this SMD rotation
        smd_mat = Euler(smd_rot, 'XYZ').to_matrix()       # 3×3
        local_rot = _CCV_INV @ smd_mat @ _CCV              # 3×3

        parent_name = VALVEBIPED_HIERARCHY.get(bone_name, "")
        if parent_name and parent_name in arm_rot:
            arm_rot[bone_name] = arm_rot[parent_name] @ local_rot
        else:
            arm_rot[bone_name] = local_rot

    # Pass 2: apply orientation to edit bones that exist in the armature
    for bone_name, rot_3x3 in arm_rot.items():
        bone = edit_bones.get(bone_name)
        if bone is None:
            continue

        length = max(bone.length, 0.01)

        # Y column = bone direction (head → tail) in armature space
        direction = Vector(rot_3x3.col[1]).normalized()
        bone.tail = bone.head + direction * length

        # Z column = bone's "up" vector — use align_roll to match it
        z_axis = Vector(rot_3x3.col[2])
        bone.align_roll(z_axis)


def simplify_finger_weights(
    mesh_objects: list[bpy.types.Object],
    mode: str,
) -> int:
    """Simplify finger vertex group weights based on the chosen mode.

    Parameters
    ----------
    mesh_objects : list[bpy.types.Object]
        Mesh objects parented to the armature.
    mode : str
        'SIMPLE'   - merge child joints into proximal (1 rod per finger)
        'DETAILED' - no change (3 joints per finger)
        'FROZEN'   - merge all finger weights into Hand

    Returns
    -------
    int
        Number of vertex group merges performed.
    """
    from ..data.bone_mapping import FINGER_SIMPLE_MERGE, FINGER_FROZEN_MERGE

    if mode == 'DETAILED':
        return 0

    if mode == 'SIMPLE':
        merge_map = FINGER_SIMPLE_MERGE
    elif mode == 'FROZEN':
        merge_map = FINGER_FROZEN_MERGE
    else:
        return 0

    merge_count = 0
    for target_name, source_names in merge_map.items():
        for source_name in source_names:
            for mesh_obj in mesh_objects:
                if mesh_obj.vertex_groups.get(source_name):
                    merge_vertex_groups(mesh_obj, source_name, target_name)
                    merge_count += 1

    return merge_count
