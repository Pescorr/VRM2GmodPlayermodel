"""Shared material naming module — single source of truth.

Both material_convert.py (VMT/VTF generation) and smd_export.py (SMD triangle
material references) import from this module to guarantee identical name mapping.
"""

import re
from collections import Counter

import bpy


def sanitize_name(name: str) -> str:
    """Sanitize a name for use as a Source Engine material/texture name.

    Replaces non-alphanumeric characters with underscores, removes leading
    underscores/numbers, and lowercases the result.
    """
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    sanitized = re.sub(r'^[_0-9]+', '', sanitized)
    return sanitized.lower() or "material"


def collect_materials_ordered(
    mesh_objects: list[bpy.types.Object],
) -> list[bpy.types.Material]:
    """Collect unique materials from mesh objects in deterministic slot order.

    This is the canonical ordering used by both material_convert and smd_export.
    The order is: iterate meshes in list order, then material slots in slot order,
    skipping duplicates (first occurrence wins).
    """
    seen = set()
    materials = []
    for obj in mesh_objects:
        for slot in obj.material_slots:
            if slot.material and slot.material not in seen:
                seen.add(slot.material)
                materials.append(slot.material)
    return materials


def build_material_name_map(
    materials: list[bpy.types.Material],
    model_name: str = "",
    naming_mode: str = "SEQUENTIAL",
) -> dict[str, str]:
    """Build a mapping from Blender material name to unique Source Engine safe name.

    Parameters
    ----------
    materials : list[bpy.types.Material]
        Ordered list of materials (from collect_materials_ordered).
    model_name : str
        Model name used as prefix for SEQUENTIAL mode.
    naming_mode : str
        "SEQUENTIAL" — mat_00, mat_01, ... (default, recommended)
        "SANITIZE"   — sanitize+dedup (legacy behavior)

    Returns
    -------
    dict[str, str]
        Mapping from Blender material name → unique safe name.
        Keyed by material.name (string) for compatibility with smd_export.
    """
    if naming_mode == "SEQUENTIAL":
        return _sequential_names(materials, model_name)
    else:
        return _sanitize_names(materials)


def _sequential_names(
    materials: list[bpy.types.Material],
    model_name: str,
) -> dict[str, str]:
    """Generate sequential numbered names: {prefix}_00, {prefix}_01, ..."""
    prefix = sanitize_name(model_name) if model_name else "mat"
    # Dynamic zero-padding width
    width = max(2, len(str(len(materials) - 1))) if materials else 2
    result = {}
    for i, mat in enumerate(materials):
        result[mat.name] = f"{prefix}_{i:0{width}d}"
    return result


def _sanitize_names(
    materials: list[bpy.types.Material],
) -> dict[str, str]:
    """Legacy behavior: sanitize names with collision detection."""
    # First pass: sanitize all names
    raw_names = {}
    for mat in materials:
        raw_names[mat.name] = sanitize_name(mat.name)

    # Detect collisions
    name_counts = Counter(raw_names.values())
    collision_names = {n for n, c in name_counts.items() if c > 1}

    if not collision_names:
        return raw_names

    # Second pass: append index to colliding names
    collision_counters = {n: 0 for n in collision_names}
    result = {}
    for mat_name in raw_names:
        base = raw_names[mat_name]
        if base in collision_names:
            result[mat_name] = f"{base}_{collision_counters[base]}"
            collision_counters[base] += 1
        else:
            result[mat_name] = base

    return result
