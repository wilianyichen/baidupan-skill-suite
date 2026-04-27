#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘同步规划工具。"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Dict

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_runtime import (
    configure_runtime,
    describe_token_search_order,
    load_access_token,
    python_command,
    shell_join,
)

HEADERS = {"User-Agent": "netdisk;P2SP;3.0.20.80"}
LIST_URL = "https://pan.baidu.com/rest/2.0/xpan/file"
TIME_TOLERANCE = 2
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


def should_include(rel_path: str, includes: list[str], excludes: list[str]) -> bool:
    include_match = True if not includes else any(fnmatch.fnmatch(rel_path, pattern) for pattern in includes)
    exclude_match = any(fnmatch.fnmatch(rel_path, pattern) for pattern in excludes)
    return include_match and not exclude_match


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

    def walk_tree(self, remote_root: str, includes: list[str], excludes: list[str]) -> Dict[str, dict]:
        remote_root = normalize_remote_path(remote_root)
        collected: Dict[str, dict] = {}

        def walk(current_path: str) -> None:
            for entry in self.list_dir(current_path):
                if entry.get("isdir", 0) == 1:
                    walk(entry["path"])
                    continue

                rel_path = remote_relative_path(remote_root, entry["path"])
                if not should_include(rel_path, includes, excludes):
                    continue
                collected[rel_path] = {
                    "relative_path": rel_path,
                    "absolute_path": entry["path"],
                    "size": int(entry.get("size", 0)),
                    "mtime": int(entry.get("server_mtime", 0)),
                    "source": "remote",
                }

        walk(remote_root)
        return collected


def remote_relative_path(remote_root: str, full_path: str) -> str:
    remote_root = normalize_remote_path(remote_root)
    full_path = normalize_remote_path(full_path)
    if remote_root == "/":
        return full_path.lstrip("/")
    prefix = remote_root.rstrip("/") + "/"
    return full_path[len(prefix) :]


def scan_local_tree(local_root: Path, includes: list[str], excludes: list[str], allow_missing: bool = False) -> Dict[str, dict]:
    if not local_root.exists():
        if allow_missing:
            return {}
        raise FileNotFoundError(f"本地目录不存在: {local_root}")
    if not local_root.is_dir():
        raise NotADirectoryError(f"本地路径不是目录: {local_root}")

    collected: Dict[str, dict] = {}
    for path in sorted(local_root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(local_root).as_posix()
        if not should_include(rel_path, includes, excludes):
            continue
        stat = path.stat()
        collected[rel_path] = {
            "relative_path": rel_path,
            "absolute_path": str(path.resolve()),
            "size": int(stat.st_size),
            "mtime": int(stat.st_mtime),
            "source": "local",
        }
    return collected


def classify_for_upload(local_item: dict, remote_item: dict | None) -> str:
    if remote_item is None:
        return "upload_new"
    if local_item["size"] == remote_item["size"] and abs(local_item["mtime"] - remote_item["mtime"]) <= TIME_TOLERANCE:
        return "skip"
    if local_item["mtime"] >= remote_item["mtime"] - TIME_TOLERANCE:
        return "upload_changed"
    return "conflict_remote_newer"


def classify_for_download(remote_item: dict, local_item: dict | None) -> str:
    if local_item is None:
        return "download_new"
    if local_item["size"] == remote_item["size"] and abs(local_item["mtime"] - remote_item["mtime"]) <= TIME_TOLERANCE:
        return "skip"
    if remote_item["mtime"] >= local_item["mtime"] - TIME_TOLERANCE:
        return "download_changed"
    return "conflict_local_newer"


def build_up_plan(local_root: Path, remote_root: str, local_map: Dict[str, dict], remote_map: Dict[str, dict], delete_extra: bool) -> dict:
    actions = {
        "upload_new": [],
        "upload_changed": [],
        "skip": [],
        "conflict_remote_newer": [],
        "delete_remote": [],
    }

    for rel_path, local_item in sorted(local_map.items()):
        remote_item = remote_map.get(rel_path)
        decision = classify_for_upload(local_item, remote_item)
        actions[decision].append(
            {
                "relative_path": rel_path,
                "local_path": local_item["absolute_path"],
                "remote_path": join_remote_path(remote_root, rel_path),
                "local_size": local_item["size"],
                "remote_size": None if remote_item is None else remote_item["size"],
                "local_mtime": local_item["mtime"],
                "remote_mtime": None if remote_item is None else remote_item["mtime"],
            }
        )

    if delete_extra:
        for rel_path, remote_item in sorted(remote_map.items()):
            if rel_path not in local_map:
                actions["delete_remote"].append(
                    {
                        "relative_path": rel_path,
                        "remote_path": remote_item["absolute_path"],
                        "remote_size": remote_item["size"],
                        "remote_mtime": remote_item["mtime"],
                    }
                )

    return {
        "mode": "up",
        "local_root": str(local_root.resolve()),
        "remote_root": normalize_remote_path(remote_root),
        "actions": actions,
    }


def build_down_plan(remote_root: str, local_root: Path, remote_map: Dict[str, dict], local_map: Dict[str, dict], delete_extra: bool) -> dict:
    actions = {
        "download_new": [],
        "download_changed": [],
        "skip": [],
        "conflict_local_newer": [],
        "delete_local": [],
    }

    for rel_path, remote_item in sorted(remote_map.items()):
        local_item = local_map.get(rel_path)
        decision = classify_for_download(remote_item, local_item)
        actions[decision].append(
            {
                "relative_path": rel_path,
                "remote_path": remote_item["absolute_path"],
                "local_path": str((local_root / rel_path).resolve()),
                "remote_size": remote_item["size"],
                "local_size": None if local_item is None else local_item["size"],
                "remote_mtime": remote_item["mtime"],
                "local_mtime": None if local_item is None else local_item["mtime"],
            }
        )

    if delete_extra:
        for rel_path, local_item in sorted(local_map.items()):
            if rel_path not in remote_map:
                actions["delete_local"].append(
                    {
                        "relative_path": rel_path,
                        "local_path": local_item["absolute_path"],
                        "local_size": local_item["size"],
                        "local_mtime": local_item["mtime"],
                    }
                )

    return {
        "mode": "down",
        "local_root": str(local_root.resolve()),
        "remote_root": normalize_remote_path(remote_root),
        "actions": actions,
    }


def join_remote_path(remote_root: str, rel_path: str) -> str:
    remote_root = normalize_remote_path(remote_root)
    if remote_root == "/":
        return "/" + rel_path.lstrip("/")
    return remote_root.rstrip("/") + "/" + rel_path.lstrip("/")


def summarize_plan(plan: dict) -> None:
    print(f"模式：{plan['mode']}")
    print(f"本地根目录：{plan['local_root']}")
    print(f"网盘根目录：{plan['remote_root']}")
    print("行动统计：")
    for action, items in plan["actions"].items():
        print(f"  {action}: {len(items)}")


def preview_actions(plan: dict, limit: int) -> None:
    for action, items in plan["actions"].items():
        if not items:
            continue
        print(f"\n[{action}]")
        for item in items[:limit]:
            size = item.get("local_size")
            if size is None:
                size = item.get("remote_size", 0)
            print(f"- {item['relative_path']} ({format_size(size or 0)})")
        if len(items) > limit:
            print(f"... 其余 {len(items) - limit} 条未显示")


def maybe_write_manifest(plan: dict, manifest: str | None) -> None:
    if not manifest:
        return
    manifest_path = Path(manifest).expanduser().resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)
    print(f"\n✅ 已写入 manifest：{manifest_path}")


def enhanced_script_path() -> str:
    return (REPO_ROOT / "bypy-enhanced" / "scripts" / "bdpan_enhanced.py").as_posix()


def print_commands(plan: dict) -> None:
    script = enhanced_script_path()
    python_exe = python_command()
    if plan["mode"] == "up":
        commands = plan["actions"]["upload_new"] + plan["actions"]["upload_changed"]
        if not commands:
            print("✅ 没有需要上传的文件")
            return
        for item in commands:
            print(shell_join([python_exe, script, "upload", item["local_path"], item["remote_path"]]))
    else:
        commands = plan["actions"]["download_new"] + plan["actions"]["download_changed"]
        if not commands:
            print("✅ 没有需要下载的文件")
            return
        for item in commands:
            print(shell_join([python_exe, script, "download", item["remote_path"], item["local_path"]]))


def collect_plan(args: argparse.Namespace) -> dict:
    token = load_token()
    client = BaiduPanClient(token)
    includes = args.include or []
    excludes = args.exclude or []

    if args.command in {"plan-up", "commands-up"}:
        local_root = Path(args.local_root).expanduser().resolve()
        remote_root = normalize_remote_path(args.remote_root)
        local_map = scan_local_tree(local_root, includes, excludes)
        remote_map = client.walk_tree(remote_root, includes, excludes)
        return build_up_plan(local_root, remote_root, local_map, remote_map, args.delete_extra)

    remote_root = normalize_remote_path(args.remote_root)
    local_root = Path(args.local_root).expanduser().resolve()
    remote_map = client.walk_tree(remote_root, includes, excludes)
    local_map = scan_local_tree(local_root, includes, excludes, allow_missing=True)
    return build_down_plan(remote_root, local_root, remote_map, local_map, args.delete_extra)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘同步规划工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_flags(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--include", action="append", help="仅包含匹配该 glob 的路径，可重复指定")
        subparser.add_argument("--exclude", action="append", help="排除匹配该 glob 的路径，可重复指定")
        subparser.add_argument("--delete-extra", action="store_true", help="额外列出另一侧独有文件的删除候选")
        subparser.add_argument("--manifest", help="把计划写入 JSON 文件")
        subparser.add_argument("--limit", type=int, default=20, help="预览时每类最多显示多少条")

    up_plan = subparsers.add_parser("plan-up", help="规划本地 -> 网盘")
    up_plan.add_argument("local_root")
    up_plan.add_argument("remote_root")
    add_common_flags(up_plan)

    down_plan = subparsers.add_parser("plan-down", help="规划网盘 -> 本地")
    down_plan.add_argument("remote_root")
    down_plan.add_argument("local_root")
    add_common_flags(down_plan)

    up_commands = subparsers.add_parser("commands-up", help="输出本地 -> 网盘的建议命令")
    up_commands.add_argument("local_root")
    up_commands.add_argument("remote_root")
    add_common_flags(up_commands)

    down_commands = subparsers.add_parser("commands-down", help="输出网盘 -> 本地的建议命令")
    down_commands.add_argument("remote_root")
    down_commands.add_argument("local_root")
    add_common_flags(down_commands)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        plan = collect_plan(args)
        summarize_plan(plan)
        preview_actions(plan, args.limit)
        maybe_write_manifest(plan, args.manifest)

        if args.command.startswith("commands-"):
            print("\n[建议命令]")
            print_commands(plan)
        return 0
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except (RuntimeError, FileNotFoundError, NotADirectoryError) as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
