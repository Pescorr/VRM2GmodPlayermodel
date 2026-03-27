#!/usr/bin/env python3
"""
開発ディレクトリ → Blender 5.0/5.1 アドオンフォルダ同期スクリプト

Usage:
    python tools/sync_addon.py          # 全バージョンに同期
    python tools/sync_addon.py --dry    # プレビュー（コピーしない）
    python tools/sync_addon.py --5.1    # 5.1のみ同期
"""

import argparse
import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
ADDON_NAME = "VRM2GmodPlayermodel"

BLENDER_ADDON_DIRS = {
    "5.0": Path.home() / "AppData/Roaming/Blender Foundation/Blender/5.0/scripts/addons" / ADDON_NAME,
    "5.1": Path.home() / "AppData/Roaming/Blender Foundation/Blender/5.1/scripts/addons" / ADDON_NAME,
}

# 同期するコアファイル/フォルダ（配布物と同じ）
SYNC_ITEMS = [
    "__init__.py",
    "preferences.py",
    "blender_manifest.toml",
    "operators",
    "ui",
    "data",
    "utils",
]

# __pycache__ 等を除外
EXCLUDE_DIRS = {"__pycache__", ".git", ".claude", "dist", "test_output", "reference"}


def sync_to(target_dir: Path, dry_run: bool = False):
    """PROJECT_DIR の SYNC_ITEMS を target_dir にコピー"""
    if not target_dir.parent.exists():
        print(f"  SKIP: parent does not exist: {target_dir.parent}")
        return 0

    copied = 0
    for item_name in SYNC_ITEMS:
        src = PROJECT_DIR / item_name
        dst = target_dir / item_name

        if src.is_file():
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            copied += 1
            print(f"  {'[DRY] ' if dry_run else ''}COPY {item_name}")

        elif src.is_dir():
            for root_path in src.rglob("*"):
                if root_path.is_file() and not any(
                    ex in root_path.parts for ex in EXCLUDE_DIRS
                ):
                    rel = root_path.relative_to(PROJECT_DIR)
                    dst_file = target_dir / rel
                    if not dry_run:
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(root_path, dst_file)
                    copied += 1
                    print(f"  {'[DRY] ' if dry_run else ''}COPY {rel}")

    return copied


def main():
    parser = argparse.ArgumentParser(description="Sync addon to Blender folders")
    parser.add_argument("--dry", action="store_true", help="Preview only")
    parser.add_argument("--5.0", dest="v50", action="store_true", help="5.0 only")
    parser.add_argument("--5.1", dest="v51", action="store_true", help="5.1 only")
    args = parser.parse_args()

    # 指定なし → 全部
    targets = {}
    if args.v50:
        targets["5.0"] = BLENDER_ADDON_DIRS["5.0"]
    elif args.v51:
        targets["5.1"] = BLENDER_ADDON_DIRS["5.1"]
    else:
        targets = BLENDER_ADDON_DIRS

    total = 0
    for ver, path in targets.items():
        print(f"\n--- Blender {ver} → {path}")
        count = sync_to(path, dry_run=args.dry)
        total += count
        print(f"  {count} files {'would be ' if args.dry else ''}synced")

    print(f"\nTotal: {total} files {'would be ' if args.dry else ''}synced")


if __name__ == "__main__":
    main()
