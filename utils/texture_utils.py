"""Texture utility functions for material conversion pipeline.

Provides:
- Nearby directory search for missing textures
- Solid-color PNG generation for materials without textures
- Base color extraction from Blender material nodes
- Texture status checking for UI display
"""

import os
import struct
import zlib

import bpy


# ---------------------------------------------------------------------------
# Nearby directory search
# ---------------------------------------------------------------------------


def search_texture_nearby(image, source_file=None):
    """Search for a missing texture file in nearby directories.

    When Blender loses track of a texture's file path (common with VRM imports
    or moved .blend files), this function searches common locations where the
    texture might exist.

    Parameters
    ----------
    image : bpy.types.Image
        The Blender image object with a (possibly invalid) filepath.
    source_file : str or None
        Path to the source VRM/blend file.  Used to determine search roots.

    Returns
    -------
    str or None
        Absolute path to the found texture file, or None if not found.
    """
    # Collect candidate filenames to search for
    candidate_names = _build_candidate_names(image)
    if not candidate_names:
        return None

    # Collect directories to search
    search_dirs = _build_search_dirs(image, source_file)
    if not search_dirs:
        return None

    # Search
    for search_dir in search_dirs:
        for name in candidate_names:
            candidate = os.path.join(search_dir, name)
            if os.path.isfile(candidate):
                return candidate

    return None


def _build_candidate_names(image):
    """Build a list of candidate filenames from an image object."""
    names = []

    # From the image filepath
    img_filepath = bpy.path.abspath(image.filepath) if image.filepath else ""
    if img_filepath:
        filename = os.path.basename(img_filepath)
        names.append(filename)
        base, ext = os.path.splitext(filename)
        if ext.lower() in ('.png', '.jpg', '.jpeg', '.tga', '.bmp'):
            for alt_ext in ('.png', '.jpg', '.jpeg', '.tga', '.bmp'):
                alt = f"{base}{alt_ext}"
                if alt != filename and alt not in names:
                    names.append(alt)

    # From the image name (Blender internal name)
    img_name = image.name
    if img_name and img_name not in names:
        _base, _ext = os.path.splitext(img_name)
        if _ext.lower() in ('.png', '.jpg', '.jpeg', '.tga', '.bmp'):
            names.append(img_name)
        elif not _ext:
            # Try common extensions
            for ext in ('.png', '.jpg', '.jpeg', '.tga'):
                names.append(f"{img_name}{ext}")

    return names


def _build_search_dirs(image, source_file=None):
    """Build a list of directories to search for textures."""
    search_dirs = []

    def _add_dir(d):
        if d and os.path.isdir(d) and d not in search_dirs:
            search_dirs.append(d)

    # 1. Directory of the image's recorded filepath
    img_filepath = bpy.path.abspath(image.filepath) if image.filepath else ""
    if img_filepath:
        _add_dir(os.path.dirname(img_filepath))

    # 2. Source file directory and texture subdirectories
    if source_file and os.path.isfile(source_file):
        src_dir = os.path.dirname(source_file)
        _add_dir(src_dir)
        for subdir in ('textures', 'tex', 'images', 'texture', 'img'):
            _add_dir(os.path.join(src_dir, subdir))
        parent = os.path.dirname(src_dir)
        if parent:
            _add_dir(parent)
            for subdir in ('textures', 'tex', 'images'):
                _add_dir(os.path.join(parent, subdir))

    # 3. Current .blend file directory
    blend_path = bpy.data.filepath
    if blend_path:
        blend_dir = os.path.dirname(blend_path)
        _add_dir(blend_dir)
        _add_dir(os.path.join(blend_dir, "textures"))

    return search_dirs


# ---------------------------------------------------------------------------
# Base color extraction
# ---------------------------------------------------------------------------


def extract_base_color(material):
    """Extract the base color from a Blender material's shader nodes.

    Checks Principled BSDF's Base Color default value and MToon group nodes.

    Parameters
    ----------
    material : bpy.types.Material

    Returns
    -------
    tuple of (float, float, float, float) or None
        RGBA color in 0.0–1.0 range, or None if not extractable.
    """
    if not material or not material.use_nodes:
        return None

    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            base_input = node.inputs.get('Base Color')
            if not base_input:
                continue

            if not base_input.is_linked:
                val = base_input.default_value
                # Also factor in alpha
                alpha_input = node.inputs.get('Alpha')
                alpha = 1.0
                if alpha_input and not alpha_input.is_linked:
                    alpha = alpha_input.default_value
                return (val[0], val[1], val[2], alpha)

            # Follow link to RGB node
            linked = base_input.links[0].from_node
            if linked.type == 'RGB':
                val = linked.outputs[0].default_value
                return (val[0], val[1], val[2],
                        val[3] if len(val) > 3 else 1.0)

        elif node.type == 'GROUP':
            # MToon shader group — look for color inputs
            for inp in node.inputs:
                name_lower = inp.name.lower()
                if inp.type == 'RGBA' and not inp.is_linked:
                    if ('color' in name_lower or 'lit' in name_lower
                            or 'base' in name_lower):
                        val = inp.default_value
                        return (val[0], val[1], val[2],
                                val[3] if len(val) > 3 else 1.0)

    return None


# ---------------------------------------------------------------------------
# Solid-color PNG generation (pure Python — no external dependencies)
# ---------------------------------------------------------------------------


def generate_solid_color_png(color_rgba, output_path, size=4):
    """Generate a small solid-color PNG file.

    Parameters
    ----------
    color_rgba : tuple of (float, float, float, float)
        RGBA color in 0.0–1.0 range.
    output_path : str
        Destination PNG path.
    size : int
        Width and height of the image (default 4).

    Returns
    -------
    bool
        True on success.
    """
    try:
        r = max(0, min(255, int(color_rgba[0] * 255 + 0.5)))
        g = max(0, min(255, int(color_rgba[1] * 255 + 0.5)))
        b = max(0, min(255, int(color_rgba[2] * 255 + 0.5)))
        a = max(0, min(255, int(color_rgba[3] * 255 + 0.5)))

        # Build raw image data (RGBA, with filter byte per row)
        raw_data = bytearray()
        for _ in range(size):
            raw_data.append(0)  # filter type: None
            for _ in range(size):
                raw_data.extend((r, g, b, a))

        signature = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', size, size,
                                8,   # bit depth
                                6,   # color type: RGBA
                                0, 0, 0)
        ihdr = _png_chunk(b'IHDR', ihdr_data)
        idat = _png_chunk(b'IDAT', zlib.compress(bytes(raw_data), 9))
        iend = _png_chunk(b'IEND', b'')

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(signature + ihdr + idat + iend)

        return True
    except Exception:
        return False


def _png_chunk(chunk_type, data):
    """Build a PNG chunk: length + type + data + CRC32."""
    body = chunk_type + data
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + body + struct.pack('>I', crc)


# ---------------------------------------------------------------------------
# Texture status check (for UI display)
# ---------------------------------------------------------------------------


def check_texture_status(material):
    """Check the texture availability status of a material.

    Used by the scan operator to populate the material overview panel.

    Parameters
    ----------
    material : bpy.types.Material

    Returns
    -------
    tuple of (str, tuple or None)
        (status, base_color)

        status is one of:
          'OK'      — image texture found and available
          'MISSING' — image texture referenced but data unavailable
          'SOLID'   — no image texture; solid-color fallback available

        base_color is (r, g, b, a) float tuple when status is 'SOLID',
        None otherwise.
    """
    if not material or not material.use_nodes:
        color = extract_base_color(material) or (0.8, 0.8, 0.8, 1.0)
        return ('SOLID', color)

    # Check Principled BSDF and MToon shader for image textures
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            result = _check_principled_texture(node)
            if result is not None:
                return result

        elif node.type == 'GROUP' and node.node_tree:
            result = _check_mtoon_texture(node)
            if result is not None:
                return result

    # No image texture found — solid-color material
    color = extract_base_color(material) or (0.8, 0.8, 0.8, 1.0)
    return ('SOLID', color)


def _check_principled_texture(bsdf_node):
    """Check if Principled BSDF has an available base color texture.

    Returns (status, color) or None if no image input found.
    """
    base_input = bsdf_node.inputs.get('Base Color')
    if not base_input or not base_input.is_linked:
        return None  # No image linked — caller will handle as SOLID

    linked = base_input.links[0].from_node
    img_node = _find_image_node_recursive(linked)
    if not img_node or not img_node.image:
        return None

    return _check_image_availability(img_node.image)


def _check_mtoon_texture(group_node):
    """Check MToon shader group for available base texture.

    Returns (status, color) or None if no relevant texture found.
    """
    for inner_node in group_node.node_tree.nodes:
        if inner_node.type != 'TEX_IMAGE' or not inner_node.image:
            continue
        label = (inner_node.label or inner_node.name).lower()
        if 'base' in label or 'main' in label or 'lit' in label:
            return _check_image_availability(inner_node.image)
    return None


def _check_image_availability(image):
    """Check whether an image's pixel data can be accessed.

    Returns ('OK', None) or ('MISSING', None).
    """
    if image.has_data:
        return ('OK', None)
    if image.packed_file:
        return ('OK', None)  # Can be unpacked during conversion
    filepath = bpy.path.abspath(image.filepath) if image.filepath else ""
    if filepath and os.path.isfile(filepath):
        return ('OK', None)
    return ('MISSING', None)


def _find_image_node_recursive(node):
    """Recursively follow node links to find an image texture node."""
    if node.type == 'TEX_IMAGE':
        return node
    for input_socket in node.inputs:
        if input_socket.is_linked:
            result = _find_image_node_recursive(
                input_socket.links[0].from_node)
            if result:
                return result
    return None
