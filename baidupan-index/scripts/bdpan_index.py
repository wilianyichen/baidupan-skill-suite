#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘索引工具。"""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_inventory import (
    BaiduPanInventoryClient,
    format_mtime,
    format_size,
    normalize_remote_path,
    scan_local_entries,
    scan_remote_entries,
)
from common.bdpan_manifest import now_iso, read_json, write_json
from common.bdpan_runtime import configure_runtime, describe_token_search_order, load_access_token

configure_runtime()


def load_token() -> str:
    try:
        return load_access_token(__file__)
    except (FileNotFoundError, KeyError) as exc:
        print(f"❌ {exc}")
        print("已检查：")
        for candidate in describe_token_search_order(__file__):
            print(f"  - {candidate}")
        sys.exit(1)


def build_index(kind: str, root: str, entries: dict[str, dict]) -> dict:
    return {
        "tool": "baidupan-index",
        "generated_at": now_iso(),
        "kind": kind,
        "root": root,
        "entries": list(entries.values()),
    }


def save_index(index: dict, output: str) -> int:
    output_path = Path(output).expanduser().resolve()
    write_json(output_path, index)
    print(f"✅ 索引已保存到: {output_path}")
    print(f"entries: {len(index['entries'])}")
    return 0


def command_build_local(args: argparse.Namespace) -> int:
    local_root = Path(args.local_root).expanduser().resolve()
    entries = scan_local_entries(local_root, include_dirs=args.include_dirs, include_files=True)
    return save_index(build_index("local", str(local_root), entries), args.output)


def command_build_remote(args: argparse.Namespace) -> int:
    token = load_token()
    client = BaiduPanInventoryClient(token)
    remote_root = normalize_remote_path(args.remote_root)
    entries = scan_remote_entries(client, remote_root, include_dirs=args.include_dirs, include_files=True)
    return save_index(build_index("remote", remote_root, entries), args.output)


def match_entry(entry: dict, pattern: str) -> bool:
    rel_path = entry["relative_path"]
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatch(rel_path, pattern)
    return pattern in rel_path


def command_query(args: argparse.Namespace) -> int:
    index = read_json(Path(args.index_file).expanduser().resolve())
    entries = index.get("entries", [])
    filtered = [entry for entry in entries if match_entry(entry, args.pattern)]
    if args.type:
        filtered = [entry for entry in filtered if entry.get("type") == args.type]
    filtered.sort(key=lambda item: (-int(item.get("mtime", 0)), item["relative_path"]))
    print(f"matches: {len(filtered)}")
    for entry in filtered[: args.limit]:
        print(f"- {entry['relative_path']} [{entry['type']}] {format_size(int(entry.get('size', 0)))} {format_mtime(int(entry.get('mtime', 0)))}")
    if len(filtered) > args.limit:
        print(f"... 其余 {len(filtered) - args.limit} 条未显示")
    return 0


def command_stats(args: argparse.Namespace) -> int:
    index = read_json(Path(args.index_file).expanduser().resolve())
    entries = index.get("entries", [])
    file_count = sum(1 for entry in entries if entry.get("type") == "file")
    dir_count = sum(1 for entry in entries if entry.get("type") == "dir")
    total_size = sum(int(entry.get("size", 0)) for entry in entries if entry.get("type") == "file")
    print(f"kind: {index.get('kind')}")
    print(f"root: {index.get('root')}")
    print(f"generated_at: {index.get('generated_at')}")
    print(f"files: {file_count}")
    print(f"dirs: {dir_count}")
    print(f"size: {format_size(total_size)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘索引工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_local_parser = subparsers.add_parser("build-local")
    build_local_parser.add_argument("local_root")
    build_local_parser.add_argument("--output", required=True)
    build_local_parser.add_argument("--include-dirs", action="store_true")

    build_remote_parser = subparsers.add_parser("build-remote")
    build_remote_parser.add_argument("remote_root")
    build_remote_parser.add_argument("--output", required=True)
    build_remote_parser.add_argument("--include-dirs", action="store_true")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("index_file")
    query_parser.add_argument("pattern")
    query_parser.add_argument("--type", choices=["file", "dir"])
    query_parser.add_argument("--limit", type=int, default=50)

    stats_parser = subparsers.add_parser("stats")
    stats_parser.add_argument("index_file")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "build-local":
        return command_build_local(args)
    if args.command == "build-remote":
        return command_build_remote(args)
    if args.command == "query":
        return command_query(args)
    if args.command == "stats":
        return command_stats(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
