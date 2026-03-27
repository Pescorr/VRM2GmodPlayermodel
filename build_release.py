#!/usr/bin/env python3
"""
VRM2GmodPlayermodel リリースビルドスクリプト
配布用 .zip を生成する。Blender外で実行すること。

Usage:
    python build_release.py
    python build_release.py --version 0.2.0
"""

import argparse
import os
import re
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
ADDON_NAME = "VRM2GmodPlayermodel"

# 配布に含めるファイル/フォルダ
INCLUDE = [
    "__init__.py",
    "preferences.py",
    "blender_manifest.toml",
    "LICENSE",
    "README.md",
    "CHANGELOG.md",
    "batch_convert.py",
    "batch_convert_blend.py",
    "batch_detect_sk.py",
    "operators/",
    "ui/",
    "data/",
    "utils/",
]

# 除外パターン
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".claude",
]


def get_version_from_manifest() -> str:
    """blender_manifest.toml からバージョンを取得"""
    manifest = PROJECT_DIR / "blender_manifest.toml"
    text = manifest.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"(.+?)"', text, re.MULTILINE)
    if match:
        return match.group(1)
    return "0.0.0"


def should_exclude(path: Path) -> bool:
    """除外対象かチェック"""
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path.name.endswith(pattern[1:]):
                return True
        elif pattern in path.parts:
            return True
    return False


def build_zip(version: str) -> Path:
    """配布用 .zip を生成"""
    dist_dir = PROJECT_DIR / "dist"
    dist_dir.mkdir(exist_ok=True)

    zip_name = f"{ADDON_NAME}-v{version}.zip"
    zip_path = dist_dir / zip_name

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in INCLUDE:
            source = PROJECT_DIR / item
            if source.is_file():
                if not should_exclude(source):
                    arcname = f"{ADDON_NAME}/{item}"
                    zf.write(source, arcname)
                    file_count += 1
                    print(f"  + {arcname}")
            elif source.is_dir():
                for root, dirs, files in os.walk(source):
                    root_path = Path(root)
                    # __pycache__ を除外
                    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
                    for f in files:
                        file_path = root_path / f
                        if not should_exclude(file_path):
                            rel = file_path.relative_to(PROJECT_DIR)
                            arcname = f"{ADDON_NAME}/{rel}"
                            zf.write(file_path, arcname)
                            file_count += 1
                            print(f"  + {arcname}")

    size_kb = zip_path.stat().st_size / 1024
    print(f"\n{'='*50}")
    print(f"Build complete: {zip_path}")
    print(f"Files: {file_count}, Size: {size_kb:.1f} KB")
    print(f"{'='*50}")
    return zip_path


def update_version(new_version: str):
    """blender_manifest.toml と __init__.py のバージョンを更新"""
    # blender_manifest.toml
    manifest = PROJECT_DIR / "blender_manifest.toml"
    text = manifest.read_text(encoding="utf-8")
    text = re.sub(
        r'^(version\s*=\s*)"(.+?)"',
        f'\\1"{new_version}"',
        text,
        flags=re.MULTILINE,
    )
    manifest.write_text(text, encoding="utf-8")

    # __init__.py
    init = PROJECT_DIR / "__init__.py"
    text = init.read_text(encoding="utf-8")
    parts = new_version.split(".")
    if len(parts) == 3:
        version_tuple = f"({parts[0]}, {parts[1]}, {parts[2]})"
        text = re.sub(
            r'"version":\s*\(\d+,\s*\d+,\s*\d+\)',
            f'"version": {version_tuple}',
            text,
        )
        init.write_text(text, encoding="utf-8")

    print(f"Version updated to {new_version}")


def main():
    parser = argparse.ArgumentParser(description="Build release .zip")
    parser.add_argument(
        "--version",
        help="Set version (updates manifest and __init__.py)",
    )
    args = parser.parse_args()

    if args.version:
        update_version(args.version)
        version = args.version
    else:
        version = get_version_from_manifest()

    print(f"Building {ADDON_NAME} v{version}")
    print(f"{'='*50}")
    build_zip(version)


if __name__ == "__main__":
    main()
