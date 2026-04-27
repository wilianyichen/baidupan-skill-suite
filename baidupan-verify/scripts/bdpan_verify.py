#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘 manifest 验证工具。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_inventory import BaiduPanInventoryClient, normalize_remote_path
from common.bdpan_manifest import read_json
from common.bdpan_runtime import configure_runtime, describe_token_search_order, load_access_token

configure_runtime()


REMOTE_KEYS = {
    "source": {"move_remote", "copy_remote", "rename_remote", "archive_remote"},
    "target": {"move_remote", "copy_remote", "rename_remote", "archive_remote", "mkdir_remote"},
}


def load_token() -> str:
    try:
        return load_access_token(__file__)
    except (FileNotFoundError, KeyError):
        return ""


def remote_needs_token(actions: list[dict]) -> bool:
    for action in actions:
        if action.get("action", "").endswith("_remote") or action.get("action") == "mkdir_remote":
            return True
    return False


def remote_path_exists(client: BaiduPanInventoryClient, remote_path: str) -> bool:
    return client.get_remote_entry(remote_path) is not None


def local_path_exists(local_path: str) -> bool:
    return Path(local_path).expanduser().exists()


def verify_manifest(manifest: dict) -> list[dict]:
    actions = manifest.get("actions", [])
    token = load_token()
    client = BaiduPanInventoryClient(token) if token and remote_needs_token(actions) else None
    results: list[dict] = []

    for action in actions:
        action_name = action.get("action", "unknown")
        row = {"action": action_name}

        for field in ["source", "target"]:
            value = action.get(field)
            if value is None:
                continue
            if action_name in REMOTE_KEYS.get(field, set()):
                if client is None:
                    row[f"{field}_exists"] = None
                else:
                    row[f"{field}_exists"] = remote_path_exists(client, normalize_remote_path(value))
            else:
                row[f"{field}_exists"] = local_path_exists(value)

        results.append(row)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘 manifest 验证工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("manifest_file")
    manifest_parser.add_argument("--limit", type=int, default=100)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command != "manifest":
        parser.print_help()
        return 1

    manifest = read_json(Path(args.manifest_file).expanduser().resolve())
    results = verify_manifest(manifest)
    total = len(results)
    source_ok = sum(1 for item in results if item.get("source_exists") is True)
    target_ok = sum(1 for item in results if item.get("target_exists") is True)
    print(f"actions: {total}")
    print(f"source_exists=true: {source_ok}")
    print(f"target_exists=true: {target_ok}")
    for item in results[: args.limit]:
        print(f"- {item}")
    if len(results) > args.limit:
        print(f"... 其余 {len(results) - args.limit} 条未显示")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
