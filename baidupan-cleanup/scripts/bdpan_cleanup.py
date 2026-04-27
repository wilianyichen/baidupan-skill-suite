#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘清理分析工具。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_runtime import configure_runtime, describe_token_search_order, load_access_token

HEADERS = {"User-Agent": "netdisk;P2SP;3.0.20.80"}
LIST_URL = "https://pan.baidu.com/rest/2.0/xpan/file"
configure_runtime()


def normalize_remote_path(path: str) -> str:
    if not path:
        return "/"
    normalized = path.replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized or "/"


def load_token() -> str:
    try:
        return load_access_token(__file__)
    except (FileNotFoundError, KeyError) as exc:
        print(f"❌ {exc}")
        print("已检查：")
        for candidate in describe_token_search_order(__file__):
            print(f"  - {candidate}")
        sys.exit(1)


def format_size(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} PB"


class BaiduPanClient:
    def __init__(self, token: str):
        self.token = token

    def list_dir(self, remote_path: str) -> list[dict]:
        remote_path = normalize_remote_path(remote_path)
        session = requests.Session()
        session.trust_env = False
        start = 0
        limit = 1000
        items: list[dict] = []

        try:
            while True:
                params = {
                    "method": "list",
                    "access_token": self.token,
                    "dir": remote_path,
                    "web": "1",
                    "start": start,
                    "limit": limit,
                }
                response = session.get(LIST_URL, params=params, headers=HEADERS, timeout=30)
                response.raise_for_status()
                payload = response.json()
                errno = payload.get("errno", 0)
                if errno != 0:
                    raise RuntimeError(f"API 错误: {payload}")
                batch = payload.get("list", [])
                items.extend(batch)
                if len(batch) < limit:
                    break
                start += len(batch)
        finally:
            session.close()

        return items

    def scan_tree(self, remote_root: str) -> tuple[list[dict], list[str]]:
        remote_root = normalize_remote_path(remote_root)
        files: list[dict] = []
        empty_dirs: list[str] = []

        def walk(current_path: str) -> None:
            entries = self.list_dir(current_path)
            if not entries:
                empty_dirs.append(current_path)
                return

            for entry in entries:
                if entry.get("isdir", 0) == 1:
                    walk(entry["path"])
                else:
                    files.append(
                        {
                            "path": entry["path"],
                            "name": entry.get("server_filename", entry["path"].rsplit("/", 1)[-1]),
                            "size": int(entry.get("size", 0)),
                            "mtime": int(entry.get("server_mtime", 0)),
                            "suffix": file_suffix(entry.get("server_filename", "")),
                        }
                    )

        walk(remote_root)
        return files, empty_dirs


def file_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if suffix else "[no-ext]"


def render_large_files(files: list[dict], top: int) -> None:
    for index, item in enumerate(sorted(files, key=lambda value: value["size"], reverse=True)[:top], start=1):
        print(f"{index:>2}. {format_size(item['size']):>10}  {item['path']}")


def render_stale_files(files: list[dict], days: int, top: int) -> None:
    threshold = int(time.time()) - days * 24 * 60 * 60
    stale = [item for item in files if item["mtime"] and item["mtime"] <= threshold]
    stale.sort(key=lambda item: item["mtime"])

    for index, item in enumerate(stale[:top], start=1):
        print(f"{index:>2}. {time.strftime('%Y-%m-%d', time.localtime(item['mtime']))}  {format_size(item['size']):>10}  {item['path']}")

    if not stale:
        print("✅ 未发现满足条件的旧文件")


def render_suffix_report(files: list[dict], top: int) -> None:
    grouped: dict[str, dict] = defaultdict(lambda: {"count": 0, "size": 0})
    for item in files:
        grouped[item["suffix"]]["count"] += 1
        grouped[item["suffix"]]["size"] += item["size"]

    rows = sorted(grouped.items(), key=lambda value: value[1]["size"], reverse=True)[:top]
    for index, (suffix, data) in enumerate(rows, start=1):
        print(f"{index:>2}. {suffix:<10} {data['count']:>6} files  {format_size(data['size']):>10}")


def render_duplicate_candidates(files: list[dict], top: int) -> None:
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for item in files:
        grouped[(item["name"].lower(), item["size"])].append(item)

    duplicates = [items for items in grouped.values() if len(items) > 1]
    duplicates.sort(key=lambda items: (len(items), items[0]["size"]), reverse=True)

    if not duplicates:
        print("✅ 未发现同名同大小的重复候选")
        return

    for index, items in enumerate(duplicates[:top], start=1):
        print(f"{index:>2}. {items[0]['name']}  {format_size(items[0]['size'])}  x{len(items)}")
        for item in items:
            print(f"    {item['path']}")


def render_empty_dirs(empty_dirs: list[str], top: int) -> None:
    if not empty_dirs:
        print("✅ 未发现空目录")
        return
    for index, path in enumerate(sorted(empty_dirs)[:top], start=1):
        print(f"{index:>2}. {path}")
    if len(empty_dirs) > top:
        print(f"... 其余 {len(empty_dirs) - top} 个空目录未显示")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘清理分析工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ["large-files", "stale-files", "suffix-report", "duplicate-candidates", "empty-dirs"]:
        sub = subparsers.add_parser(command)
        sub.add_argument("remote_root")
        sub.add_argument("--top", type=int, default=20, help="最多显示多少条")
        if command == "stale-files":
            sub.add_argument("--days", type=int, default=180, help="多少天未更新算旧文件")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        client = BaiduPanClient(load_token())
        files, empty_dirs = client.scan_tree(args.remote_root)

        print(f"扫描目录：{normalize_remote_path(args.remote_root)}")
        print(f"文件数：{len(files)}")
        print(f"空目录数：{len(empty_dirs)}")
        print()

        if args.command == "large-files":
            render_large_files(files, args.top)
        elif args.command == "stale-files":
            render_stale_files(files, args.days, args.top)
        elif args.command == "suffix-report":
            render_suffix_report(files, args.top)
        elif args.command == "duplicate-candidates":
            render_duplicate_candidates(files, args.top)
            print("\n提示：这里只是“同名同大小”候选，不代表内容绝对一致。")
        elif args.command == "empty-dirs":
            render_empty_dirs(empty_dirs, args.top)
        return 0
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
