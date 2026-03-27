"""Batch conversion script for existing .blend files (not VRM).

Usage:
    blender <blend_file> --background --python batch_convert_blend.py -- <model_name> <output_base>
"""

import sys
import os

# Parse arguments after "--"
argv = sys.argv
if "--" in argv:
    args = argv[argv.index("--") + 1:]
else:
    print("ERROR: No arguments. Usage: blender <blend> --background --python batch_convert_blend.py -- <model_name> <output_base>")
    sys.exit(1)

if len(args) < 2:
    print("ERROR: Need 2 arguments: <model_name> <output_base>")
    sys.exit(1)

model_name = args[0]
output_base = args[1]

print(f"=== VRM2GmodPlayermodel Batch Convert (.blend) ===")
print(f"Blend: {sys.argv[1] if len(sys.argv) > 1 else 'unknown'}")
print(f"Model: {model_name}")
print(f"Output: {output_base}")

import bpy

# --- Setup properties ---
props = bpy.context.scene.vrm2gmod
props.model_name = model_name
props.output_path = output_base
props.auto_compile = True
props.auto_vtf = True
props.copy_to_gmod = False
props.export_flex = True

# --- Step 1: Bone Remap ---
print("\n--- Step 1: Bone Remap ---")
result = bpy.ops.vrm2gmod.bone_remap()
print(f"Bone remap: {result}")

# --- Step 2: Mesh Prepare ---
print("\n--- Step 2: Mesh Prepare ---")
result = bpy.ops.vrm2gmod.mesh_prepare()
print(f"Mesh prepare: {result}")

# Refresh
bpy.context.view_layer.update()

# --- Find armature and mesh ---
from VRM2GmodPlayermodel.utils.bone_utils import find_armature
armature = find_armature(bpy.context)
if not armature:
    print("ERROR: No armature found after mesh_prepare")
    sys.exit(1)

mesh_obj = None
for obj in bpy.context.view_layer.objects:
    try:
        if obj.type == 'MESH' and obj.parent == armature:
            mesh_obj = obj
            break
    except ReferenceError:
        continue

print(f"Armature: {armature.name}")
print(f"Mesh: {mesh_obj.name if mesh_obj else 'NONE'}")

# --- Step 2.5: A-pose ---
print("\n--- Step 2.5: A-pose Conversion ---")
from VRM2GmodPlayermodel.utils.pose_correction import apply_a_pose
try:
    if mesh_obj:
        apply_a_pose(armature, mesh_obj)
        print("A-pose conversion OK")
    else:
        print("SKIP: No mesh")
except Exception as e:
    print(f"A-pose error (continuing): {e}")

# --- Detect Shape Keys ---
print("\n--- Shape Key Detection ---")
try:
    result = bpy.ops.vrm2gmod.detect_shape_keys()
    print(f"Shape key detect: {result}")

    # Auto-assign all shape keys (recognized → standard, unknown → CUSTOM)
    from VRM2GmodPlayermodel.data.flex_mapping import auto_assign_all
    assigned_count = 0
    for item in props.flex_items:
        target, custom_name = auto_assign_all(item.name)
        if target != 'NONE' and item.flex_target == 'NONE':
            item.flex_target = target
            if target == 'CUSTOM':
                item.custom_flex_name = custom_name
            print(f"  AUTO-ASSIGNED: {item.name} -> {target}"
                  + (f" (custom: {custom_name})" if custom_name else ""))
            assigned_count += 1

    print(f"Total: {len(props.flex_items)}, Assigned: {assigned_count}")
except Exception as e:
    print(f"Shape key detect error: {e}")
    import traceback
    traceback.print_exc()

# --- Steps 3-8: Export Pipeline ---
print("\n--- Steps 3-8: Export Pipeline ---")

compile_dir = os.path.join(output_base, "compile")
models_dir = os.path.join(output_base, "models", "player", model_name)
materials_dir = os.path.join(output_base, "materials", "models", "player", model_name)
os.makedirs(compile_dir, exist_ok=True)
os.makedirs(models_dir, exist_ok=True)
os.makedirs(materials_dir, exist_ok=True)

# Re-find mesh after possible changes
mesh_obj = None
for obj in bpy.context.view_layer.objects:
    try:
        if obj.type == 'MESH' and obj.parent == armature:
            mesh_obj = obj
            break
    except ReferenceError:
        continue

from VRM2GmodPlayermodel.utils.smd_export import (
    write_reference_smd, write_physics_smd,
    write_proportions_smd, write_reference_skeleton_smd,
    write_flex_vta,
)

# Debug: check shape keys on mesh
print(f"\n--- Debug: Mesh shape key check ---")
print(f"Mesh obj: {mesh_obj.name if mesh_obj else 'NONE'}")
if mesh_obj and mesh_obj.data.shape_keys:
    sk_count = len(mesh_obj.data.shape_keys.key_blocks) - 1
    print(f"Shape keys: {sk_count}")
    for kb in mesh_obj.data.shape_keys.key_blocks[:5]:
        print(f"  {kb.name}")
    if sk_count > 4:
        print(f"  ... and {sk_count - 4} more")
else:
    print("Shape keys: NONE!")
    # Try to find mesh WITH shape keys
    for obj in bpy.context.view_layer.objects:
        try:
            if obj.type == 'MESH' and obj.data.shape_keys:
                print(f"  Found mesh with SK: {obj.name} ({len(obj.data.shape_keys.key_blocks)-1} keys)")
                if obj.parent == armature:
                    print(f"  -> This is a child of armature! Using it.")
                    mesh_obj = obj
                    break
        except ReferenceError:
            continue

# Debug: check flex items vs shape keys
print(f"\n--- Debug: flex_items vs shape keys ---")
assigned_items = [(item.name, item.flex_target) for item in props.flex_items if item.flex_target != 'NONE']
print(f"Assigned flex items: {assigned_items}")
if mesh_obj and mesh_obj.data.shape_keys:
    kb_names = [kb.name for kb in mesh_obj.data.shape_keys.key_blocks]
    for sk_name, target in assigned_items:
        found = sk_name in kb_names
        print(f"  '{sk_name}' -> '{target}' | In mesh: {found}")

# Step 3: SMD Export
print("\n--- Step 3: SMD Export ---")
smd_path = os.path.join(compile_dir, f"{model_name}.smd")
ok = write_reference_smd(smd_path, armature, mesh_obj)
size_kb = os.path.getsize(smd_path) / 1024 if ok and os.path.isfile(smd_path) else 0
print(f"Reference SMD: {'OK' if ok else 'FAILED'} ({size_kb:.0f} KB)")

# Step 3.5: VTA Export
print("\n--- Step 3.5: VTA Export ---")
vta_path = os.path.join(compile_dir, f"{model_name}_flex.vta")
try:
    ok, flex_names = write_flex_vta(vta_path, armature, mesh_obj, props.flex_items)
    if ok:
        size_kb = os.path.getsize(vta_path) / 1024
        print(f"VTA export: OK ({len(flex_names)} flexes, {size_kb:.0f} KB)")
        print(f"  Flex names: {flex_names}")
    else:
        print("VTA export: No shape keys to export")
        flex_names = []
except Exception as e:
    print(f"VTA export error: {e}")
    import traceback
    traceback.print_exc()
    flex_names = []

# Step 4: Proportion Trick SMDs
print("\n--- Step 4: Proportion Trick SMDs ---")
ok = write_proportions_smd(os.path.join(compile_dir, "proportions.smd"), armature)
print(f"proportions.smd: {'OK' if ok else 'FAILED'}")
ok = write_reference_skeleton_smd(os.path.join(compile_dir, "reference.smd"), armature)
print(f"reference.smd: {'OK' if ok else 'FAILED'}")

# Step 5: Material Convert
print("\n--- Step 5: Material Convert ---")
try:
    result = bpy.ops.vrm2gmod.material_convert()
    print(f"Material convert: {result}")
except Exception as e:
    print(f"Material convert error: {e}")

# Step 6: Physics Generate
print("\n--- Step 6: Physics Generate ---")
try:
    result = bpy.ops.vrm2gmod.physics_generate()
    print(f"Physics generate: {result}")
    if result == {'FINISHED'}:
        phys_collection = bpy.data.collections.get("Physics")
        if phys_collection:
            phys_objects = [obj for obj in phys_collection.objects if obj.type == 'MESH']
            phys_path = os.path.join(compile_dir, "physics.smd")
            ok = write_physics_smd(phys_path, armature, phys_objects)
            print(f"Physics SMD: {'OK' if ok else 'FAILED'}")
except Exception as e:
    print(f"Physics generate error: {e}")

# Step 7: QC Generate
print("\n--- Step 7: QC Generate ---")
try:
    result = bpy.ops.vrm2gmod.qc_generate()
    print(f"QC generate: {result}")
    qc_path = os.path.join(compile_dir, f"{model_name}.qc")
    with open(qc_path, 'r') as f:
        qc_content = f.read()
    if '$model "body"' in qc_content:
        print("QC: Uses $model (flex enabled)")
    else:
        print("QC: Uses $bodygroup (no flex)")
    for line in qc_content.split('\n'):
        if 'flexcontroller' in line:
            print(f"  {line.strip()}")
except Exception as e:
    print(f"QC generate error: {e}")

# Save .blend
print("\n--- Save .blend ---")
blend_path = os.path.join(compile_dir, f"{model_name}.blend")
try:
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, copy=True)
    print(f"Saved: {blend_path}")
except Exception as e:
    print(f"Save error: {e}")

# Step 8: Compile
print("\n--- Step 8: studiomdl Compile ---")
from VRM2GmodPlayermodel.utils.studiomdl_compile import compile_model

studiomdl_path = r"R:\SteamLibrary\steamapps\common\GarrysMod\bin\studiomdl.exe"
game_dir = r"R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod"
qc_path = os.path.join(compile_dir, f"{model_name}.qc")

success, log = compile_model(studiomdl_path, qc_path, game_dir)
print(f"Compile: {'SUCCESS' if success else 'FAILED'}")
if not success:
    print(f"Log:\n{log[-3000:]}")
else:
    import shutil
    studiomdl_output = os.path.join(game_dir, "models", "player", model_name)
    for ext in ('.mdl', '.dx90.vtx', '.dx80.vtx', '.sw.vtx', '.vvd', '.phy'):
        src = os.path.join(studiomdl_output, f"{model_name}{ext}")
        if os.path.isfile(src):
            dst = os.path.join(models_dir, f"{model_name}{ext}")
            shutil.copy2(src, dst)
            print(f"  Copied: {model_name}{ext}")

# Generate Lua
print("\n--- Lua Generation ---")
from VRM2GmodPlayermodel.utils.lua_generate import generate_playermodel_lua
lua_dir = os.path.join(output_base, "lua", "autorun")
os.makedirs(lua_dir, exist_ok=True)
lua_path = os.path.join(lua_dir, f"{model_name}_playermodel.lua")
with open(lua_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(generate_playermodel_lua(model_name))
print(f"Lua: {lua_path}")

# Copy to addon
print("\n--- Copy to addon ---")
addon_models = os.path.join(output_base, "models", "player", model_name)
gmod_models = os.path.join(game_dir, "models", "player", model_name)
if os.path.isdir(gmod_models):
    import shutil
    for f in os.listdir(gmod_models):
        src = os.path.join(gmod_models, f)
        dst = os.path.join(addon_models, f)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"  Synced to addon: {f}")

print("\n=== DONE ===")
