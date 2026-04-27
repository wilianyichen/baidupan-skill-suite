#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘目录监控脚本。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_runtime import configure_runtime, describe_token_search_order, load_access_token
from merkle_tree import build_dir_node, build_file_node, diff_snapshots
from snapshot import MonitoredSnapshot, resolve_snapshot_path


HEADERS = {"User-Agent": "netdisk;P2SP;3.0.20.80"}
LIST_URL = "https://pan.baidu.com/rest/2.0/xpan/file"
configure_runtime()


def normalize_remote_path(path: str) -> str:
    if not path:
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    normalized = path.replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized or "/"


def load_token() -> str:
    try:
        return load_access_token(__file__)
    except (FileNotFoundError, KeyError) as exc:
        print(f"❌ {exc}")
        print("   已检查：")
        for candidate in describe_token_search_order(__file__):
            print(f"   - {candidate}")
        sys.exit(1)


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

    def build_snapshot(self, remote_path: str) -> dict:
        remote_path = normalize_remote_path(remote_path)
        children: dict[str, dict] = {}

        for entry in sorted(self.list_dir(remote_path), key=lambda item: (item.get("isdir", 0) == 0, item.get("server_filename", ""))):
            name = entry.get("server_filename", entry.get("path", "").rsplit("/", 1)[-1])
            if entry.get("isdir", 0) == 1:
                child = self.build_snapshot(entry["path"])
                child["name"] = name
                child["mtime"] = int(entry.get("server_mtime", child.get("mtime", 0)))
            else:
                child = build_file_node(entry)
            children[name] = child

        node = build_dir_node(remote_path, children)
        if remote_path == "/":
            node["name"] = "/"
        return node


def snapshot_object(remote_path: str, root: dict, snapshot_path: Path | None = None) -> MonitoredSnapshot:
    return MonitoredSnapshot.from_root(remote_path=normalize_remote_path(remote_path), root=root, snapshot_path=snapshot_path)


def print_summary(changes: list[dict]) -> None:
    added = sum(1 for item in changes if item["kind"] == "added")
    removed = sum(1 for item in changes if item["kind"] == "removed")
    modified = sum(1 for item in changes if item["kind"] == "modified")
    print(f"变化总数：{len(changes)}")
    print(f"  新增：{added}")
    print(f"  删除：{removed}")
    print(f"  修改：{modified}")


def render_change(change: dict) -> str:
    symbol = {"added": "+", "removed": "-", "modified": "~"}[change["kind"]]
    node = change.get("new") or change.get("old") or {}
    node_type = "目录" if node.get("type") == "dir" else "文件"
    path = change["path"]

    if change["kind"] == "modified":
        old = change["old"]
        new = change["new"]
        details = []
        if old.get("size") != new.get("size"):
            details.append(f"size {old.get('size', 0)} -> {new.get('size', 0)}")
        if old.get("mtime") != new.get("mtime"):
            details.append(f"mtime {old.get('mtime', 0)} -> {new.get('mtime', 0)}")
        suffix = f" ({', '.join(details)})" if details else ""
        return f"{symbol} {node_type} {path}{suffix}"

    return f"{symbol} {node_type} {path}"


def command_init(client: BaiduPanClient, args: argparse.Namespace) -> int:
    remote_path = normalize_remote_path(args.remote_path)
    snapshot_path = resolve_snapshot_path(remote_path, args.name)
    monitored = snapshot_object(remote_path, client.build_snapshot(remote_path), snapshot_path=snapshot_path)
    monitored.save()
    print(f"✅ 已创建快照：{snapshot_path}")
    print(f"   根哈希：{monitored.root['hash']}")
    return 0


def load_existing_snapshot(remote_path: str, name: str | None) -> tuple[Path, MonitoredSnapshot]:
    snapshot_path = resolve_snapshot_path(remote_path, name)
    if not snapshot_path.exists():
        print(f"❌ 快照不存在：{snapshot_path}")
        print("   请先执行 init")
        raise SystemExit(1)
    return snapshot_path, MonitoredSnapshot.load(snapshot_path)


def command_check(client: BaiduPanClient, args: argparse.Namespace) -> int:
    remote_path = normalize_remote_path(args.remote_path)
    _, existing = load_existing_snapshot(remote_path, args.name)
    current = snapshot_object(remote_path, client.build_snapshot(remote_path))

    if current.root["hash"] == existing.root["hash"]:
        print("✅ 目录无变化")
        return 0

    changes = diff_snapshots(existing.root, current.root)
    print("⚠️  检测到目录变化")
    print_summary(changes)
    if args.verbose:
        for change in changes[: args.limit]:
            print(render_change(change))
    return 2


def command_diff(client: BaiduPanClient, args: argparse.Namespace) -> int:
    remote_path = normalize_remote_path(args.remote_path)
    _, existing = load_existing_snapshot(remote_path, args.name)
    current = snapshot_object(remote_path, client.build_snapshot(remote_path))
    changes = diff_snapshots(existing.root, current.root)

    if not changes:
        print("✅ 目录无变化")
        return 0

    print_summary(changes)
    for change in changes[: args.limit]:
        print(render_change(change))

    if len(changes) > args.limit:
        print(f"... 其余 {len(changes) - args.limit} 条变化未显示")
    return 2


def command_update(client: BaiduPanClient, args: argparse.Namespace) -> int:
    remote_path = normalize_remote_path(args.remote_path)
    snapshot_path, existing = load_existing_snapshot(remote_path, args.name)
    current = snapshot_object(remote_path, client.build_snapshot(remote_path), snapshot_path=snapshot_path)
    changes = diff_snapshots(existing.root, current.root)

    current.save()
    print(f"✅ 快照已更新：{snapshot_path}")
    print_summary(changes)
    return 0


def command_tree(args: argparse.Namespace) -> int:
    remote_path = normalize_remote_path(args.remote_path)
    _, monitored = load_existing_snapshot(remote_path, args.name)

    try:
        rendered = monitored.render_tree(branch=args.branch, max_depth=args.depth)
    except KeyError as exc:
        print(f"❌ {exc}")
        return 1

    print(rendered)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        monitored.export_tree(output_path=output_path, branch=args.branch, max_depth=args.depth)
        print(f"✅ 已保存到：{output_path}")

    return 0


def command_compare(args: argparse.Namespace) -> int:
    remote_path = normalize_remote_path(args.remote_path)
    _, monitored = load_existing_snapshot(remote_path, args.name)

    try:
        rendered = monitored.render_comparison(
            left_branch=args.left_branch,
            right_branch=args.right_branch,
            ignore_extension=args.ignore_extension,
            limit=args.limit,
        )
    except KeyError as exc:
        print(f"❌ {exc}")
        return 1

    print(rendered)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        monitored.export_comparison(
            output_path=output_path,
            left_branch=args.left_branch,
            right_branch=args.right_branch,
            ignore_extension=args.ignore_extension,
            limit=args.limit,
        )
        print(f"✅ 已保存到：{output_path}")

    return 0


def command_watch(client: BaiduPanClient, args: argparse.Namespace) -> int:
    remote_path = normalize_remote_path(args.remote_path)
    snapshot_path = resolve_snapshot_path(remote_path, args.name)
    rounds = args.rounds
    iteration = 0

    if snapshot_path.exists():
        existing = MonitoredSnapshot.load(snapshot_path)
    else:
        existing = snapshot_object(remote_path, client.build_snapshot(remote_path), snapshot_path=snapshot_path)
        existing.save()
        print(f"✅ 已创建初始快照：{snapshot_path}")

    while True:
        iteration += 1
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 第 {iteration} 次检查")
        current = snapshot_object(remote_path, client.build_snapshot(remote_path), snapshot_path=snapshot_path)
        changes = diff_snapshots(existing.root, current.root)

        if changes:
            print("⚠️  检测到变化")
            print_summary(changes)
            for change in changes[: args.limit]:
                print(render_change(change))
            current.save()
            existing = current
        else:
            print("✅ 无变化")

        if rounds and iteration >= rounds:
            break
        time.sleep(args.interval)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘目录监控工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ["init", "check", "diff", "update", "watch", "tree", "compare"]:
        sub = subparsers.add_parser(name)
        sub.add_argument("remote_path", help="要监控的网盘目录")
        sub.add_argument("--name", help="自定义快照名称")
        if name in {"check", "diff", "update", "watch", "compare"}:
            sub.add_argument("--limit", type=int, default=50, help="最多显示多少条变化")
        if name == "check":
            sub.add_argument("--verbose", action="store_true", help="变化时顺便输出明细")
        if name == "watch":
            sub.add_argument("--interval", type=int, default=300, help="轮询间隔，单位秒")
            sub.add_argument("--rounds", type=int, default=0, help="轮询次数，0 表示无限循环")
        if name == "tree":
            sub.add_argument("--branch", help="要查看的分支路径。可填相对监视根目录的路径，也可填绝对路径")
            sub.add_argument("--depth", type=int, help="最大展开层级，默认完整展开")
            sub.add_argument("--output", help="把 tree 输出保存到文件")
        if name == "compare":
            sub.add_argument("left_branch", help="左侧分支路径，可填相对监视根目录的路径，也可填绝对路径")
            sub.add_argument("right_branch", help="右侧分支路径，可填相对监视根目录的路径，也可填绝对路径")
            sub.add_argument("--ignore-extension", action="store_true", help="比较文件结构时忽略扩展名")
            sub.add_argument("--output", help="把比较结果保存到文件")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    client = BaiduPanClient(load_token())

    try:
        if args.command == "init":
            return command_init(client, args)
        if args.command == "check":
            return command_check(client, args)
        if args.command == "diff":
            return command_diff(client, args)
        if args.command == "update":
            return command_update(client, args)
        if args.command == "watch":
            return command_watch(client, args)
        if args.command == "tree":
            return command_tree(args)
        if args.command == "compare":
            return command_compare(args)
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
