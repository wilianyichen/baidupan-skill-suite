#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘文件系统计划工具。"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_inventory import normalize_remote_path
from common.bdpan_manifest import now_iso, render_manifest_summary, write_json
from common.bdpan_runtime import configure_runtime

configure_runtime()


def archive_target(remote_path: str, archive_root: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d")
    remote_path = normalize_remote_path(remote_path)
    archive_root = normalize_remote_path(archive_root)
    if remote_path == "/":
        raise ValueError("不能归档根目录")
    return normalize_remote_path(f"{archive_root.rstrip('/')}/{stamp}{remote_path}")


def make_manifest(actions: list[dict]) -> dict:
    return {
        "tool": "baidupan-fs",
        "generated_at": now_iso(),
        "actions": actions,
    }


def emit_manifest(manifest: dict, output: str | None) -> int:
    print(render_manifest_summary(manifest))
    if output:
        output_path = Path(output).expanduser().resolve()
        write_json(output_path, manifest)
        print(f"✅ manifest 已保存到: {output_path}")
    return 0


def command_mkdir(args: argparse.Namespace) -> int:
    manifest = make_manifest([{"action": "mkdir_remote", "target": normalize_remote_path(path)} for path in args.paths])
    return emit_manifest(manifest, args.output)


def command_move(args: argparse.Namespace) -> int:
    manifest = make_manifest(
        [{"action": "move_remote", "source": normalize_remote_path(args.source), "target": normalize_remote_path(args.target)}]
    )
    return emit_manifest(manifest, args.output)


def command_copy(args: argparse.Namespace) -> int:
    manifest = make_manifest(
        [{"action": "copy_remote", "source": normalize_remote_path(args.source), "target": normalize_remote_path(args.target)}]
    )
    return emit_manifest(manifest, args.output)


def command_rename(args: argparse.Namespace) -> int:
    source = normalize_remote_path(args.source)
    parent = normalize_remote_path(str(Path(source).parent).replace("\\", "/"))
    if parent == ".":
        parent = "/"
    target = normalize_remote_path(f"{parent.rstrip('/')}/{args.new_name}")
    manifest = make_manifest([{"action": "rename_remote", "source": source, "target": target}])
    return emit_manifest(manifest, args.output)


def command_archive(args: argparse.Namespace) -> int:
    actions = []
    for path in args.paths:
        source = normalize_remote_path(path)
        actions.append(
            {
                "action": "archive_remote",
                "source": source,
                "target": archive_target(source, args.archive_root),
            }
        )
    manifest = make_manifest(actions)
    return emit_manifest(manifest, args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘文件系统计划工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mkdir_parser = subparsers.add_parser("mkdir-plan")
    mkdir_parser.add_argument("paths", nargs="+")
    mkdir_parser.add_argument("--output")

    move_parser = subparsers.add_parser("move-plan")
    move_parser.add_argument("source")
    move_parser.add_argument("target")
    move_parser.add_argument("--output")

    copy_parser = subparsers.add_parser("copy-plan")
    copy_parser.add_argument("source")
    copy_parser.add_argument("target")
    copy_parser.add_argument("--output")

    rename_parser = subparsers.add_parser("rename-plan")
    rename_parser.add_argument("source")
    rename_parser.add_argument("new_name")
    rename_parser.add_argument("--output")

    archive_parser = subparsers.add_parser("archive-plan")
    archive_parser.add_argument("paths", nargs="+")
    archive_parser.add_argument("--archive-root", default="/归档整理")
    archive_parser.add_argument("--output")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "mkdir-plan":
        return command_mkdir(args)
    if args.command == "move-plan":
        return command_move(args)
    if args.command == "copy-plan":
        return command_copy(args)
    if args.command == "rename-plan":
        return command_rename(args)
    if args.command == "archive-plan":
        return command_archive(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
