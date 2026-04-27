#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘归档计划工具。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_inventory import normalize_remote_path
from common.bdpan_manifest import now_iso, read_json, render_manifest_summary, write_json
from common.bdpan_runtime import configure_runtime

configure_runtime()


def archive_target(remote_path: str, archive_root: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d")
    remote_path = normalize_remote_path(remote_path)
    archive_root = normalize_remote_path(archive_root)
    return normalize_remote_path(f"{archive_root.rstrip('/')}/{stamp}{remote_path}")


def build_manifest(paths: list[str], archive_root: str) -> dict:
    actions = []
    for path in paths:
        source = normalize_remote_path(path)
        actions.append({"action": "archive_remote", "source": source, "target": archive_target(source, archive_root)})
    return {
        "tool": "baidupan-archive",
        "generated_at": now_iso(),
        "actions": actions,
    }


def output_manifest(manifest: dict, output: str | None) -> int:
    print(render_manifest_summary(manifest))
    if output:
        output_path = Path(output).expanduser().resolve()
        write_json(output_path, manifest)
        print(f"✅ 归档 manifest 已保存到: {output_path}")
    return 0


def command_direct(args: argparse.Namespace) -> int:
    return output_manifest(build_manifest(args.paths, args.archive_root), args.output)


def command_from_report(args: argparse.Namespace) -> int:
    report = read_json(Path(args.report_file).expanduser().resolve())
    source_kind = report.get(f"{args.source}_kind")
    if source_kind != "remote":
        print(f"❌ {args.source} 侧不是 remote，不能生成网盘归档计划")
        return 1

    paths: list[str] = []
    paths.extend(item["path"] for item in report.get(f"{args.source}_only_dirs", []))
    paths.extend(item["path"] for item in report.get(f"{args.source}_only_files", []))
    if not paths:
        print("✅ 报告中没有可归档的远端独有路径")
        return 0

    return output_manifest(build_manifest(paths, args.archive_root), args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘归档计划工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    direct_parser = subparsers.add_parser("direct-paths")
    direct_parser.add_argument("paths", nargs="+")
    direct_parser.add_argument("--archive-root", default="/归档整理")
    direct_parser.add_argument("--output")

    report_parser = subparsers.add_parser("from-report")
    report_parser.add_argument("report_file")
    report_parser.add_argument("--source", choices=["left", "right"], required=True)
    report_parser.add_argument("--archive-root", default="/归档整理")
    report_parser.add_argument("--output")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "direct-paths":
        return command_direct(args)
    if args.command == "from-report":
        return command_from_report(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
