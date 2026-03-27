"""Pure Python VTF file writer for Source Engine textures.

Writes VTF v7.2 files in BGRA8888 format (uncompressed) with full mipmap chain
and a DXT1 low-resolution thumbnail.  Matches the VTF layout produced by
VTFCmd.exe / VTFLib so Source Engine loads the texture without errors.

No external dependencies required — works inside Blender's bundled Python.
"""

import math
import os
import struct

# ---------------------------------------------------------------------------
# VTF constants
# ---------------------------------------------------------------------------

IMAGE_FORMAT_BGRA8888 = 12
IMAGE_FORMAT_DXT1 = 13

LOWRES_WIDTH = 16
LOWRES_HEIGHT = 16

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_power_of_2(n: int) -> int:
    """Round up to the next power of 2."""
    if n <= 1:
        return 1
    n -= 1
    n |= n >> 1
    n |= n >> 2
    n |= n >> 4
    n |= n >> 8
    n |= n >> 16
    return n + 1


def _mipmap_count(width: int, height: int) -> int:
    """Number of mipmap levels.  Matches VTFCmd convention
    (``floor(log2(max_dim))``), so the smallest level is 2×2."""
    return int(math.log2(max(width, height)))


def _downsample_2x(pixels: list[tuple[int, int, int, int]],
                   width: int, height: int):
    """2×2 box-filter downsample.  Returns (new_pixels, new_w, new_h)."""
    new_w = max(width // 2, 1)
    new_h = max(height // 2, 1)
    result: list[tuple[int, int, int, int]] = []
    for y in range(new_h):
        for x in range(new_w):
            sx, sy = x * 2, y * 2
            samples = []
            for dy in range(2):
                for dx in range(2):
                    px = min(sx + dx, width - 1)
                    py = min(sy + dy, height - 1)
                    samples.append(pixels[py * width + px])
            r = sum(s[0] for s in samples) // 4
            g = sum(s[1] for s in samples) // 4
            b = sum(s[2] for s in samples) // 4
            a = sum(s[3] for s in samples) // 4
            result.append((r, g, b, a))
    return result, new_w, new_h


def _rgb_to_565(r: int, g: int, b: int) -> int:
    """Pack 8-bit RGB into RGB565."""
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def _make_dxt1_thumbnail(pixels: list[tuple[int, int, int, int]],
                         width: int, height: int) -> bytes:
    """Create a simple DXT1 encoding of *pixels* (width×height RGBA).

    Uses a minimal two-color quantisation per 4×4 block — quality is low
    but perfectly sufficient for the 16×16 embedded thumbnail.
    """
    blocks_w = max(width // 4, 1)
    blocks_h = max(height // 4, 1)
    out = bytearray()

    for by in range(blocks_h):
        for bx in range(blocks_w):
            # Gather 4x4 block
            block: list[tuple[int, int, int]] = []
            for dy in range(4):
                for dx in range(4):
                    px = min(bx * 4 + dx, width - 1)
                    py = min(by * 4 + dy, height - 1)
                    rgba = pixels[py * width + px]
                    block.append((rgba[0], rgba[1], rgba[2]))

            # Find min/max colors
            min_r = min(c[0] for c in block)
            min_g = min(c[1] for c in block)
            min_b = min(c[2] for c in block)
            max_r = max(c[0] for c in block)
            max_g = max(c[1] for c in block)
            max_b = max(c[2] for c in block)

            c0 = _rgb_to_565(max_r, max_g, max_b)
            c1 = _rgb_to_565(min_r, min_g, min_b)

            # Ensure c0 >= c1 for opaque mode
            if c0 < c1:
                c0, c1 = c1, c0
                min_r, max_r = max_r, min_r
                min_g, max_g = max_g, min_g
                min_b, max_b = max_b, min_b
            elif c0 == c1:
                # Uniform block — all indices 0
                out.extend(struct.pack('<HH', c0, c1))
                out.extend(b'\x00\x00\x00\x00')
                continue

            # Build 2-bit lookup table
            # palette: 0=c0, 1=c1, 2=2/3*c0+1/3*c1, 3=1/3*c0+2/3*c1
            palette = [
                (max_r, max_g, max_b),
                (min_r, min_g, min_b),
                ((2 * max_r + min_r + 1) // 3,
                 (2 * max_g + min_g + 1) // 3,
                 (2 * max_b + min_b + 1) // 3),
                ((max_r + 2 * min_r + 1) // 3,
                 (max_g + 2 * min_g + 1) // 3,
                 (max_b + 2 * min_b + 1) // 3),
            ]

            indices = 0
            for i, (cr, cg, cb) in enumerate(block):
                best_idx = 0
                best_dist = 999999
                for pi, (pr, pg, pb) in enumerate(palette):
                    d = (cr - pr) ** 2 + (cg - pg) ** 2 + (cb - pb) ** 2
                    if d < best_dist:
                        best_dist = d
                        best_idx = pi
                indices |= (best_idx << (i * 2))

            out.extend(struct.pack('<HHI', c0, c1, indices))

    return bytes(out)


# ---------------------------------------------------------------------------
# Core writer
# ---------------------------------------------------------------------------


def write_vtf(rgba_pixels: list[tuple[int, int, int, int]],
              width: int, height: int,
              output_path: str,
              is_normal_map: bool = False) -> None:
    """Write a VTF 7.2 file from RGBA pixel data (BGRA8888 format).

    The output file layout matches VTFCmd.exe conventions:
      Header (80 B) → Low-res DXT1 thumbnail → Mipmap data (2×2 … full).

    Args:
        rgba_pixels: (R, G, B, A) tuples, row-major **top-left** origin.
        width:  Must be a power of 2.
        height: Must be a power of 2.
        output_path: Destination ``.vtf`` file path.
        is_normal_map: If *True* the NORMAL texture flag is set.
    """
    assert width > 0 and (width & (width - 1)) == 0, \
        f"Width must be a power of 2, got {width}"
    assert height > 0 and (height & (height - 1)) == 0, \
        f"Height must be a power of 2, got {height}"

    num_mipmaps = _mipmap_count(width, height)

    # Flags — use 0 (same as VTFCmd default).
    # NORMAL is set only for normal maps.
    flags = 0x00000080 if is_normal_map else 0x00000000

    # --- Build mipmap chain (smallest → largest, VTF on-disk order) ---
    # Smallest level is 2×2 (num_mipmaps levels total).
    current_pixels = list(rgba_pixels)
    cur_w, cur_h = width, height
    levels = [(current_pixels, cur_w, cur_h)]

    while cur_w > 2 or cur_h > 2:
        current_pixels, cur_w, cur_h = _downsample_2x(
            current_pixels, cur_w, cur_h)
        levels.append((current_pixels, cur_w, cur_h))

    levels.reverse()  # smallest (2×2) first

    mip_data_list: list[bytes] = []
    for pixels, _w, _h in levels:
        buf = bytearray(_w * _h * 4)
        for i, (r, g, b, a) in enumerate(pixels):
            off = i * 4
            buf[off] = b        # B
            buf[off + 1] = g    # G
            buf[off + 2] = r    # R
            buf[off + 3] = a    # A
        mip_data_list.append(bytes(buf))

    # --- Low-res thumbnail (16×16 DXT1) ---
    # Downsample to 16×16 for thumbnail
    thumb_pixels = list(rgba_pixels)
    tw, th = width, height
    while tw > LOWRES_WIDTH or th > LOWRES_HEIGHT:
        thumb_pixels, tw, th = _downsample_2x(thumb_pixels, tw, th)
    thumbnail_data = _make_dxt1_thumbnail(thumb_pixels, tw, th)

    # --- VTF 7.2 header (80 bytes) ---
    header = bytearray(80)
    struct.pack_into('4s', header, 0, b'VTF\0')       # signature
    struct.pack_into('<II', header, 4, 7, 2)           # version 7.2
    struct.pack_into('<I', header, 12, 80)             # header size
    struct.pack_into('<HH', header, 16, width, height) # dimensions
    struct.pack_into('<I', header, 20, flags)          # flags
    struct.pack_into('<HH', header, 24, 1, 0)         # frames=1, firstFrame=0
    # offset 28: 4 bytes padding (zero)
    # offset 32: reflectivity — use 0,0,0 (like VTFCmd default)
    # offset 44: 4 bytes padding (zero)
    struct.pack_into('<f', header, 48, 1.0)            # bumpmap scale
    struct.pack_into('<I', header, 52, IMAGE_FORMAT_BGRA8888)  # hi-res format
    struct.pack_into('<B', header, 56, num_mipmaps)    # mipmap count
    struct.pack_into('<I', header, 57, IMAGE_FORMAT_DXT1)  # lo-res format
    struct.pack_into('<BB', header, 61,
                     LOWRES_WIDTH, LOWRES_HEIGHT)      # lo-res dims
    struct.pack_into('<H', header, 63, 1)              # depth (v7.2)
    # bytes 65-79: zero padding

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(header)
        f.write(thumbnail_data)
        for mip in mip_data_list:
            f.write(mip)


# ---------------------------------------------------------------------------
# Blender-specific helper
# ---------------------------------------------------------------------------


def png_to_vtf_blender(png_path: str,
                       vtf_path: str,
                       is_normal_map: bool = False,
                       max_size: int = 2048) -> tuple[bool, str]:
    """Convert a PNG file to VTF using Blender's image API.

    Must be called from within Blender (``import bpy`` must work).

    Args:
        png_path: Source PNG image.
        vtf_path: Destination VTF file.
        is_normal_map: Sets NORMAL flag in the VTF.
        max_size: Clamp texture dimensions to this value.

    Returns:
        (success, message) tuple.
    """
    try:
        import bpy  # noqa: F811
    except ImportError:
        return False, "Blender環境外では使用できません"

    if not os.path.isfile(png_path):
        return False, f"入力ファイルが見つかりません: {png_path}"

    img = None
    try:
        img = bpy.data.images.load(png_path)
        width, height = img.size[0], img.size[1]

        if width == 0 or height == 0:
            return False, f"画像サイズが無効です: {width}x{height}"

        # Power-of-2 & clamp
        po2_w = min(_next_power_of_2(width), max_size)
        po2_h = min(_next_power_of_2(height), max_size)

        if po2_w != width or po2_h != height:
            img.scale(po2_w, po2_h)
            width, height = po2_w, po2_h

        # Read pixels (flat RGBA float array, bottom-up in Blender)
        pixels_flat = img.pixels[:]
        n = width * height

        # Convert float → byte RGBA tuples
        raw: list[tuple[int, int, int, int]] = [
            (
                max(0, min(255, int(pixels_flat[i * 4] * 255 + 0.5))),
                max(0, min(255, int(pixels_flat[i * 4 + 1] * 255 + 0.5))),
                max(0, min(255, int(pixels_flat[i * 4 + 2] * 255 + 0.5))),
                max(0, min(255, int(pixels_flat[i * 4 + 3] * 255 + 0.5))),
            )
            for i in range(n)
        ]

        # Blender stores pixels bottom-up → flip to top-down
        flipped: list[tuple[int, int, int, int]] = []
        for y in range(height - 1, -1, -1):
            row_start = y * width
            flipped.extend(raw[row_start:row_start + width])

        write_vtf(flipped, width, height, vtf_path, is_normal_map)

        size_kb = os.path.getsize(vtf_path) / 1024
        return True, f"VTF生成成功: {vtf_path} ({size_kb:.1f} KB)"

    except Exception as e:
        return False, f"VTF変換エラー: {e}"
    finally:
        if img is not None:
            try:
                bpy.data.images.remove(img)
            except Exception:
                pass
