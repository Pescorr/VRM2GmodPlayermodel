"""Headless VRM→GMod conversion test — imports .vrm directly.

Usage:
    blender --background --python test_vrm_direct.py -- <vrm_file> <model_name> <output_dir> [<studiomdl_path>]

This script:
1. Imports a .vrm file using the VRM addon
2. Registers the VRM2GmodPlayermodel addon
3. Configures settings and runs the full conversion pipeline
4. Optionally compiles with studiomdl
5. Reports output files and bone structure
"""

import sys
import os
import traceback
import time

# Parse arguments after '--'
argv = sys.argv
if "--" in argv:
    args = argv[argv.index("--") + 1:]
else:
    args = []

if len(args) < 3:
    print("=" * 60)
    print("ERROR: Missing arguments")
    print("Usage: blender --background --python test_vrm_direct.py -- "
          "<vrm_file> <model_name> <output_dir> [<studiomdl_path>]")
    print("=" * 60)
    sys.exit(1)

VRM_FILE = args[0]
MODEL_NAME = args[1]
OUTPUT_DIR = args[2]
STUDIOMDL_PATH = args[3] if len(args) > 3 else ""

print("=" * 60)
print("VRM2GmodPlayermodel - Direct VRM Test")
print("=" * 60)
print(f"VRM file:      {VRM_FILE}")
print(f"Model name:    {MODEL_NAME}")
print(f"Output dir:    {OUTPUT_DIR}")
print(f"studiomdl:     {STUDIOMDL_PATH}")
print(f"Python:        {sys.version}")
print("=" * 60)

import bpy

# ----------------------------------------------------------------
# Step 1: Import VRM file
# ----------------------------------------------------------------
print("\n[1/6] Importing VRM file...")
try:
    # Try VRM addon import (Blender 4.x/5.x extension)
    result = bpy.ops.import_scene.vrm(filepath=VRM_FILE)
    print(f"  OK - VRM import result: {result}")
except AttributeError:
    print("  VRM addon not available via import_scene.vrm")
    print("  FAILED: VRM addon is required. Install it via Blender Extensions.")
    sys.exit(1)
except Exception as e:
    print(f"  FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Print scene info
print(f"  Objects in scene: {len(bpy.context.view_layer.objects)}")
for obj in bpy.context.view_layer.objects:
    try:
        print(f"    - {obj.name} ({obj.type})"
              f"{' [' + str(len(obj.data.bones)) + ' bones]' if obj.type == 'ARMATURE' else ''}"
              f"{' [' + str(len(obj.data.vertices)) + ' verts]' if obj.type == 'MESH' else ''}")
    except (ReferenceError, AttributeError):
        continue

# Find armature
armature = None
for obj in bpy.context.view_layer.objects:
    try:
        if obj.type == 'ARMATURE':
            armature = obj
            break
    except ReferenceError:
        continue

if armature:
    print(f"\n  Armature: {armature.name} ({len(armature.data.bones)} bones)")
    # Print VRM-related bone info
    vrm_ext = getattr(armature.data, 'vrm_addon_extension', None)
    if vrm_ext:
        print("  VRM metadata: FOUND")
        humanoid = getattr(vrm_ext, 'vrm1', None)
        if humanoid:
            hb = getattr(humanoid, 'humanoid', None)
            if hb:
                hbones = getattr(hb, 'human_bones', None)
                if hbones:
                    # Count mapped bones
                    mapped = 0
                    for attr_name in dir(hbones):
                        bone_spec = getattr(hbones, attr_name, None)
                        if hasattr(bone_spec, 'node') and hasattr(bone_spec.node, 'bone_name'):
                            if bone_spec.node.bone_name:
                                mapped += 1
                    print(f"  VRM humanoid bones mapped: {mapped}")
    else:
        print("  VRM metadata: NOT FOUND (will use pattern guessing)")
else:
    print("  WARNING: No armature found!")
    sys.exit(1)

# ----------------------------------------------------------------
# Step 2: Enable VRM2GmodPlayermodel addon
# ----------------------------------------------------------------
print("\n[2/6] Enabling VRM2GmodPlayermodel addon...")
try:
    # Try standard addon enable
    bpy.ops.preferences.addon_enable(module="VRM2GmodPlayermodel")
    print("  OK - Addon enabled via preferences")
except Exception as e:
    print(f"  Standard enable failed: {e}")
    print("  Trying manual registration...")
    try:
        import importlib
        addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent_dir = os.path.dirname(addon_path)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        import VRM2GmodPlayermodel
        importlib.reload(VRM2GmodPlayermodel)
        VRM2GmodPlayermodel.register()
        print("  OK - Manual registration succeeded")
    except Exception as e2:
        print(f"  FAILED manual registration: {e2}")
        traceback.print_exc()
        sys.exit(1)

# ----------------------------------------------------------------
# Step 3: Configure settings
# ----------------------------------------------------------------
print("\n[3/6] Configuring settings...")
try:
    props = bpy.context.scene.vrm2gmod
    props.model_name = MODEL_NAME
    props.output_path = OUTPUT_DIR
    props.auto_compile = bool(STUDIOMDL_PATH)
    props.copy_to_gmod = False
    print(f"  model_name:    {props.model_name}")
    print(f"  output_path:   {props.output_path}")
    print(f"  auto_compile:  {props.auto_compile}")

    # Set studiomdl path in addon preferences
    if STUDIOMDL_PATH:
        try:
            addon_prefs = bpy.context.preferences.addons["VRM2GmodPlayermodel"].preferences
            addon_prefs.studiomdl_path = STUDIOMDL_PATH
            print(f"  studiomdl:     {addon_prefs.studiomdl_path}")
        except KeyError:
            print("  WARNING: Could not set studiomdl path in addon preferences")

    print("  OK")
except Exception as e:
    print(f"  FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# ----------------------------------------------------------------
# Step 4: Run conversion pipeline
# ----------------------------------------------------------------
print("\n[4/6] Running full conversion pipeline...")
print("-" * 40)
start_time = time.time()
try:
    result = bpy.ops.vrm2gmod.convert_full()
    elapsed = time.time() - start_time
    print("-" * 40)
    print(f"  Result: {result}")
    print(f"  Time:   {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - start_time
    print("-" * 40)
    print(f"  EXCEPTION after {elapsed:.1f}s: {e}")
    traceback.print_exc()

# ----------------------------------------------------------------
# Step 5: Report output files
# ----------------------------------------------------------------
print("\n[5/6] Output files:")

# Compile directory
compile_dir = os.path.join(OUTPUT_DIR, "compile")
if os.path.isdir(compile_dir):
    total_size = 0
    for root, dirs, files in os.walk(compile_dir):
        for f in sorted(files):
            fpath = os.path.join(root, f)
            size_kb = os.path.getsize(fpath) / 1024
            total_size += size_kb
            rel = os.path.relpath(fpath, compile_dir)
            print(f"  compile/{rel:40s} {size_kb:8.1f} KB")
    print(f"  {'TOTAL':49s} {total_size:8.1f} KB")
else:
    print(f"  WARNING: Compile directory not found: {compile_dir}")

# Models directory (compiled output)
models_dir = os.path.join(OUTPUT_DIR, "models")
if os.path.isdir(models_dir):
    print(f"\n  Compiled models:")
    for root, dirs, files in os.walk(models_dir):
        for f in sorted(files):
            fpath = os.path.join(root, f)
            size_kb = os.path.getsize(fpath) / 1024
            rel = os.path.relpath(fpath, OUTPUT_DIR)
            print(f"  {rel:48s} {size_kb:8.1f} KB")

# Materials directory
mats_dir = os.path.join(OUTPUT_DIR, "materials")
if os.path.isdir(mats_dir):
    print(f"\n  Materials:")
    for root, dirs, files in os.walk(mats_dir):
        for f in sorted(files):
            fpath = os.path.join(root, f)
            size_kb = os.path.getsize(fpath) / 1024
            rel = os.path.relpath(fpath, OUTPUT_DIR)
            print(f"  {rel:48s} {size_kb:8.1f} KB")

# ----------------------------------------------------------------
# Step 6: Print final bone structure
# ----------------------------------------------------------------
print("\n[6/6] Post-conversion skeleton:")
armature = None
for obj in bpy.context.view_layer.objects:
    try:
        if obj.type == 'ARMATURE':
            armature = obj
            break
    except ReferenceError:
        continue

if armature:
    print(f"  Armature: {armature.name} ({len(armature.data.bones)} bones)")
    valve_count = 0
    non_valve = []
    for bone in armature.data.bones:
        parent = bone.parent.name if bone.parent else "(root)"
        if bone.name.startswith("ValveBiped."):
            valve_count += 1
        else:
            non_valve.append(bone.name)
        print(f"    {bone.name:50s} parent: {parent}")

    print(f"\n  ValveBiped bones: {valve_count}")
    if non_valve:
        print(f"  Non-ValveBiped bones remaining: {len(non_valve)}")
        for name in non_valve:
            print(f"    WARNING: {name}")

# Verify critical QC files
print("\n  QC file check:")
qc_path = os.path.join(compile_dir, f"{MODEL_NAME}.qc")
if os.path.isfile(qc_path):
    with open(qc_path, 'r') as f:
        qc_content = f.read()
    print(f"    QC file: OK ({len(qc_content)} bytes)")
    # Check critical elements
    checks = [
        ("$modelname", "$modelname" in qc_content),
        ("$includemodel", "$includemodel" in qc_content),
        ("Proportion Trick", "proportions" in qc_content and "predelta" in qc_content),
        ("$collisionjoints", "$collisionjoints" in qc_content),
        ("$ikchain", "$ikchain" in qc_content),
        ("$bonemerge", "$bonemerge" in qc_content),
        ("$hboxset", "$hboxset" in qc_content),
    ]
    for name, ok in checks:
        print(f"    {name:25s} {'OK' if ok else 'MISSING!'}")
else:
    print(f"    WARNING: QC file not found: {qc_path}")

print("\n" + "=" * 60)
print("Test complete.")
print("=" * 60)
