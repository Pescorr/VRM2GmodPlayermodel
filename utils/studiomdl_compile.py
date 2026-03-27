"""studiomdl compiler wrapper."""

import os
import subprocess


def compile_model(studiomdl_path: str, qc_path: str,
                  game_dir: str = "") -> tuple[bool, str]:
    """Compile a QC file into MDL using studiomdl.exe.

    Args:
        studiomdl_path: Path to studiomdl.exe
        qc_path: Path to the .qc file to compile
        game_dir: Optional game directory for -game parameter

    Returns:
        Tuple of (success: bool, output_log: str)
    """
    if not os.path.isfile(studiomdl_path):
        return False, f"studiomdl.exe が見つかりません: {studiomdl_path}"

    if not os.path.isfile(qc_path):
        return False, f"QCファイルが見つかりません: {qc_path}"

    cmd = [studiomdl_path]

    if game_dir:
        cmd.extend(["-game", game_dir])

    # -nop4 disables Perforce integration
    cmd.append("-nop4")
    cmd.append(qc_path)

    try:
        # Use encoding='utf-8' with errors='replace' to handle
        # studiomdl output containing non-UTF-8 characters
        # (e.g. Japanese filesystem paths in addon loading messages).
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120,
            cwd=os.path.dirname(qc_path),
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = stdout + "\n" + stderr
        success = result.returncode == 0

        if not success:
            # Check for common errors
            if "can't find bone" in output.lower():
                output += "\n[ヒント] ボーン名が見つかりません。ボーンリマップが正しく実行されたか確認してください。"
            elif "material" in output.lower() and "not found" in output.lower():
                output += "\n[ヒント] マテリアルが見つかりません。VMTファイルが正しく生成されたか確認してください。"

        return success, output

    except FileNotFoundError:
        return False, f"studiomdl.exe を実行できません: {studiomdl_path}"
    except subprocess.TimeoutExpired:
        return False, "studiomdl タイムアウト（120秒）"
