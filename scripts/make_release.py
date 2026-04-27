#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成版本化 release 产物。"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"


def read_version(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成版本化 release 产物")
    parser.add_argument("--version", default="", help="版本号。不填时读取 VERSION 文件")
    parser.add_argument("--include-token", action="store_true", help="打包时包含 token")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    version = args.version or read_version(PROJECT_ROOT / "VERSION")
    version_tag = version if version.startswith("v") else f"v{version}"
    package_name = f"baidupan-skill-suite-{version_tag}-linux.tar.gz"
    package_path = DIST_DIR / package_name

    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "package_linux_bundle.py"),
            "--package-name",
            package_name,
        ]
        + (["--include-token"] if args.include_token else []),
        check=True,
    )

    release_note_src = PROJECT_ROOT / "docs" / "releases" / f"{version_tag}.md"
    if not release_note_src.exists():
        print(f"❌ release note not found: {release_note_src}")
        return 1

    release_note_dst = DIST_DIR / f"baidupan-skill-suite-{version_tag}-release-notes.md"
    shutil.copyfile(release_note_src, release_note_dst)

    checksum = sha256sum(package_path)
    checksum_path = DIST_DIR / f"baidupan-skill-suite-{version_tag}-linux.sha256"
    checksum_path.write_text(f"{checksum}  {package_name}\n", encoding="utf-8")

    print(f"✅ release package: {package_path}")
    print(f"✅ release notes:   {release_note_dst}")
    print(f"✅ sha256:          {checksum_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
