"""Detect shape keys from an existing .blend file and list them.

Usage:
    blender <blend_file> --background --python batch_detect_sk.py
"""

import bpy
import sys

print("=== Shape Key Detection ===")
print(f"File: {bpy.data.filepath}")

# Find armature
armature = None
for obj in bpy.context.view_layer.objects:
    if obj.type == 'ARMATURE':
        armature = obj
        break

if not armature:
    print("ERROR: No armature found")
    sys.exit(1)

print(f"Armature: {armature.name}")

# Check if ValveBiped converted
has_pelvis = "ValveBiped.Bip01_Pelvis" in armature.data.bones
print(f"ValveBiped converted: {has_pelvis}")

# Find mesh
mesh_obj = None
for obj in bpy.context.view_layer.objects:
    try:
        if obj.type == 'MESH' and obj.parent == armature:
            mesh_obj = obj
            break
    except ReferenceError:
        continue

if not mesh_obj:
    print("ERROR: No mesh found")
    sys.exit(1)

print(f"Mesh: {mesh_obj.name}")

if not mesh_obj.data.shape_keys:
    print("No shape keys found")
    sys.exit(0)

print(f"\n--- Shape Keys ({len(mesh_obj.data.shape_keys.key_blocks) - 1} total, excluding Basis) ---")
for i, kb in enumerate(mesh_obj.data.shape_keys.key_blocks):
    if kb.name == "Basis":
        continue
    # Check if any vertex is different from Basis
    basis = mesh_obj.data.shape_keys.key_blocks[0]
    max_delta = 0
    for vi in range(min(len(kb.data), len(basis.data))):
        delta = (kb.data[vi].co - basis.data[vi].co).length
        if delta > max_delta:
            max_delta = delta
    print(f"  [{i}] {kb.name} (max_delta={max_delta:.4f})")

print("\n=== DONE ===")
