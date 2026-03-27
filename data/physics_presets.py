"""Physics model presets for ragdoll generation.

Defines convex hull boxes per bone for Source Engine collision joints.
Dimensions are in Source Engine units (1 unit ≈ 1 inch).
These are base sizes designed for male_07 (~72 units tall).

Scaling strategy (2026-03-17):
  - Box dimensions along the BONE CHAIN direction scale by the actual
    bone length ratio (model_length / male_07_length).
  - Cross-section dimensions scale by the global height ratio.
  - This prevents grossly oversized boxes on models with anime
    proportions (e.g., short arms, large head).
"""

import math

# Each entry: (bone_name, relative_offset_x, y, z, size_x, y, z)
# Offset is relative to bone position
# Size is the box dimensions

PHYSICS_BONES_MALE = [
    # Torso
    ("ValveBiped.Bip01_Pelvis", 0, 0, 0, 10, 7, 8),
    ("ValveBiped.Bip01_Spine", 0, 0, 3, 9, 6, 6),
    ("ValveBiped.Bip01_Spine1", 0, 0, 3, 10, 6, 6),
    ("ValveBiped.Bip01_Spine2", 0, 0, 3, 10, 6, 6),
    # Head
    ("ValveBiped.Bip01_Head1", 0, 0, 4, 7, 7, 8),
    # Left arm
    ("ValveBiped.Bip01_L_UpperArm", 6, 0, 0, 12, 4, 4),
    ("ValveBiped.Bip01_L_Forearm", 5, 0, 0, 10, 3, 3),
    ("ValveBiped.Bip01_L_Hand", 3, 0, 0, 5, 3, 2),
    # Right arm
    ("ValveBiped.Bip01_R_UpperArm", -6, 0, 0, 12, 4, 4),
    ("ValveBiped.Bip01_R_Forearm", -5, 0, 0, 10, 3, 3),
    ("ValveBiped.Bip01_R_Hand", -3, 0, 0, 5, 3, 2),
    # Left leg
    ("ValveBiped.Bip01_L_Thigh", 0, 0, -8, 5, 5, 16),
    ("ValveBiped.Bip01_L_Calf", 0, 0, -7, 4, 4, 14),
    ("ValveBiped.Bip01_L_Foot", 0, 2, -1, 4, 7, 3),
    # Right leg
    ("ValveBiped.Bip01_R_Thigh", 0, 0, -8, 5, 5, 16),
    ("ValveBiped.Bip01_R_Calf", 0, 0, -7, 4, 4, 14),
    ("ValveBiped.Bip01_R_Foot", 0, 2, -1, 4, 7, 3),
]

PHYSICS_BONES_FEMALE = [
    # Same structure but slightly different proportions
    ("ValveBiped.Bip01_Pelvis", 0, 0, 0, 9, 7, 7),
    ("ValveBiped.Bip01_Spine", 0, 0, 3, 8, 5, 5),
    ("ValveBiped.Bip01_Spine1", 0, 0, 3, 9, 5, 5),
    ("ValveBiped.Bip01_Spine2", 0, 0, 3, 9, 5, 5),
    ("ValveBiped.Bip01_Head1", 0, 0, 4, 6, 6, 7),
    ("ValveBiped.Bip01_L_UpperArm", 5, 0, 0, 10, 3, 3),
    ("ValveBiped.Bip01_L_Forearm", 4, 0, 0, 8, 2.5, 2.5),
    ("ValveBiped.Bip01_L_Hand", 2.5, 0, 0, 4, 2.5, 1.5),
    ("ValveBiped.Bip01_R_UpperArm", -5, 0, 0, 10, 3, 3),
    ("ValveBiped.Bip01_R_Forearm", -4, 0, 0, 8, 2.5, 2.5),
    ("ValveBiped.Bip01_R_Hand", -2.5, 0, 0, 4, 2.5, 1.5),
    ("ValveBiped.Bip01_L_Thigh", 0, 0, -7, 4.5, 4.5, 14),
    ("ValveBiped.Bip01_L_Calf", 0, 0, -6, 3.5, 3.5, 12),
    ("ValveBiped.Bip01_L_Foot", 0, 2, -1, 3.5, 6, 2.5),
    ("ValveBiped.Bip01_R_Thigh", 0, 0, -7, 4.5, 4.5, 14),
    ("ValveBiped.Bip01_R_Calf", 0, 0, -6, 3.5, 3.5, 12),
    ("ValveBiped.Bip01_R_Foot", 0, 2, -1, 3.5, 6, 2.5),
]

# Joint constraint definitions for ragdoll
# (bone_name, min_x, max_x, min_y, max_y, min_z, max_z, friction)
JOINT_CONSTRAINTS = [
    ("ValveBiped.Bip01_Spine", -20, 20, -20, 20, -10, 10, 1.0),
    ("ValveBiped.Bip01_Spine1", -15, 15, -15, 15, -10, 10, 1.0),
    ("ValveBiped.Bip01_Spine2", -15, 15, -15, 15, -10, 10, 1.0),
    ("ValveBiped.Bip01_Neck1", -20, 20, -30, 30, -20, 20, 1.0),
    ("ValveBiped.Bip01_Head1", -10, 10, -15, 15, -10, 10, 1.0),
    ("ValveBiped.Bip01_L_Clavicle", -5, 5, -5, 5, -15, 15, 1.0),
    ("ValveBiped.Bip01_L_UpperArm", -90, 30, -60, 60, -80, 80, 1.0),
    ("ValveBiped.Bip01_L_Forearm", -5, 140, -10, 10, -70, 70, 1.0),
    ("ValveBiped.Bip01_L_Hand", -30, 30, -40, 40, -30, 30, 1.0),
    ("ValveBiped.Bip01_R_Clavicle", -5, 5, -5, 5, -15, 15, 1.0),
    ("ValveBiped.Bip01_R_UpperArm", -90, 30, -60, 60, -80, 80, 1.0),
    ("ValveBiped.Bip01_R_Forearm", -5, 140, -10, 10, -70, 70, 1.0),
    ("ValveBiped.Bip01_R_Hand", -30, 30, -40, 40, -30, 30, 1.0),
    ("ValveBiped.Bip01_L_Thigh", -80, 30, -30, 30, -30, 30, 1.0),
    ("ValveBiped.Bip01_L_Calf", -5, 140, -5, 5, -5, 5, 1.0),
    ("ValveBiped.Bip01_L_Foot", -30, 50, -20, 20, -10, 10, 1.0),
    ("ValveBiped.Bip01_R_Thigh", -80, 30, -30, 30, -30, 30, 1.0),
    ("ValveBiped.Bip01_R_Calf", -5, 140, -5, 5, -5, 5, 1.0),
    ("ValveBiped.Bip01_R_Foot", -30, 50, -20, 20, -10, 10, 1.0),
]


# ---------------------------------------------------------------------------
# Per-bone chain data for proportional physics box scaling.
#
# Maps physics bone → (child_bone_name, primary_axis_index).
#   child_bone_name : the next bone in the chain; used to measure bone length.
#   primary_axis_index : 0=X, 1=Y, 2=Z — the axis along which the box
#       extends along the bone chain.  Offset and size on this axis scale
#       by bone-length ratio; the other two axes scale by height ratio.
#
# Bones NOT in this dict (Pelvis, Head, Hand, Foot) use uniform height
# scaling on all axes.
# ---------------------------------------------------------------------------
PHYSICS_BONE_CHAIN: dict[str, tuple[str, int]] = {
    # Spine chain (primary axis = Z)
    "ValveBiped.Bip01_Spine":      ("ValveBiped.Bip01_Spine1", 2),
    "ValveBiped.Bip01_Spine1":     ("ValveBiped.Bip01_Spine2", 2),
    "ValveBiped.Bip01_Spine2":     ("ValveBiped.Bip01_Spine4", 2),
    # Left arm (primary axis = X)
    "ValveBiped.Bip01_L_UpperArm": ("ValveBiped.Bip01_L_Forearm", 0),
    "ValveBiped.Bip01_L_Forearm":  ("ValveBiped.Bip01_L_Hand", 0),
    # Right arm (primary axis = X)
    "ValveBiped.Bip01_R_UpperArm": ("ValveBiped.Bip01_R_Forearm", 0),
    "ValveBiped.Bip01_R_Forearm":  ("ValveBiped.Bip01_R_Hand", 0),
    # Left leg (primary axis = Z)
    "ValveBiped.Bip01_L_Thigh":    ("ValveBiped.Bip01_L_Calf", 2),
    "ValveBiped.Bip01_L_Calf":     ("ValveBiped.Bip01_L_Foot", 2),
    # Right leg (primary axis = Z)
    "ValveBiped.Bip01_R_Thigh":    ("ValveBiped.Bip01_R_Calf", 2),
    "ValveBiped.Bip01_R_Calf":     ("ValveBiped.Bip01_R_Foot", 2),
}


def compute_bone_scale(armature, bone_name, male07_ref_positions):
    """Return (primary_scale, primary_axis) for a physics bone.

    Parameters
    ----------
    armature : bpy.types.Object
        Armature with ValveBiped-named bones.
    bone_name : str
        The physics bone to compute scale for.
    male07_ref_positions : dict
        ``MALE07_REFERENCE_POSITIONS`` from bone_mapping.

    Returns
    -------
    tuple[float, int] | None
        (scale_ratio, primary_axis_index) if the bone has a chain child,
        or *None* if the bone should use uniform height scaling.
    """
    chain = PHYSICS_BONE_CHAIN.get(bone_name)
    if not chain:
        return None

    child_name, primary_axis = chain

    # Model's actual bone length (world space distance in Blender armature)
    parent_bone = armature.data.bones.get(bone_name)
    child_bone = armature.data.bones.get(child_name)
    if not parent_bone or not child_bone:
        return None

    actual_length = (child_bone.head_local - parent_bone.head_local).length
    if actual_length < 0.01:
        return None

    # male_07 reference bone length = magnitude of child's parent-relative pos
    ref_pos = male07_ref_positions.get(child_name)
    if not ref_pos:
        return None
    ref_length = math.sqrt(ref_pos[0] ** 2 + ref_pos[1] ** 2 + ref_pos[2] ** 2)
    if ref_length < 0.01:
        return None

    return (actual_length / ref_length, primary_axis)
