"""Batch conversion script for Blender command-line execution.

Usage:
    blender --background --python batch_convert.py -- <vrm_path> <model_name> <output_base>
"""

import sys
import os

# Parse arguments after "--"
argv = sys.argv
if "--" in argv:
    args = argv[argv.index("--") + 1:]
else:
    print("ERROR: No arguments provided. Usage: blender --background --python batch_convert.py -- <vrm_path> <model_name> <output_base>")
    sys.exit(1)

if len(args) < 3:
    print("ERROR: Need 3 arguments: <vrm_path> <model_name> <output_base>")
    sys.exit(1)

vrm_path = args[0]
model_name = args[1]
output_base = args[2]

print(f"=== VRM2GmodPlayermodel Batch Convert ===")
print(f"VRM: {vrm_path}")
print(f"Model: {model_name}")
print(f"Output: {output_base}")

import bpy

# --- Step 0: Import VRM ---
print("\n--- Step 0: VRM Import ---")
try:
    bpy.ops.import_scene.vrm(filepath=vrm_path)
    print("VRM import OK")
except Exception as e:
    print(f"VRM import error: {e}")
    sys.exit(1)

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

# --- Step 2.5: A-pose ---
print("\n--- Step 2.5: A-pose Conversion ---")
from VRM2GmodPlayermodel.utils.pose_correction import apply_a_pose
try:
    apply_a_pose(armature, mesh_obj)
    print("A-pose conversion OK")
except Exception as e:
    print(f"A-pose error: {e}")

# --- Detect Shape Keys ---
print("\n--- Shape Key Detection ---")
try:
    result = bpy.ops.vrm2gmod.detect_shape_keys()
    print(f"Shape key detect: {result}")

    # Show detected items
    for item in props.flex_items:
        status = item.flex_target
        print(f"  {item.name} -> {status} (standard={item.is_standard})")

    # Auto-assign all shape keys (recognized → standard, unknown → CUSTOM)
    from VRM2GmodPlayermodel.data.flex_mapping import auto_assign_all
    for item in props.flex_items:
        target, custom_name = auto_assign_all(item.name)
        if target != 'NONE' and item.flex_target == 'NONE':
            item.flex_target = target
            if target == 'CUSTOM':
                item.custom_flex_name = custom_name
            print(f"  AUTO-ASSIGNED: {item.name} -> {target}"
                  + (f" (custom: {custom_name})" if custom_name else ""))

    assigned = sum(1 for item in props.flex_items if item.flex_target != 'NONE')
    print(f"Total: {len(props.flex_items)}, Assigned: {assigned}")
except Exception as e:
    print(f"Shape key detect error: {e}")

# --- Steps 3-8: Export Pipeline ---
print("\n--- Steps 3-8: Export Pipeline ---")

compile_dir = os.path.join(output_base, "compile")
models_dir = os.path.join(output_base, "models", "player", model_name)
materials_dir = os.path.join(output_base, "materials", "models", "player", model_name)
os.makedirs(compile_dir, exist_ok=True)
os.makedirs(models_dir, exist_ok=True)
os.makedirs(materials_dir, exist_ok=True)

# Step 3: SMD Export
print("\n--- Step 3: SMD Export ---")
from VRM2GmodPlayermodel.utils.smd_export import (
    write_reference_smd, write_physics_smd,
    write_proportions_smd, write_reference_skeleton_smd,
    write_flex_vta,
)

smd_path = os.path.join(compile_dir, f"{model_name}.smd")
ok = write_reference_smd(smd_path, armature, mesh_obj)
print(f"Reference SMD: {'OK' if ok else 'FAILED'} ({os.path.getsize(smd_path) / 1024:.0f} KB)")

# Step 3.5: VTA Export
print("\n--- Step 3.5: VTA Export ---")
vta_path = os.path.join(compile_dir, f"{model_name}_flex.vta")
try:
    ok, flex_names = write_flex_vta(vta_path, armature, mesh_obj, props.flex_items)
    if ok:
        print(f"VTA export: OK ({len(flex_names)} flexes, {os.path.getsize(vta_path) / 1024:.0f} KB)")
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

    # Verify QC content
    qc_path = os.path.join(compile_dir, f"{model_name}.qc")
    with open(qc_path, 'r') as f:
        qc_content = f.read()
    if '$model' in qc_content:
        print("QC: Uses $model (flex enabled)")
    elif '$bodygroup' in qc_content:
        print("QC: Uses $bodygroup (no flex)")

    # Show flexcontroller lines
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
    # Copy compiled files
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

print("\n=== DONE ===")
