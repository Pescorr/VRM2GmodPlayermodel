"""Post-conversion diagnostics for VRM → GMod playermodel pipeline.

Checks bone completeness, proportions, weight coverage, and reports
warnings/errors that help users identify and fix conversion issues.
"""

import bpy
from mathutils import Vector

from ..data.bone_mapping import (
    VALVEBIPED_HIERARCHY,
    MALE07_REFERENCE_POSITIONS,
)


# ---------------------------------------------------------------------------
# Required bone sets for a valid Source Engine playermodel
# ---------------------------------------------------------------------------

# Minimum bones that MUST exist for the model to compile and animate
REQUIRED_BONES = {
    "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Spine1",
    "ValveBiped.Bip01_Spine2",
    "ValveBiped.Bip01_Spine4",
    "ValveBiped.Bip01_Neck1",
    "ValveBiped.Bip01_Head1",
    "ValveBiped.Bip01_R_Clavicle",
    "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_L_Clavicle",
    "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_R_Thigh",
    "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_R_Foot",
    "ValveBiped.Bip01_L_Thigh",
    "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_L_Foot",
}


# ---------------------------------------------------------------------------
# Main diagnostic function
# ---------------------------------------------------------------------------


def run_diagnostics(armature, mesh_objects, model_name="",
                    body_type="MALE"):
    """Run post-conversion diagnostics.

    Parameters
    ----------
    armature : bpy.types.Object
        The converted armature with ValveBiped bones.
    mesh_objects : list[bpy.types.Object]
        Mesh objects parented to the armature.
    model_name : str
        Model name for display.
    body_type : str
        'MALE' or 'FEMALE'.

    Returns
    -------
    list[dict]
        List of {'level': 'ERROR'|'WARNING'|'INFO', 'message': str}.
    """
    results = []

    if not armature or not armature.data:
        results.append({'level': 'ERROR',
                        'message': 'アーマチュアが見つかりません'})
        return results

    bone_names = {bone.name for bone in armature.data.bones}

    # --- Check 1: Required bones ---
    _check_required_bones(bone_names, results)

    # --- Check 2: Bone hierarchy ---
    _check_hierarchy(armature, results)

    # --- Check 3: Proportions ---
    _check_proportions(armature, results)

    # --- Check 4: Pelvis position ---
    _check_pelvis_position(armature, results)

    # --- Check 5: Weight coverage ---
    _check_weight_coverage(armature, mesh_objects, bone_names, results)

    # --- Check 6: Body type info ---
    results.append({
        'level': 'INFO',
        'message': f'アニメーションセット: {body_type.lower()}'
    })

    return results


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_required_bones(bone_names, results):
    """Check that all required ValveBiped bones exist."""
    missing = REQUIRED_BONES - bone_names
    if missing:
        # Sort for deterministic output
        missing_short = [n.replace("ValveBiped.Bip01_", "") for n in sorted(missing)]
        results.append({
            'level': 'ERROR',
            'message': f'必須ボーン欠損: {", ".join(missing_short)}'
        })
    else:
        results.append({
            'level': 'INFO',
            'message': f'ボーン完全性: {len(REQUIRED_BONES)}/{len(REQUIRED_BONES)} 正常'
        })


def _check_hierarchy(armature, results):
    """Check that bone parent-child relationships match ValveBiped standard."""
    problems = []
    for bone_name, expected_parent in VALVEBIPED_HIERARCHY.items():
        bone = armature.data.bones.get(bone_name)
        if not bone:
            continue
        actual_parent = bone.parent.name if bone.parent else ""
        if expected_parent and actual_parent != expected_parent:
            # Check if parent exists at all
            if not armature.data.bones.get(expected_parent):
                continue  # Parent bone doesn't exist — already caught by required check
            short_bone = bone_name.replace("ValveBiped.Bip01_", "")
            short_expected = expected_parent.replace("ValveBiped.Bip01_", "")
            short_actual = actual_parent.replace("ValveBiped.Bip01_", "")
            problems.append(f"{short_bone}: 親={short_actual} (期待={short_expected})")

    if problems:
        results.append({
            'level': 'WARNING',
            'message': f'階層不一致: {"; ".join(problems[:3])}'
                       + (f' 他{len(problems)-3}件' if len(problems) > 3 else '')
        })


def _check_proportions(armature, results):
    """Check if limb proportions are within reasonable range of male_07."""
    # Compare arm and leg lengths to male_07 reference
    arm_pairs = [
        ("ValveBiped.Bip01_R_Clavicle", "ValveBiped.Bip01_R_Hand", "右腕"),
        ("ValveBiped.Bip01_L_Clavicle", "ValveBiped.Bip01_L_Hand", "左腕"),
    ]
    leg_pairs = [
        ("ValveBiped.Bip01_R_Thigh", "ValveBiped.Bip01_R_Foot", "右脚"),
        ("ValveBiped.Bip01_L_Thigh", "ValveBiped.Bip01_L_Foot", "左脚"),
    ]

    # male_07 approximate limb lengths (Source Units)
    # Clavicle→UpperArm→Forearm→Hand ≈ 6 + 11.7 + 11.5 ≈ 29.2 SU
    male07_arm_length = 29.2
    # Thigh→Calf→Foot ≈ 17.8 + 12.5 ≈ 30.3 SU
    male07_leg_length = 30.3

    scale = 39.3701  # Blender m → Source Units

    for start_name, end_name, label in arm_pairs + leg_pairs:
        start_bone = armature.data.bones.get(start_name)
        end_bone = armature.data.bones.get(end_name)
        if not start_bone or not end_bone:
            continue

        length_su = (start_bone.head_local - end_bone.head_local).length * scale
        ref_length = (male07_arm_length if "腕" in label else male07_leg_length)
        ratio = length_su / ref_length if ref_length > 0 else 0

        if ratio < 0.30:
            results.append({
                'level': 'WARNING',
                'message': f'プロポーション: {label}がmale_07の{ratio:.0%}'
                           f'（チビモデル？）'
            })
        elif ratio > 2.0:
            results.append({
                'level': 'WARNING',
                'message': f'プロポーション: {label}がmale_07の{ratio:.0%}'
                           f'（巨大モデル？）'
            })


def _check_pelvis_position(armature, results):
    """Check Pelvis position for XY offset issues."""
    pelvis = armature.data.bones.get("ValveBiped.Bip01_Pelvis")
    if not pelvis:
        return

    pos = pelvis.head_local
    xy_offset = (pos.x ** 2 + pos.y ** 2) ** 0.5
    z_height_su = pos.z * 39.3701

    if xy_offset > 0.05:  # > 5cm offset from center
        offset_su = xy_offset * 39.3701
        results.append({
            'level': 'INFO',
            'message': f'Pelvis XY補正適用: {offset_su:.1f}SU → 0'
                       f' (元のオフセット除去)'
        })

    if z_height_su < 15:
        results.append({
            'level': 'WARNING',
            'message': f'Pelvis高さが低い: {z_height_su:.0f}SU'
                       f' (male_07=38.6SU)'
        })
    elif z_height_su > 55:
        results.append({
            'level': 'WARNING',
            'message': f'Pelvis高さが高い: {z_height_su:.0f}SU'
                       f' (male_07=38.6SU)'
        })


def _check_weight_coverage(armature, mesh_objects, bone_names, results):
    """Check that critical bones have vertex weights assigned."""
    # Only check main body bones (not helpers/attachments)
    check_bones = REQUIRED_BONES & bone_names

    bones_without_weights = []
    for mesh_obj in mesh_objects:
        if not mesh_obj.vertex_groups:
            continue
        vg_names = {vg.name for vg in mesh_obj.vertex_groups}
        for bone_name in check_bones:
            if bone_name not in vg_names:
                short = bone_name.replace("ValveBiped.Bip01_", "")
                if short not in bones_without_weights:
                    bones_without_weights.append(short)

    if bones_without_weights:
        results.append({
            'level': 'WARNING',
            'message': f'ウェイト未割当: {", ".join(bones_without_weights[:5])}'
                       + (f' 他{len(bones_without_weights)-5}件'
                          if len(bones_without_weights) > 5 else '')
        })
