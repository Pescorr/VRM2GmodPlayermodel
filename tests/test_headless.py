"""Headless Blender test script for VRM2GmodPlayermodel addon.

Usage:
    blender --background --python test_headless.py -- <blend_file> <model_name> <output_dir>

This script:
1. Opens the specified .blend file
2. Registers the VRM2GmodPlayermodel addon
3. Configures addon settings (model_name, output_path, studiomdl path)
4. Runs the full conversion pipeline
5. Prints detailed logs for debugging
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
    print("Usage: blender --background --python test_headless.py -- <blend_file> <model_name> <output_dir>")
    print("=" * 60)
    sys.exit(1)

BLEND_FILE = args[0]
MODEL_NAME = args[1]
OUTPUT_DIR = args[2]
STUDIOMDL_PATH = args[3] if len(args) > 3 else ""

print("=" * 60)
print("VRM2GmodPlayermodel - Headless Test")
print("=" * 60)
print(f"Blend file:    {BLEND_FILE}")
print(f"Model name:    {MODEL_NAME}")
print(f"Output dir:    {OUTPUT_DIR}")
print(f"studiomdl:     {STUDIOMDL_PATH}")
print(f"Python:        {sys.version}")
print("=" * 60)

import bpy

# ----------------------------------------------------------------
# Step 1: Open blend file
# ----------------------------------------------------------------
print("\n[1/5] Opening blend file...")
try:
    bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)
    print(f"  OK - Loaded: {bpy.data.filepath}")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

# Print scene info
print(f"  Objects in scene: {len(bpy.context.view_layer.objects)}")
for obj in bpy.context.view_layer.objects:
    try:
        print(f"    - {obj.name} ({obj.type})")
    except ReferenceError:
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
    print(f"  Armature found: {armature.name} ({len(armature.data.bones)} bones)")
else:
    print("  WARNING: No armature found!")

# ----------------------------------------------------------------
# Step 2: Enable addon
# ----------------------------------------------------------------
print("\n[2/5] Enabling VRM2GmodPlayermodel addon...")
try:
    bpy.ops.preferences.addon_enable(module="VRM2GmodPlayermodel")
    print("  OK - Addon enabled")
except Exception as e:
    print(f"  FAILED to enable addon: {e}")
    print("  Trying manual registration...")
    try:
        # Fallback: import and register manually
        import importlib
        addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if addon_path not in sys.path:
            sys.path.insert(0, os.path.dirname(addon_path))
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
print("\n[3/5] Configuring addon settings...")
try:
    props = bpy.context.scene.vrm2gmod
    props.model_name = MODEL_NAME
    props.output_path = OUTPUT_DIR
    props.auto_compile = False  # We'll compile manually for better logging
    props.copy_to_gmod = False
    print(f"  model_name:    {props.model_name}")
    print(f"  output_path:   {props.output_path}")
    print(f"  auto_compile:  {props.auto_compile}")
    print(f"  copy_to_gmod:  {props.copy_to_gmod}")

    # Set studiomdl path in addon preferences
    if STUDIOMDL_PATH:
        addon_prefs = bpy.context.preferences.addons["VRM2GmodPlayermodel"].preferences
        addon_prefs.studiomdl_path = STUDIOMDL_PATH
        print(f"  studiomdl:     {addon_prefs.studiomdl_path}")

    print("  OK - Settings configured")
except Exception as e:
    print(f"  FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# ----------------------------------------------------------------
# Step 4: Run conversion
# ----------------------------------------------------------------
print("\n[4/5] Running full conversion pipeline...")
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
print("\n[5/5] Output files:")
compile_dir = os.path.join(OUTPUT_DIR, "compile")
if os.path.isdir(compile_dir):
    for f in sorted(os.listdir(compile_dir)):
        fpath = os.path.join(compile_dir, f)
        if os.path.isfile(fpath):
            size_kb = os.path.getsize(fpath) / 1024
            print(f"  {f:40s} {size_kb:8.1f} KB")
else:
    print(f"  Compile directory not found: {compile_dir}")

# Also list armature bones after conversion
armature = None
for obj in bpy.context.view_layer.objects:
    try:
        if obj.type == 'ARMATURE':
            armature = obj
            break
    except ReferenceError:
        continue

if armature:
    print(f"\n  Bones after conversion ({len(armature.data.bones)}):")
    for bone in armature.data.bones:
        parent = bone.parent.name if bone.parent else "(root)"
        print(f"    {bone.name:50s} parent: {parent}")

print("\n" + "=" * 60)
print("Test complete.")
print("=" * 60)
