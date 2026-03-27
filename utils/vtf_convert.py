"""VTFCmd wrapper for PNG → VTF texture conversion."""

import os
import subprocess
from pathlib import Path


def convert_to_vtf(vtfcmd_path: str, input_path: str, output_dir: str,
                   is_normal_map: bool = False) -> tuple[bool, str]:
    """Convert a PNG/TGA image to VTF format using VTFCmd.exe.

    Args:
        vtfcmd_path: Path to VTFCmd.exe
        input_path: Path to input image file
        output_dir: Directory to place the output VTF file
        is_normal_map: If True, adds normal map conversion flags

    Returns:
        Tuple of (success: bool, message: str)
    """
    if not os.path.isfile(vtfcmd_path):
        return False, f"VTFCmd.exe が見つかりません: {vtfcmd_path}"

    if not os.path.isfile(input_path):
        return False, f"入力ファイルが見つかりません: {input_path}"

    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        vtfcmd_path,
        "-file", input_path,
        "-output", output_dir,
        "-format", "DXT5" if not is_normal_map else "DXT5",
        "-flag", "POINTSAMPLE",
        "-flag", "NOLOD",
    ]

    if is_normal_map:
        cmd.extend(["-flag", "NORMAL"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            vtf_name = Path(input_path).stem + ".vtf"
            vtf_path = os.path.join(output_dir, vtf_name)
            if os.path.isfile(vtf_path):
                return True, f"VTF変換成功: {vtf_path}"
            else:
                return True, f"VTFCmd完了（出力確認: {output_dir}）"
        else:
            return False, f"VTFCmd エラー: {result.stderr or result.stdout}"

    except FileNotFoundError:
        return False, f"VTFCmd.exe を実行できません: {vtfcmd_path}"
    except subprocess.TimeoutExpired:
        return False, "VTFCmd タイムアウト（60秒）"


def batch_convert_to_vtf(vtfcmd_path: str, input_dir: str, output_dir: str,
                         normal_map_suffix: str = "_n") -> tuple[int, int, list[str]]:
    """Batch convert all PNG/TGA files in a directory to VTF.

    Args:
        vtfcmd_path: Path to VTFCmd.exe
        input_dir: Directory containing input images
        output_dir: Directory to place output VTF files
        normal_map_suffix: Suffix to identify normal maps (e.g., "_n")

    Returns:
        Tuple of (success_count, fail_count, error_messages)
    """
    success = 0
    fail = 0
    errors = []

    for filename in os.listdir(input_dir):
        ext = Path(filename).suffix.lower()
        if ext not in ('.png', '.tga', '.bmp', '.jpg', '.jpeg'):
            continue

        input_path = os.path.join(input_dir, filename)
        stem = Path(filename).stem
        is_normal = stem.endswith(normal_map_suffix)

        ok, msg = convert_to_vtf(vtfcmd_path, input_path, output_dir, is_normal)
        if ok:
            success += 1
        else:
            fail += 1
            errors.append(msg)

    return success, fail, errors
