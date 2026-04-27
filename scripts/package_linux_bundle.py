#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包当前项目，供 Linux 环境解压使用。"""

from __future__ import annotations

import argparse
import tarfile
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "dist"
DEFAULT_PACKAGE_BASENAME = "baidupan-tools-linux"
INCLUDE_PATHS = [
    "README.md",
    "requirements.min.txt",
    "common",
    "scripts",
    "docs",
    "baidupan-suite",
    "bypy-baidu-netdisk",
    "bypy-enhanced",
    "baidupan-monitor",
    "baidupan-sync",
    "baidupan-cleanup",
    "baidupan-reconcile",
    "baidupan-fs",
    "baidupan-index",
    "baidupan-archive",
    "baidupan-verify",
    "baidupan-batch-runner",
    "baidupan-apply",
]

SKIP_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="打包 Linux 使用的百度网盘技能工具集")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="输出目录，默认 dist/",
    )
    parser.add_argument(
        "--package-name",
        default="",
        help="压缩包文件名。不填时自动生成为 baidupan-tools-linux-YYYYMMDD-HHMMSS.tar.gz",
    )
    parser.add_argument(
        "--root-name",
        default="baidupan-tools",
        help="压缩包内部顶层目录名，默认 baidupan-tools",
    )
    parser.add_argument(
        "--include-token",
        action="store_true",
        help="把当前项目根目录的 bypy.token.json 一起打进包。默认不包含。",
    )
    return parser


def resolve_package_path(output_dir: Path, package_name: str) -> Path:
    if package_name:
        filename = package_name
    else:
        filename = f"{DEFAULT_PACKAGE_BASENAME}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz"
    if not filename.endswith(".tar.gz"):
        filename += ".tar.gz"
    return output_dir / filename


def should_skip(path: Path) -> bool:
    if path.name in SKIP_NAMES:
        return True
    if any(part in SKIP_NAMES for part in path.parts):
        return True
    if any(path.name.endswith(suffix) for suffix in SKIP_SUFFIXES):
        return True
    if ".pyc." in path.name:
        return True
    return False


def add_path(archive: tarfile.TarFile, source: Path, root_name: str) -> None:
    if should_skip(source):
        return
    arcname = str(Path(root_name) / source.relative_to(PROJECT_ROOT))
    archive.add(
        source,
        arcname=arcname,
        filter=lambda tarinfo: None if should_skip(Path(tarinfo.name)) else tarinfo,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = resolve_package_path(output_dir, args.package_name)

    include_paths = [PROJECT_ROOT / item for item in INCLUDE_PATHS]
    if args.include_token:
        token_path = PROJECT_ROOT / "bypy.token.json"
        if token_path.exists():
            include_paths.append(token_path)

    with tarfile.open(package_path, "w:gz") as archive:
        for path in include_paths:
            if path.exists():
                add_path(archive, path, args.root_name)

    print(f"✅ Linux 技能包已生成: {package_path}")
    print(f"root_name: {args.root_name}")
    print(f"include_token: {'yes' if args.include_token else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
