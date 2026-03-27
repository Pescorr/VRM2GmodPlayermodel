"""QC file templates for Source Engine playermodel compilation.

Based on Althories guide convention (no $definebone).
Generates complete QC with $bonemerge, $attachment, $ikchain,
Proportion Trick, and $collisionjoints.

Reference: https://github.com/Althories/vrm-porting-guide-files

QC section order (critical for Proportion Trick):
  1. $modelname, $cdmaterials, $surfaceprop, $eyeposition
  2. $bodygroup
  3. $attachment
  4. $bonemerge
  5. $ikchain + $ikautoplaylock
  6. $sequence "ragdoll"
  7. $includemodel (HL2 animations)
  8. Proportion Trick ($animation + $sequence) ★ MUST BE LAST
  9. $hboxset + $hbox (hitboxes)
  10. $collisionjoints + $collisiontext
"""

# ---------------------------------------------------------------------------
# Hitbox definitions: (group_id, bone_name, min_xyz, max_xyz)
# ---------------------------------------------------------------------------
HITBOX_DEFS = [
    (3, "ValveBiped.Bip01_Pelvis",     (-5, -4, -5),  (5, 4, 5)),
    (4, "ValveBiped.Bip01_Spine",      (-5, -3, -3),  (5, 3, 5)),
    (2, "ValveBiped.Bip01_Spine1",     (-5, -3, -3),  (5, 3, 5)),
    (2, "ValveBiped.Bip01_Spine2",     (-6, -3, -3),  (6, 3, 5)),
    (1, "ValveBiped.Bip01_Head1",      (-3, -5, -3),  (3, 5, 7)),
    (4, "ValveBiped.Bip01_L_UpperArm", (-2, -2, -12), (2, 2, 0)),
    (5, "ValveBiped.Bip01_L_Forearm",  (-2, -2, -10), (2, 2, 0)),
    (5, "ValveBiped.Bip01_L_Hand",     (-1, -1, -4),  (1, 1, 0)),
    (4, "ValveBiped.Bip01_R_UpperArm", (-2, -2, 0),   (2, 2, 12)),
    (5, "ValveBiped.Bip01_R_Forearm",  (-2, -2, 0),   (2, 2, 10)),
    (5, "ValveBiped.Bip01_R_Hand",     (-1, -1, 0),   (1, 1, 4)),
    (6, "ValveBiped.Bip01_L_Thigh",    (-4, -3, -16), (4, 3, 0)),
    (7, "ValveBiped.Bip01_L_Calf",     (-3, -2, -14), (3, 3, 0)),
    (7, "ValveBiped.Bip01_L_Foot",     (-2, -2, -1),  (2, 7, 3)),
    (6, "ValveBiped.Bip01_R_Thigh",    (-4, -3, 0),   (4, 3, 16)),
    (7, "ValveBiped.Bip01_R_Calf",     (-3, -2, 0),   (3, 3, 14)),
    (7, "ValveBiped.Bip01_R_Foot",     (-2, -2, -3),  (2, 7, 1)),
]
