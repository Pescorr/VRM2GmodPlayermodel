# Blender 5.0 Extension format uses blender_manifest.toml instead of bl_info
# Keep bl_info for backwards compatibility with Blender 4.x legacy addon install
bl_info = {
    "name": "VRM to GMod Playermodel",
    "author": "Pescorr",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > VRM2GMod",
    "description": "Convert VRM models to Garry's Mod playermodels with one click",
    "category": "Import-Export",
}

import bpy

from . import preferences
from .operators import (
    bone_remap,
    mesh_prepare,
    material_convert,
    physics_generate,
    qc_generate,
    convert_full,
    weight_paint,
    flex_detect,
)
from .ui import panel

modules = [
    preferences,
    bone_remap,
    mesh_prepare,
    material_convert,
    physics_generate,
    qc_generate,
    convert_full,
    weight_paint,
    flex_detect,
    panel,
]


def register():
    for mod in modules:
        mod.register()


def unregister():
    for mod in reversed(modules):
        mod.unregister()


if __name__ == "__main__":
    register()
