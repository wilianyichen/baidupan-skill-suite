#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘 manifest 汇总工具。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_manifest import merge_manifests, read_json, render_manifest_summary, render_runbook, write_json
from common.bdpan_runtime import configure_runtime

configure_runtime()


def load_manifests(paths: list[str]) -> list[dict]:
    manifests = []
    for path in paths:
        manifest = read_json(Path(path).expanduser().resolve())
        manifest["source_manifest"] = str(Path(path).expanduser().resolve())
        manifests.append(manifest)
    return manifests


def command_summary(args: argparse.Namespace) -> int:
    for manifest in load_manifests(args.manifests):
        print(f"[{manifest['source_manifest']}]")
        print(render_manifest_summary(manifest))
        print()
    return 0


def command_merge(args: argparse.Namespace) -> int:
    merged = merge_manifests(load_manifests(args.manifests))
    output_path = Path(args.output).expanduser().resolve()
    write_json(output_path, merged)
    print(f"✅ 已写入: {output_path}")
    print(render_manifest_summary(merged))
    return 0


def command_runbook(args: argparse.Namespace) -> int:
    manifest = read_json(Path(args.manifest).expanduser().resolve())
    rendered = render_runbook(manifest, limit=args.limit)
    print(rendered)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"✅ runbook 已保存到: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘 manifest 汇总工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("manifests", nargs="+")

    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("output")
    merge_parser.add_argument("manifests", nargs="+")

    runbook_parser = subparsers.add_parser("runbook")
    runbook_parser.add_argument("manifest")
    runbook_parser.add_argument("--limit", type=int, default=200)
    runbook_parser.add_argument("--output")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "summary":
        return command_summary(args)
    if args.command == "merge":
        return command_merge(args)
    if args.command == "runbook":
        return command_runbook(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
