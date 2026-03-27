"""Weight diagnostics: analyze bone weights after VRM→ValveBiped conversion.

Run:
  blender --background --python diagnose_weights.py -- <blend_file> <model_name> <output_dir>

This runs the conversion pipeline (bone_remap + mesh_prepare + orient_bones),
then analyzes the resulting vertex weights to identify problems.
"""

import sys
import os

# Parse CLI args after "--"
argv = sys.argv[sys.argv.index("--") + 1:]
blend_file = argv[0]
model_name = argv[1]
output_dir = argv[2]

import bpy

# Open blend file
bpy.ops.wm.open_mainfile(filepath=blend_file)

# Enable addon
addon_name = "VRM2GmodPlayermodel"
bpy.ops.preferences.addon_enable(module=addon_name)

# Set props
props = bpy.context.scene.vrm2gmod
props.model_name = model_name
props.output_path = output_dir

# Run bone remap (includes orient_bones)
result = bpy.ops.vrm2gmod.bone_remap()
print(f"\n=== Bone Remap: {result} ===")

# Run mesh prepare (join + triangulate)
result = bpy.ops.vrm2gmod.mesh_prepare()
print(f"=== Mesh Prepare: {result} ===")

# Find armature and mesh
armature = None
mesh_obj = None
for obj in bpy.context.view_layer.objects:
    try:
        if obj.type == 'ARMATURE':
            armature = obj
        elif obj.type == 'MESH' and obj.parent and obj.parent.type == 'ARMATURE':
            mesh_obj = obj
    except ReferenceError:
        continue

if not armature or not mesh_obj:
    print("ERROR: armature or mesh not found")
    sys.exit(1)

print(f"\nArmature: {armature.name}")
print(f"Mesh: {mesh_obj.name}")
print(f"Total vertices: {len(mesh_obj.data.vertices)}")
print(f"Total vertex groups: {len(mesh_obj.vertex_groups)}")

# === Analysis 1: Vertex group → bone mapping ===
print("\n" + "=" * 70)
print("ANALYSIS 1: Vertex Groups and Bone Assignment")
print("=" * 70)

bone_names = {bone.name for bone in armature.data.bones}
vg_names = {vg.name: vg.index for vg in mesh_obj.vertex_groups}

# Which vertex groups map to existing bones?
mapped_vgs = {name for name in vg_names if name in bone_names}
unmapped_vgs = {name for name in vg_names if name not in bone_names}

print(f"\nVertex groups matching bones: {len(mapped_vgs)}")
for name in sorted(mapped_vgs):
    print(f"  ✓ {name}")

if unmapped_vgs:
    print(f"\nVertex groups WITHOUT matching bone (orphaned): {len(unmapped_vgs)}")
    for name in sorted(unmapped_vgs):
        print(f"  ✗ {name}")

# === Analysis 2: Per-bone weight statistics ===
print("\n" + "=" * 70)
print("ANALYSIS 2: Per-Bone Weight Statistics")
print("=" * 70)

# Count vertices and total weight per vertex group
vg_stats = {}  # vg_index -> {count, total_weight, max_weight}
for vg in mesh_obj.vertex_groups:
    vg_stats[vg.index] = {"name": vg.name, "count": 0, "total_weight": 0.0, "max_weight": 0.0}

for vert in mesh_obj.data.vertices:
    for g in vert.groups:
        if g.group in vg_stats:
            stats = vg_stats[g.group]
            stats["count"] += 1
            stats["total_weight"] += g.weight
            stats["max_weight"] = max(stats["max_weight"], g.weight)

print(f"\n{'Bone/VG Name':<45} {'Verts':>7} {'AvgW':>7} {'MaxW':>7}")
print("-" * 70)
for vg_idx in sorted(vg_stats.keys()):
    s = vg_stats[vg_idx]
    if s["count"] > 0:
        avg = s["total_weight"] / s["count"]
        print(f"{s['name']:<45} {s['count']:>7} {avg:>7.3f} {s['max_weight']:>7.3f}")
    else:
        print(f"{s['name']:<45} {'(empty)':>7}")

# === Analysis 3: Vertices with problems ===
print("\n" + "=" * 70)
print("ANALYSIS 3: Vertex Weight Problems")
print("=" * 70)

zero_weight_verts = 0
no_group_verts = 0
low_weight_verts = 0  # total weight < 0.1
single_bone_verts = 0
multi_bone_verts = 0

# Track which bone owns the most vertices (by highest weight)
primary_bone_count = {}

for vert in mesh_obj.data.vertices:
    valid_groups = [(g.group, g.weight) for g in vert.groups if g.weight > 0.001]

    if len(vert.groups) == 0:
        no_group_verts += 1
        continue

    total_w = sum(w for _, w in valid_groups)

    if total_w < 0.001:
        zero_weight_verts += 1
    elif total_w < 0.1:
        low_weight_verts += 1

    if len(valid_groups) == 1:
        single_bone_verts += 1
    elif len(valid_groups) > 1:
        multi_bone_verts += 1

    if valid_groups:
        primary = max(valid_groups, key=lambda x: x[1])
        vg_name = mesh_obj.vertex_groups[primary[0]].name if primary[0] < len(mesh_obj.vertex_groups) else "???"
        primary_bone_count[vg_name] = primary_bone_count.get(vg_name, 0) + 1

total_verts = len(mesh_obj.data.vertices)
print(f"\nTotal vertices:        {total_verts}")
print(f"No vertex group:       {no_group_verts} ({100*no_group_verts/total_verts:.1f}%)")
print(f"Zero total weight:     {zero_weight_verts} ({100*zero_weight_verts/total_verts:.1f}%)")
print(f"Low total weight(<0.1):{low_weight_verts} ({100*low_weight_verts/total_verts:.1f}%)")
print(f"Single bone:           {single_bone_verts} ({100*single_bone_verts/total_verts:.1f}%)")
print(f"Multi bone:            {multi_bone_verts} ({100*multi_bone_verts/total_verts:.1f}%)")

print(f"\n{'Primary Bone (most verts owned)':<45} {'Verts':>7}")
print("-" * 55)
for name, count in sorted(primary_bone_count.items(), key=lambda x: -x[1]):
    print(f"{name:<45} {count:>7} ({100*count/total_verts:.1f}%)")

# === Analysis 4: ValveBiped bones WITHOUT any weights ===
print("\n" + "=" * 70)
print("ANALYSIS 4: ValveBiped Bones Without Vertex Weights")
print("=" * 70)

from VRM2GmodPlayermodel.data.bone_mapping import VALVEBIPED_BONE_ORDER, QC_ONLY_BONES

for bone_name in VALVEBIPED_BONE_ORDER:
    if bone_name in QC_ONLY_BONES:
        continue  # QC-only bones don't need weights

    bone = armature.data.bones.get(bone_name)
    if bone is None:
        continue

    vg = mesh_obj.vertex_groups.get(bone_name)
    if vg is None:
        print(f"  ⚠ {bone_name} — NO vertex group at all!")
        continue

    # Check if any vertices actually have weight > 0 for this group
    vg_idx = vg.index
    has_weight = False
    for vert in mesh_obj.data.vertices:
        for g in vert.groups:
            if g.group == vg_idx and g.weight > 0.001:
                has_weight = True
                break
        if has_weight:
            break

    if not has_weight:
        print(f"  ⚠ {bone_name} — vertex group exists but EMPTY (0 weighted verts)")

# === Analysis 5: Spatial analysis - check for disconnected mesh clusters ===
print("\n" + "=" * 70)
print("ANALYSIS 5: Bone Orientation Sanity Check")
print("=" * 70)

# Compare bone rest rotations vs male_07 target
from VRM2GmodPlayermodel.data.bone_mapping import MALE07_SMD_ROTATIONS
import math
from mathutils import Matrix

_CCV = Matrix.Identity(4)
_CCV_INV = Matrix.Identity(4)

print(f"\n{'Bone':<40} {'SMD Rot (actual)':<30} {'SMD Rot (male_07)':<30} {'Match':>5}")
print("-" * 110)

for bone_name in VALVEBIPED_BONE_ORDER:
    bone = armature.data.bones.get(bone_name)
    if bone is None:
        continue

    target = MALE07_SMD_ROTATIONS.get(bone_name)
    if target is None:
        continue

    # Get actual SMD rotation
    if bone.parent:
        local = bone.parent.matrix_local.inverted() @ bone.matrix_local
    else:
        local = bone.matrix_local.copy()

    smd_local = _CCV @ local @ _CCV_INV
    rot = smd_local.to_euler('XYZ')
    actual = (rot.x, rot.y, rot.z)

    # Compare
    diff = sum(abs(a - t) for a, t in zip(actual, target))
    match = "✓" if diff < 0.01 else f"✗ Δ={diff:.3f}"

    actual_str = f"({actual[0]:.4f}, {actual[1]:.4f}, {actual[2]:.4f})"
    target_str = f"({target[0]:.4f}, {target[1]:.4f}, {target[2]:.4f})"

    print(f"{bone_name:<40} {actual_str:<30} {target_str:<30} {match:>5}")

print("\n" + "=" * 70)
print("Diagnosis complete.")
print("=" * 70)
