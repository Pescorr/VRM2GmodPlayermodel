"""VRM humanoid bone → ValveBiped bone name mapping.

Comprehensive mapping including helper bones, hierarchy, and reference data
from HL2 male_07 standard citizen model (via Althories guide) for animation
compatibility.
"""

# ---------------------------------------------------------------------------
# VRM humanoid bone name → ValveBiped bone name
# Reference: https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/humanoid.md
# Reference: https://wiki.facepunch.com/gmod/ValveBiped_Bones
# ---------------------------------------------------------------------------
VRM_TO_VALVEBIPED: dict[str, str] = {
    # === Torso ===
    "hips": "ValveBiped.Bip01_Pelvis",
    "spine": "ValveBiped.Bip01_Spine",
    "chest": "ValveBiped.Bip01_Spine1",
    "upperChest": "ValveBiped.Bip01_Spine2",
    "neck": "ValveBiped.Bip01_Neck1",
    "head": "ValveBiped.Bip01_Head1",
    # === Left Arm ===
    "leftShoulder": "ValveBiped.Bip01_L_Clavicle",
    "leftUpperArm": "ValveBiped.Bip01_L_UpperArm",
    "leftLowerArm": "ValveBiped.Bip01_L_Forearm",
    "leftHand": "ValveBiped.Bip01_L_Hand",
    # === Right Arm ===
    "rightShoulder": "ValveBiped.Bip01_R_Clavicle",
    "rightUpperArm": "ValveBiped.Bip01_R_UpperArm",
    "rightLowerArm": "ValveBiped.Bip01_R_Forearm",
    "rightHand": "ValveBiped.Bip01_R_Hand",
    # === Left Leg ===
    "leftUpperLeg": "ValveBiped.Bip01_L_Thigh",
    "leftLowerLeg": "ValveBiped.Bip01_L_Calf",
    "leftFoot": "ValveBiped.Bip01_L_Foot",
    "leftToes": "ValveBiped.Bip01_L_Toe0",
    # === Right Leg ===
    "rightUpperLeg": "ValveBiped.Bip01_R_Thigh",
    "rightLowerLeg": "ValveBiped.Bip01_R_Calf",
    "rightFoot": "ValveBiped.Bip01_R_Foot",
    "rightToes": "ValveBiped.Bip01_R_Toe0",
    # === Left Hand Fingers ===
    # Thumb (VRM has Metacarpal/Proximal/Distal, ValveBiped has Finger0/01/02)
    # Note: ThumbMetacarpal is merged into Finger0 (see bone_remap.py)
    "leftThumbProximal": "ValveBiped.Bip01_L_Finger0",
    "leftThumbIntermediate": "ValveBiped.Bip01_L_Finger01",
    "leftThumbDistal": "ValveBiped.Bip01_L_Finger02",
    # Index
    "leftIndexProximal": "ValveBiped.Bip01_L_Finger1",
    "leftIndexIntermediate": "ValveBiped.Bip01_L_Finger11",
    "leftIndexDistal": "ValveBiped.Bip01_L_Finger12",
    # Middle
    "leftMiddleProximal": "ValveBiped.Bip01_L_Finger2",
    "leftMiddleIntermediate": "ValveBiped.Bip01_L_Finger21",
    "leftMiddleDistal": "ValveBiped.Bip01_L_Finger22",
    # Ring
    "leftRingProximal": "ValveBiped.Bip01_L_Finger3",
    "leftRingIntermediate": "ValveBiped.Bip01_L_Finger31",
    "leftRingDistal": "ValveBiped.Bip01_L_Finger32",
    # Little
    "leftLittleProximal": "ValveBiped.Bip01_L_Finger4",
    "leftLittleIntermediate": "ValveBiped.Bip01_L_Finger41",
    "leftLittleDistal": "ValveBiped.Bip01_L_Finger42",
    # === Right Hand Fingers ===
    "rightThumbProximal": "ValveBiped.Bip01_R_Finger0",
    "rightThumbIntermediate": "ValveBiped.Bip01_R_Finger01",
    "rightThumbDistal": "ValveBiped.Bip01_R_Finger02",
    "rightIndexProximal": "ValveBiped.Bip01_R_Finger1",
    "rightIndexIntermediate": "ValveBiped.Bip01_R_Finger11",
    "rightIndexDistal": "ValveBiped.Bip01_R_Finger12",
    "rightMiddleProximal": "ValveBiped.Bip01_R_Finger2",
    "rightMiddleIntermediate": "ValveBiped.Bip01_R_Finger21",
    "rightMiddleDistal": "ValveBiped.Bip01_R_Finger22",
    "rightRingProximal": "ValveBiped.Bip01_R_Finger3",
    "rightRingIntermediate": "ValveBiped.Bip01_R_Finger31",
    "rightRingDistal": "ValveBiped.Bip01_R_Finger32",
    "rightLittleProximal": "ValveBiped.Bip01_R_Finger4",
    "rightLittleIntermediate": "ValveBiped.Bip01_R_Finger41",
    "rightLittleDistal": "ValveBiped.Bip01_R_Finger42",
}

# Reverse mapping for lookup
VALVEBIPED_TO_VRM: dict[str, str] = {v: k for k, v in VRM_TO_VALVEBIPED.items()}

# VRM bones that should be merged (not directly mapped)
# ThumbMetacarpal → merged into ThumbProximal's vertex group
VRM_MERGE_BONES: dict[str, str] = {
    "leftThumbMetacarpal": "leftThumbProximal",
    "rightThumbMetacarpal": "rightThumbProximal",
}

# ---------------------------------------------------------------------------
# Complete ValveBiped hierarchy (bone → parent)
# Includes Spine4, helper bones, forward, and Anim_Attachment
# Reference: male_07 (HL2 standard citizen model, 68 bones)
# ---------------------------------------------------------------------------
VALVEBIPED_HIERARCHY: dict[str, str] = {
    # === Core Skeleton ===
    "ValveBiped.Bip01_Pelvis": "",  # root
    "ValveBiped.Bip01_Spine": "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_Spine1": "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Spine2": "ValveBiped.Bip01_Spine1",
    "ValveBiped.Bip01_Spine4": "ValveBiped.Bip01_Spine2",  # ★ critical for HL2 anim
    "ValveBiped.Bip01_Neck1": "ValveBiped.Bip01_Spine4",   # ★ parented to Spine4
    "ValveBiped.Bip01_Head1": "ValveBiped.Bip01_Neck1",
    "ValveBiped.forward": "ValveBiped.Bip01_Head1",         # gaze direction
    # === Right Arm ===
    "ValveBiped.Bip01_R_Clavicle": "ValveBiped.Bip01_Spine4",  # ★ parented to Spine4
    "ValveBiped.Bip01_R_UpperArm": "ValveBiped.Bip01_R_Clavicle",
    "ValveBiped.Bip01_R_Forearm": "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Hand": "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Anim_Attachment_RH": "ValveBiped.Bip01_R_Hand",  # weapon attach
    # Right fingers
    "ValveBiped.Bip01_R_Finger4": "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_R_Finger41": "ValveBiped.Bip01_R_Finger4",
    "ValveBiped.Bip01_R_Finger42": "ValveBiped.Bip01_R_Finger41",
    "ValveBiped.Bip01_R_Finger3": "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_R_Finger31": "ValveBiped.Bip01_R_Finger3",
    "ValveBiped.Bip01_R_Finger32": "ValveBiped.Bip01_R_Finger31",
    "ValveBiped.Bip01_R_Finger2": "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_R_Finger21": "ValveBiped.Bip01_R_Finger2",
    "ValveBiped.Bip01_R_Finger22": "ValveBiped.Bip01_R_Finger21",
    "ValveBiped.Bip01_R_Finger1": "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_R_Finger11": "ValveBiped.Bip01_R_Finger1",
    "ValveBiped.Bip01_R_Finger12": "ValveBiped.Bip01_R_Finger11",
    "ValveBiped.Bip01_R_Finger0": "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_R_Finger01": "ValveBiped.Bip01_R_Finger0",
    "ValveBiped.Bip01_R_Finger02": "ValveBiped.Bip01_R_Finger01",
    # Right arm helper bones
    "ValveBiped.Bip01_R_Ulna": "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Wrist": "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Shoulder": "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Bicep": "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Elbow": "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Trapezius": "ValveBiped.Bip01_R_Clavicle",
    # === Left Arm ===
    "ValveBiped.Bip01_L_Clavicle": "ValveBiped.Bip01_Spine4",  # ★ parented to Spine4
    "ValveBiped.Bip01_L_UpperArm": "ValveBiped.Bip01_L_Clavicle",
    "ValveBiped.Bip01_L_Forearm": "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_Hand": "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Anim_Attachment_LH": "ValveBiped.Bip01_L_Hand",  # weapon attach
    # Left fingers
    "ValveBiped.Bip01_L_Finger4": "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_L_Finger41": "ValveBiped.Bip01_L_Finger4",
    "ValveBiped.Bip01_L_Finger42": "ValveBiped.Bip01_L_Finger41",
    "ValveBiped.Bip01_L_Finger3": "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_L_Finger31": "ValveBiped.Bip01_L_Finger3",
    "ValveBiped.Bip01_L_Finger32": "ValveBiped.Bip01_L_Finger31",
    "ValveBiped.Bip01_L_Finger2": "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_L_Finger21": "ValveBiped.Bip01_L_Finger2",
    "ValveBiped.Bip01_L_Finger22": "ValveBiped.Bip01_L_Finger21",
    "ValveBiped.Bip01_L_Finger1": "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_L_Finger11": "ValveBiped.Bip01_L_Finger1",
    "ValveBiped.Bip01_L_Finger12": "ValveBiped.Bip01_L_Finger11",
    "ValveBiped.Bip01_L_Finger0": "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_L_Finger01": "ValveBiped.Bip01_L_Finger0",
    "ValveBiped.Bip01_L_Finger02": "ValveBiped.Bip01_L_Finger01",
    # Left arm helper bones
    "ValveBiped.Bip01_L_Ulna": "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Wrist": "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Elbow": "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_Shoulder": "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_Bicep": "ValveBiped.Bip01_L_Clavicle",
    "ValveBiped.Bip01_L_Trapezius": "ValveBiped.Bip01_L_Clavicle",
    # === Right Leg ===
    "ValveBiped.Bip01_R_Thigh": "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_R_Calf": "ValveBiped.Bip01_R_Thigh",
    "ValveBiped.Bip01_R_Foot": "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_R_Toe0": "ValveBiped.Bip01_R_Foot",
    # === Left Leg ===
    "ValveBiped.Bip01_L_Thigh": "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_L_Calf": "ValveBiped.Bip01_L_Thigh",
    "ValveBiped.Bip01_L_Foot": "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_L_Toe0": "ValveBiped.Bip01_L_Foot",
}

# ---------------------------------------------------------------------------
# Bones that exist ONLY in $definebone (not in SMD mesh data)
# These are added by the QC generator, not by Blender bone remap
# ---------------------------------------------------------------------------
QC_ONLY_BONES = {
    # Helper bones (IK/animation aids, no vertex weights)
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
    # Special bones
    "ValveBiped.forward",
    "ValveBiped.Anim_Attachment_RH",
    "ValveBiped.Anim_Attachment_LH",
}

# Bones in SMD (mesh bones with vertex weights + Spine4)
SMD_BONES = set(VALVEBIPED_HIERARCHY.keys()) - QC_ONLY_BONES

# ---------------------------------------------------------------------------
# Optimal bone order in SMD (male_07 reference order)
# This order is used when writing SMD files for best compatibility
# ---------------------------------------------------------------------------
VALVEBIPED_BONE_ORDER: list[str] = [
    # Spine chain
    "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Spine1",
    "ValveBiped.Bip01_Spine2",
    "ValveBiped.Bip01_Spine4",
    # Head
    "ValveBiped.Bip01_Neck1",
    "ValveBiped.Bip01_Head1",
    "ValveBiped.forward",
    # Right arm + fingers
    "ValveBiped.Bip01_R_Clavicle",
    "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Anim_Attachment_RH",
    "ValveBiped.Bip01_R_Finger4",
    "ValveBiped.Bip01_R_Finger41",
    "ValveBiped.Bip01_R_Finger42",
    "ValveBiped.Bip01_R_Finger3",
    "ValveBiped.Bip01_R_Finger31",
    "ValveBiped.Bip01_R_Finger32",
    "ValveBiped.Bip01_R_Finger2",
    "ValveBiped.Bip01_R_Finger21",
    "ValveBiped.Bip01_R_Finger22",
    "ValveBiped.Bip01_R_Finger1",
    "ValveBiped.Bip01_R_Finger11",
    "ValveBiped.Bip01_R_Finger12",
    "ValveBiped.Bip01_R_Finger0",
    "ValveBiped.Bip01_R_Finger01",
    "ValveBiped.Bip01_R_Finger02",
    # Right arm helpers
    "ValveBiped.Bip01_R_Ulna",
    "ValveBiped.Bip01_R_Wrist",
    "ValveBiped.Bip01_R_Shoulder",
    "ValveBiped.Bip01_R_Bicep",
    "ValveBiped.Bip01_R_Elbow",
    "ValveBiped.Bip01_R_Trapezius",
    # Left arm + fingers
    "ValveBiped.Bip01_L_Clavicle",
    "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Anim_Attachment_LH",
    "ValveBiped.Bip01_L_Finger4",
    "ValveBiped.Bip01_L_Finger41",
    "ValveBiped.Bip01_L_Finger42",
    "ValveBiped.Bip01_L_Finger3",
    "ValveBiped.Bip01_L_Finger31",
    "ValveBiped.Bip01_L_Finger32",
    "ValveBiped.Bip01_L_Finger2",
    "ValveBiped.Bip01_L_Finger21",
    "ValveBiped.Bip01_L_Finger22",
    "ValveBiped.Bip01_L_Finger1",
    "ValveBiped.Bip01_L_Finger11",
    "ValveBiped.Bip01_L_Finger12",
    "ValveBiped.Bip01_L_Finger0",
    "ValveBiped.Bip01_L_Finger01",
    "ValveBiped.Bip01_L_Finger02",
    # Left arm helpers
    "ValveBiped.Bip01_L_Ulna",
    "ValveBiped.Bip01_L_Wrist",
    "ValveBiped.Bip01_L_Elbow",
    "ValveBiped.Bip01_L_Shoulder",
    "ValveBiped.Bip01_L_Bicep",
    "ValveBiped.Bip01_L_Trapezius",
    # Right leg
    "ValveBiped.Bip01_R_Thigh",
    "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_R_Foot",
    "ValveBiped.Bip01_R_Toe0",
    # Left leg
    "ValveBiped.Bip01_L_Thigh",
    "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_L_Foot",
    "ValveBiped.Bip01_L_Toe0",
]

# ---------------------------------------------------------------------------
# VRM-specific bone prefixes to EXCLUDE from Source Engine export
# These have no ValveBiped equivalent and would cause issues
# ---------------------------------------------------------------------------
VRM_EXCLUDE_PREFIXES = (
    "ponite", "ear_", "tail", "koshibire", "head_L", "head_R",
    "ahoge", "ahgoge", "oppi_", "onaka", "eye_L", "eye_R",
    "head.00", "head.01", "head.02", "head.03", "head.04",
)

# Bones that are optional in VRM but required for Source Engine
# If missing in VRM, these will be inserted at interpolated positions
OPTIONAL_VRM_BONES = {"chest", "upperChest", "neck", "leftShoulder", "rightShoulder",
                      "leftToes", "rightToes"}

# Bone names that indicate spring bone / physics colliders (to be removed)
SPRING_BONE_PREFIXES = ("secondary", "collider", "spring", "hair", "skirt", "cloth")

# ---------------------------------------------------------------------------
# Finger weight simplification maps
# Used by simplify_finger_weights() in bone_utils.py
# ---------------------------------------------------------------------------

# SIMPLE mode: 4指は1関節、親指はHandに完全統合（伸び防止）
# 辞書の順序が重要: Finger01/02→Finger0 → Finger0→Hand の順で実行
FINGER_SIMPLE_MERGE: dict[str, list[str]] = {
    # --- まず親指の子関節を根元に統合 ---
    "ValveBiped.Bip01_R_Finger0": [
        "ValveBiped.Bip01_R_Finger01", "ValveBiped.Bip01_R_Finger02"],
    "ValveBiped.Bip01_L_Finger0": [
        "ValveBiped.Bip01_L_Finger01", "ValveBiped.Bip01_L_Finger02"],
    # --- 4指: 子関節を根元に統合（1関節で動く） ---
    "ValveBiped.Bip01_R_Finger1": [
        "ValveBiped.Bip01_R_Finger11", "ValveBiped.Bip01_R_Finger12"],
    "ValveBiped.Bip01_R_Finger2": [
        "ValveBiped.Bip01_R_Finger21", "ValveBiped.Bip01_R_Finger22"],
    "ValveBiped.Bip01_R_Finger3": [
        "ValveBiped.Bip01_R_Finger31", "ValveBiped.Bip01_R_Finger32"],
    "ValveBiped.Bip01_R_Finger4": [
        "ValveBiped.Bip01_R_Finger41", "ValveBiped.Bip01_R_Finger42"],
    "ValveBiped.Bip01_L_Finger1": [
        "ValveBiped.Bip01_L_Finger11", "ValveBiped.Bip01_L_Finger12"],
    "ValveBiped.Bip01_L_Finger2": [
        "ValveBiped.Bip01_L_Finger21", "ValveBiped.Bip01_L_Finger22"],
    "ValveBiped.Bip01_L_Finger3": [
        "ValveBiped.Bip01_L_Finger31", "ValveBiped.Bip01_L_Finger32"],
    "ValveBiped.Bip01_L_Finger4": [
        "ValveBiped.Bip01_L_Finger41", "ValveBiped.Bip01_L_Finger42"],
    # --- 最後に親指をHandに統合（Finger0→Hand） ---
    # 上でFinger01/02がFinger0に統合済みなので、全親指ウェイトがHandに移る
    "ValveBiped.Bip01_R_Hand": ["ValveBiped.Bip01_R_Finger0"],
    "ValveBiped.Bip01_L_Hand": ["ValveBiped.Bip01_L_Finger0"],
}

# FROZEN mode: all finger weights merged into Hand bone
FINGER_FROZEN_MERGE: dict[str, list[str]] = {
    "ValveBiped.Bip01_R_Hand": [
        "ValveBiped.Bip01_R_Finger0", "ValveBiped.Bip01_R_Finger01",
        "ValveBiped.Bip01_R_Finger02",
        "ValveBiped.Bip01_R_Finger1", "ValveBiped.Bip01_R_Finger11",
        "ValveBiped.Bip01_R_Finger12",
        "ValveBiped.Bip01_R_Finger2", "ValveBiped.Bip01_R_Finger21",
        "ValveBiped.Bip01_R_Finger22",
        "ValveBiped.Bip01_R_Finger3", "ValveBiped.Bip01_R_Finger31",
        "ValveBiped.Bip01_R_Finger32",
        "ValveBiped.Bip01_R_Finger4", "ValveBiped.Bip01_R_Finger41",
        "ValveBiped.Bip01_R_Finger42",
    ],
    "ValveBiped.Bip01_L_Hand": [
        "ValveBiped.Bip01_L_Finger0", "ValveBiped.Bip01_L_Finger01",
        "ValveBiped.Bip01_L_Finger02",
        "ValveBiped.Bip01_L_Finger1", "ValveBiped.Bip01_L_Finger11",
        "ValveBiped.Bip01_L_Finger12",
        "ValveBiped.Bip01_L_Finger2", "ValveBiped.Bip01_L_Finger21",
        "ValveBiped.Bip01_L_Finger22",
        "ValveBiped.Bip01_L_Finger3", "ValveBiped.Bip01_L_Finger31",
        "ValveBiped.Bip01_L_Finger32",
        "ValveBiped.Bip01_L_Finger4", "ValveBiped.Bip01_L_Finger41",
        "ValveBiped.Bip01_L_Finger42",
    ],
}

# ---------------------------------------------------------------------------
# Weight Paint UI: bone groups by body part (SMD bones with vertex weights)
# (group_label, blender_icon, [bone_names])
# ---------------------------------------------------------------------------
WEIGHT_PAINT_BONE_GROUPS: list[tuple[str, str, list[str]]] = [
    ("体幹", "BONE_DATA", [
        "ValveBiped.Bip01_Pelvis",
        "ValveBiped.Bip01_Spine",
        "ValveBiped.Bip01_Spine1",
        "ValveBiped.Bip01_Spine2",
        "ValveBiped.Bip01_Spine4",
    ]),
    ("頭部", "USER", [
        "ValveBiped.Bip01_Neck1",
        "ValveBiped.Bip01_Head1",
    ]),
    ("右腕", "HAND", [
        "ValveBiped.Bip01_R_Clavicle",
        "ValveBiped.Bip01_R_UpperArm",
        "ValveBiped.Bip01_R_Forearm",
        "ValveBiped.Bip01_R_Hand",
    ]),
    ("右手指", "VIEW_PAN", [
        "ValveBiped.Bip01_R_Finger0",
        "ValveBiped.Bip01_R_Finger01",
        "ValveBiped.Bip01_R_Finger02",
        "ValveBiped.Bip01_R_Finger1",
        "ValveBiped.Bip01_R_Finger11",
        "ValveBiped.Bip01_R_Finger12",
        "ValveBiped.Bip01_R_Finger2",
        "ValveBiped.Bip01_R_Finger21",
        "ValveBiped.Bip01_R_Finger22",
        "ValveBiped.Bip01_R_Finger3",
        "ValveBiped.Bip01_R_Finger31",
        "ValveBiped.Bip01_R_Finger32",
        "ValveBiped.Bip01_R_Finger4",
        "ValveBiped.Bip01_R_Finger41",
        "ValveBiped.Bip01_R_Finger42",
    ]),
    ("左腕", "HAND", [
        "ValveBiped.Bip01_L_Clavicle",
        "ValveBiped.Bip01_L_UpperArm",
        "ValveBiped.Bip01_L_Forearm",
        "ValveBiped.Bip01_L_Hand",
    ]),
    ("左手指", "VIEW_PAN", [
        "ValveBiped.Bip01_L_Finger0",
        "ValveBiped.Bip01_L_Finger01",
        "ValveBiped.Bip01_L_Finger02",
        "ValveBiped.Bip01_L_Finger1",
        "ValveBiped.Bip01_L_Finger11",
        "ValveBiped.Bip01_L_Finger12",
        "ValveBiped.Bip01_L_Finger2",
        "ValveBiped.Bip01_L_Finger21",
        "ValveBiped.Bip01_L_Finger22",
        "ValveBiped.Bip01_L_Finger3",
        "ValveBiped.Bip01_L_Finger31",
        "ValveBiped.Bip01_L_Finger32",
        "ValveBiped.Bip01_L_Finger4",
        "ValveBiped.Bip01_L_Finger41",
        "ValveBiped.Bip01_L_Finger42",
    ]),
    ("右脚", "CON_KINEMATIC", [
        "ValveBiped.Bip01_R_Thigh",
        "ValveBiped.Bip01_R_Calf",
        "ValveBiped.Bip01_R_Foot",
        "ValveBiped.Bip01_R_Toe0",
    ]),
    ("左脚", "CON_KINEMATIC", [
        "ValveBiped.Bip01_L_Thigh",
        "ValveBiped.Bip01_L_Calf",
        "ValveBiped.Bip01_L_Foot",
        "ValveBiped.Bip01_L_Toe0",
    ]),
]

# ---------------------------------------------------------------------------
# Mesh names / keywords to EXCLUDE from body mesh (non-body geometry)
# These meshes may have valid bone weights but are not part of the visible body.
# Matched case-insensitively against the mesh object name.
# ---------------------------------------------------------------------------
MESH_EXCLUDE_KEYWORDS = (
    "球",           # Japanese for "sphere" — eye highlight spheres
    "sphere",       # English sphere meshes
    "highlight",    # Eye highlight overlays
    "collider",     # Physics/spring bone colliders
    "gizmo",        # Editor gizmos
    "bound",        # Bounding volumes
    "dummy",        # Dummy/placeholder meshes
    "shadow",       # Shadow caster meshes
    "outline",      # Outline/toon outline meshes
)

# ---------------------------------------------------------------------------
# $bonemerge entries (for weapon/attachment bone merging in GMod)
# Reference: HL2 standard ValveBiped
# ---------------------------------------------------------------------------
BONEMERGE_BONES: list[str] = [
    "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Spine1",
    "ValveBiped.Bip01_Spine2",
    "ValveBiped.Bip01_Spine4",
    "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_Head1",
    "ValveBiped.Bip01_R_Clavicle",
    "ValveBiped.Bip01_L_Clavicle",
]

# ---------------------------------------------------------------------------
# $attachment definitions
# (name, bone, offset_x, offset_y, offset_z, rotate_x, rotate_y, rotate_z)
# Reference: Althories VRM porting guide
# ---------------------------------------------------------------------------
ATTACHMENT_DEFS: list[tuple[str, str, float, float, float, float, float, float]] = [
    ("eyes", "ValveBiped.Bip01_Head1", 2.63, -4.13, 0.04, 0.0, -80.1, -90.0),
    ("mouth", "ValveBiped.Bip01_Head1", -0.2, -5.8, 0.0, 0.0, -80.0, -90.0),
    ("chest", "ValveBiped.Bip01_Spine2", 4.0, 4.0, 0.0, 0.0, 95.0, 90.0),
    ("forward", "ValveBiped.forward", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    ("anim_attachment_RH", "ValveBiped.Anim_Attachment_RH", 0.0, 0.0, 0.0, -90.0, -90.0, 0.0),
    ("anim_attachment_LH", "ValveBiped.Anim_Attachment_LH", 0.0, 0.0, 0.0, -90.0, -90.0, 0.0),
]

# ---------------------------------------------------------------------------
# IK chain definitions
# (chain_name, bone_name, knee_x, knee_y, knee_z)
# ---------------------------------------------------------------------------
IKCHAIN_DEFS: list[tuple[str, str, float, float, float]] = [
    ("rhand", "ValveBiped.Bip01_R_Hand", 0.707, 0.707, 0.0),
    ("lhand", "ValveBiped.Bip01_L_Hand", 0.707, 0.707, 0.0),
    ("rfoot", "ValveBiped.Bip01_R_Foot", 0.707, -0.707, 0.0),
    ("lfoot", "ValveBiped.Bip01_L_Foot", 0.707, -0.707, 0.0),
]

# ---------------------------------------------------------------------------
# $includemodel paths (correct paths for GMod)
# Separate male/female animation sets for body_type selection
# ---------------------------------------------------------------------------
INCLUDEMODEL_PATHS_MALE: list[str] = [
    "m_anm.mdl",
    "humans/male_shared.mdl",
    "humans/male_ss.mdl",
    "humans/male_gestures.mdl",
    "humans/male_postures.mdl",
]

INCLUDEMODEL_PATHS_FEMALE: list[str] = [
    "f_anm.mdl",
    "humans/female_shared.mdl",
    "humans/female_ss.mdl",
    "humans/female_gestures.mdl",
    "humans/female_postures.mdl",
]

# Legacy alias for backwards compatibility
INCLUDEMODEL_PATHS: list[str] = INCLUDEMODEL_PATHS_MALE

# ---------------------------------------------------------------------------
# male_07 Reference Skeleton Positions
# Standard ValveBiped bone positions from HL2 male_07 citizen model.
# Used for Proportion Trick: reference.smd generation.
# Values are (parent_relative_x, parent_relative_y, parent_relative_z) in SMD coords.
# Source: Althories/vrm-porting-guide-files male_07_reference.smd (Crowbar 0.72)
# ---------------------------------------------------------------------------
MALE07_REFERENCE_POSITIONS: dict[str, tuple[float, float, float]] = {
    "ValveBiped.Bip01_Pelvis":     (-0.000005, -0.533615, 38.566917),
    "ValveBiped.Bip01_Spine":      (0.000005, 3.345127, -2.981901),
    "ValveBiped.Bip01_Spine1":     (4.018326, 0.000000, 0.000000),
    "ValveBiped.Bip01_Spine2":     (3.518562, 0.000000, 0.000000),
    "ValveBiped.Bip01_Spine4":     (8.942646, -0.000001, 0.000000),
    "ValveBiped.Bip01_Neck1":      (3.307274, 0.000001, 0.000000),
    "ValveBiped.Bip01_Head1":      (3.593716, 0.000000, 0.000000),
    "ValveBiped.forward":          (2.000000, -3.000004, 0.000000),
    # Right arm
    "ValveBiped.Bip01_R_Clavicle": (2.033356, 1.000773, -1.937610),
    "ValveBiped.Bip01_R_UpperArm": (6.028144, -0.000004, 0.000000),
    "ValveBiped.Bip01_R_Forearm":  (11.692551, 0.000000, 0.000008),
    "ValveBiped.Bip01_R_Hand":     (11.481701, -0.000001, 0.000011),
    "ValveBiped.Anim_Attachment_RH": (2.676090, -1.712448, 0.000000),
    # Right fingers
    "ValveBiped.Bip01_R_Finger4":  (3.859676, -0.132572, 1.193109),
    "ValveBiped.Bip01_R_Finger41": (1.312565, 0.000004, -0.000002),
    "ValveBiped.Bip01_R_Finger42": (0.729362, 0.000001, 0.000000),
    "ValveBiped.Bip01_R_Finger3":  (3.942291, 0.050323, 0.431043),
    "ValveBiped.Bip01_R_Finger31": (1.539097, 0.000002, 0.000000),
    "ValveBiped.Bip01_R_Finger32": (1.196323, 0.000000, 0.000000),
    "ValveBiped.Bip01_R_Finger2":  (3.881346, 0.211365, -0.402026),
    "ValveBiped.Bip01_R_Finger21": (1.719582, 0.000000, 0.000000),
    "ValveBiped.Bip01_R_Finger22": (1.209179, 0.000004, 0.000000),
    "ValveBiped.Bip01_R_Finger1":  (3.871260, 0.106621, -1.301834),
    "ValveBiped.Bip01_R_Finger11": (1.719433, -0.000004, -0.000002),
    "ValveBiped.Bip01_R_Finger12": (1.099659, 0.000000, -0.000001),
    "ValveBiped.Bip01_R_Finger0":  (0.838804, -0.311184, -1.310237),
    "ValveBiped.Bip01_R_Finger01": (1.789787, -0.000003, 0.000000),
    "ValveBiped.Bip01_R_Finger02": (1.207006, -0.000001, -0.000004),
    # Right arm helpers
    "ValveBiped.Bip01_R_Ulna":     (5.740849, 0.000000, 0.000004),
    "ValveBiped.Bip01_R_Wrist":    (11.481697, -0.000001, 0.000011),
    "ValveBiped.Bip01_R_Shoulder": (1.500000, 0.000001, -0.000008),
    "ValveBiped.Bip01_R_Bicep":    (5.559998, 0.000000, -0.000004),
    "ValveBiped.Bip01_R_Elbow":    (11.692558, 0.000000, 0.000000),
    "ValveBiped.Bip01_R_Trapezius": (5.166961, -0.000004, 0.000000),
    # Left arm
    "ValveBiped.Bip01_L_Clavicle": (2.033348, 1.000769, 1.937660),
    "ValveBiped.Bip01_L_UpperArm": (6.028146, -0.000004, 0.000000),
    "ValveBiped.Bip01_L_Forearm":  (11.692560, 0.000000, -0.000004),
    "ValveBiped.Bip01_L_Hand":     (11.481678, 0.000001, -0.000034),
    "ValveBiped.Anim_Attachment_LH": (2.676090, -1.712440, -0.000001),
    # Left fingers
    "ValveBiped.Bip01_L_Finger4":  (3.859713, -0.142406, -1.191978),
    "ValveBiped.Bip01_L_Finger41": (1.312561, 0.000002, 0.000000),
    "ValveBiped.Bip01_L_Finger42": (0.729362, 0.000003, -0.000001),
    "ValveBiped.Bip01_L_Finger3":  (3.942331, 0.046776, -0.431444),
    "ValveBiped.Bip01_L_Finger31": (1.539093, 0.000002, -0.000001),
    "ValveBiped.Bip01_L_Finger32": (1.196323, -0.000004, -0.000001),
    "ValveBiped.Bip01_L_Finger2":  (3.881376, 0.214691, 0.400259),
    "ValveBiped.Bip01_L_Finger21": (1.719576, 0.000004, 0.000000),
    "ValveBiped.Bip01_L_Finger22": (1.209175, 0.000000, 0.000000),
    "ValveBiped.Bip01_L_Finger1":  (3.871292, 0.117424, 1.300905),
    "ValveBiped.Bip01_L_Finger11": (1.719433, -0.000004, -0.000003),
    "ValveBiped.Bip01_L_Finger12": (1.099663, 0.000002, 0.000000),
    "ValveBiped.Bip01_L_Finger0":  (0.838831, -0.300278, 1.312777),
    "ValveBiped.Bip01_L_Finger01": (1.789785, 0.000001, 0.000000),
    "ValveBiped.Bip01_L_Finger02": (1.207001, 0.000000, 0.000000),
    # Left arm helpers
    "ValveBiped.Bip01_L_Ulna":     (5.740849, 0.000000, 0.000000),
    "ValveBiped.Bip01_L_Wrist":    (11.481699, 0.000000, -0.000004),
    "ValveBiped.Bip01_L_Elbow":    (11.692554, 0.000001, -0.000004),
    "ValveBiped.Bip01_L_Shoulder": (1.499996, 0.000000, -0.000004),
    "ValveBiped.Bip01_L_Bicep":    (5.559998, 0.000000, 0.000000),
    "ValveBiped.Bip01_L_Trapezius": (5.166963, -0.000004, 0.000000),
    # Right leg
    "ValveBiped.Bip01_R_Thigh":    (-3.890452, 0.000004, 0.000007),
    "ValveBiped.Bip01_R_Calf":     (17.848167, 0.000000, 0.000000),
    "ValveBiped.Bip01_R_Foot":     (16.525248, 0.000000, 0.000000),
    "ValveBiped.Bip01_R_Toe0":     (6.879449, -0.000002, 0.000000),
    # Left leg
    "ValveBiped.Bip01_L_Thigh":    (3.890452, -0.000004, -0.000003),
    "ValveBiped.Bip01_L_Calf":     (17.848167, 0.000000, 0.000000),
    "ValveBiped.Bip01_L_Foot":     (16.525244, 0.000001, 0.000000),
    "ValveBiped.Bip01_L_Toe0":     (6.879449, -0.000001, 0.000000),
}

# ---------------------------------------------------------------------------
# male_07 SMD Skeleton Rotations — RadianEuler format (rx, ry, rz).
# Source: Althories/vrm-porting-guide-files male_07_reference.smd (Crowbar 0.72)
# Used for SMD file output (reference.smd and proportions.smd QC-only bones).
# ---------------------------------------------------------------------------
MALE07_SMD_ROTATIONS: dict[str, tuple[float, float, float]] = {
    # Spine chain
    "ValveBiped.Bip01_Pelvis":          (1.570796, 0.000000, 0.000000),
    "ValveBiped.Bip01_Spine":           (1.570796, 0.086293, 1.570796),
    "ValveBiped.Bip01_Spine1":          (0.000000, 0.000000, -0.029242),
    "ValveBiped.Bip01_Spine2":          (0.000000, 0.000000, 0.100336),
    "ValveBiped.Bip01_Spine4":          (0.000000, 0.000000, 0.194096),
    "ValveBiped.Bip01_Neck1":           (3.141590, 0.000000, 0.400478),
    "ValveBiped.Bip01_Head1":           (0.000000, -0.000001, 0.406587),
    # Special
    "ValveBiped.forward":               (-1.570796, 0.000000, -1.326450),
    # Right arm
    "ValveBiped.Bip01_R_Clavicle":      (-1.668474, 1.286518, 2.942953),
    "ValveBiped.Bip01_R_UpperArm":      (1.639479, -0.008065, -0.586846),
    "ValveBiped.Bip01_R_Forearm":       (0.000000, -0.000001, -0.060372),
    "ValveBiped.Bip01_R_Hand":          (-1.564937, 0.106605, 0.044193),
    # Right attachment
    "ValveBiped.Anim_Attachment_RH":    (-1.570796, 0.000000, -1.570795),
    # Right fingers
    "ValveBiped.Bip01_R_Finger4":       (0.479140, -0.158545, -0.879041),
    "ValveBiped.Bip01_R_Finger41":      (0.000001, -0.011931, -0.439671),
    "ValveBiped.Bip01_R_Finger42":      (0.000000, -0.006133, -0.244270),
    "ValveBiped.Bip01_R_Finger3":       (0.154999, -0.079305, -0.810205),
    "ValveBiped.Bip01_R_Finger31":      (0.000000, -0.005854, -0.247771),
    "ValveBiped.Bip01_R_Finger32":      (0.000000, -0.009663, -0.430760),
    "ValveBiped.Bip01_R_Finger2":       (-0.087717, -0.035763, -0.519702),
    "ValveBiped.Bip01_R_Finger21":      (0.000000, -0.007584, -0.366444),
    "ValveBiped.Bip01_R_Finger22":      (0.000000, -0.004241, -0.216380),
    "ValveBiped.Bip01_R_Finger1":       (-0.352486, 0.029262, -0.464072),
    "ValveBiped.Bip01_R_Finger11":      (-0.000001, -0.007737, -0.362953),
    "ValveBiped.Bip01_R_Finger12":      (-0.000001, -0.004929, -0.244295),
    "ValveBiped.Bip01_R_Finger0":       (1.248034, 0.664310, -0.725028),
    "ValveBiped.Bip01_R_Finger01":      (0.000001, 0.003279, 0.228616),
    "ValveBiped.Bip01_R_Finger02":      (0.000000, 0.005010, 0.362994),
    # Right arm helpers
    "ValveBiped.Bip01_R_Ulna":          (0.004600, -0.000001, 0.000000),
    "ValveBiped.Bip01_R_Wrist":         (0.008510, -0.000001, 0.000000),
    "ValveBiped.Bip01_R_Shoulder":      (0.000000, 0.000000, 0.000000),
    "ValveBiped.Bip01_R_Bicep":         (0.000000, 0.000000, 0.000000),
    "ValveBiped.Bip01_R_Elbow":         (0.000000, 0.000000, -0.029500),
    "ValveBiped.Bip01_R_Trapezius":     (0.000000, 0.000000, 0.000000),
    # Left arm
    "ValveBiped.Bip01_L_Clavicle":      (1.596637, -1.286514, 2.942961),
    "ValveBiped.Bip01_L_UpperArm":      (-1.579613, 0.047802, -0.585173),
    "ValveBiped.Bip01_L_Forearm":       (0.000000, 0.000000, -0.060372),
    "ValveBiped.Bip01_L_Hand":          (1.573183, -0.106613, 0.044193),
    # Left attachment
    "ValveBiped.Anim_Attachment_LH":    (1.570797, -0.000001, 1.570797),
    # Left fingers
    "ValveBiped.Bip01_L_Finger4":       (-0.479144, 0.152190, -0.879874),
    "ValveBiped.Bip01_L_Finger41":      (0.000000, 0.009665, -0.439720),
    "ValveBiped.Bip01_L_Finger42":      (0.000000, 0.004971, -0.244299),
    "ValveBiped.Bip01_L_Finger3":       (-0.155014, 0.073328, -0.810648),
    "ValveBiped.Bip01_L_Finger31":      (0.000000, 0.004460, -0.247797),
    "ValveBiped.Bip01_L_Finger32":      (0.000000, 0.007361, -0.430802),
    "ValveBiped.Bip01_L_Finger2":       (0.087707, 0.031641, -0.519952),
    "ValveBiped.Bip01_L_Finger21":      (0.000000, 0.005005, -0.366486),
    "ValveBiped.Bip01_L_Finger22":      (0.000000, 0.002798, -0.216404),
    "ValveBiped.Bip01_L_Finger1":       (0.352467, -0.032975, -0.463848),
    "ValveBiped.Bip01_L_Finger11":      (0.000000, 0.005107, -0.362997),
    "ValveBiped.Bip01_L_Finger12":      (0.000000, 0.003255, -0.244324),
    "ValveBiped.Bip01_L_Finger0":       (-1.251009, -0.669800, -0.720133),
    "ValveBiped.Bip01_L_Finger01":      (0.000000, -0.002159, 0.228629),
    "ValveBiped.Bip01_L_Finger02":      (0.000000, -0.003300, 0.363014),
    # Left arm helpers
    "ValveBiped.Bip01_L_Ulna":          (-0.000544, 0.000000, 0.000000),
    "ValveBiped.Bip01_L_Wrist":         (-0.001005, 0.000000, 0.000000),
    "ValveBiped.Bip01_L_Elbow":         (0.000000, 0.000000, -0.029500),
    "ValveBiped.Bip01_L_Shoulder":      (0.000000, 0.000000, 0.000000),
    "ValveBiped.Bip01_L_Bicep":         (0.000000, 0.000000, 0.000000),
    "ValveBiped.Bip01_L_Trapezius":     (0.000000, 0.000000, 0.000000),
    # Right leg
    "ValveBiped.Bip01_R_Thigh":         (-1.570796, 0.051845, -1.576021),
    "ValveBiped.Bip01_R_Calf":          (0.000000, 0.000000, 0.034187),
    "ValveBiped.Bip01_R_Foot":          (0.038611, 0.040779, -1.071632),
    "ValveBiped.Bip01_R_Toe0":          (-0.081334, -0.002949, -0.584373),
    # Left leg
    "ValveBiped.Bip01_L_Thigh":         (-1.570796, 0.051839, -1.565574),
    "ValveBiped.Bip01_L_Calf":          (0.000000, 0.000000, 0.034200),
    "ValveBiped.Bip01_L_Foot":          (-0.027915, -0.040782, -1.071638),
    "ValveBiped.Bip01_L_Toe0":          (-0.007299, -0.002951, -0.584373),
}
