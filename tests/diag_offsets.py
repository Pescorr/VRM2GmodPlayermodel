"""Diagnostic: print per-bone offsets after running full pipeline.

Hooks into the smd_export to capture offset data.
Run: blender --background <blend> --python diag_offsets.py -- <blend> laguna <outdir>
"""
import sys, os, math, io

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
if len(args) < 3:
    print("Usage: blender --background <blend> --python diag_offsets.py -- <blend> <name> <outdir>")
    sys.exit(1)

BLEND_FILE = args[0]
MODEL_NAME = args[1]
OUTPUT_DIR = args[2]

import bpy

# Enable addon
bpy.ops.preferences.addon_enable(module="VRM2GmodPlayermodel")

# Monkey-patch _compute_bone_offsets to capture its output
import VRM2GmodPlayermodel.utils.smd_export as smd_mod
_original_compute = smd_mod._compute_bone_offsets
_captured_offsets = {}
_captured_bones = []

def _patched_compute(ordered_bones, bone_idx, armature):
    global _captured_offsets, _captured_bones
    result = _original_compute(ordered_bones, bone_idx, armature)
    _captured_offsets = dict(result)
    _captured_bones = list(ordered_bones)

    # Also capture VRM world positions
    vrm_positions = {}
    for smd_idx, (bone_name, bone) in enumerate(ordered_bones):
        if bone is not None:
            vrm_positions[smd_idx] = bone.head_local.copy()
    _captured_offsets['_vrm_pos'] = vrm_positions

    return result

smd_mod._compute_bone_offsets = _patched_compute

# Set addon properties
scene = bpy.context.scene
props = scene.vrm2gmod
props.model_name = MODEL_NAME
props.output_path = OUTPUT_DIR
props.auto_compile = False

# Run pipeline
result = bpy.ops.vrm2gmod.convert_full()
print(f"\nPipeline result: {result}")

# Print diagnostic
print("\n" + "=" * 80)
print("BONE OFFSETS (projected_world - VRM_world)")
print("=" * 80)
print(f"{'Bone':<40} {'Off X':>8} {'Off Y':>8} {'Off Z':>8} {'Mag':>8}")
print("-" * 80)

vrm_pos = _captured_offsets.pop('_vrm_pos', {})

for smd_idx, (bone_name, bone) in enumerate(_captured_bones):
    off = _captured_offsets.get(smd_idx)
    if off is None:
        continue
    mag = off.length
    short_name = bone_name.replace("ValveBiped.Bip01_", "").replace("ValveBiped.", "")
    is_qc = bone is None
    marker = " ***" if mag > 2.0 else (" **" if mag > 1.0 else "")
    qc = " (QC)" if is_qc else ""
    print(f"{short_name:<40} {off.x:>8.3f} {off.y:>8.3f} {off.z:>8.3f} {mag:>8.3f}{marker}{qc}")

# Detail for arm bones
arm_names = [
    "ValveBiped.Bip01_R_Clavicle", "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Forearm", "ValveBiped.Bip01_R_Hand",
]
print("\n" + "=" * 80)
print("ARM BONE DETAIL (Right arm)")
print("=" * 80)
for bname in arm_names:
    found_idx = None
    for si, (bn, b) in enumerate(_captured_bones):
        if bn == bname:
            found_idx = si
            break
    if found_idx is None:
        continue
    off = _captured_offsets.get(found_idx)
    vw = vrm_pos.get(found_idx)
    short = bname.replace("ValveBiped.Bip01_", "")
    if vw and off:
        pw = vw + off
        print(f"\n{short}:")
        print(f"  VRM world:  ({vw.x:>8.3f}, {vw.y:>8.3f}, {vw.z:>8.3f})")
        print(f"  Proj world: ({pw.x:>8.3f}, {pw.y:>8.3f}, {pw.z:>8.3f})")
        print(f"  Offset:     ({off.x:>8.3f}, {off.y:>8.3f}, {off.z:>8.3f})  mag={off.length:.3f}")

print("\nDone.")
