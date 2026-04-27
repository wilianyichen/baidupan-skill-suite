#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘 manifest 执行器。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_inventory import BaiduPanInventoryClient, format_mtime, normalize_remote_path
from common.bdpan_manifest import now_iso, read_json, render_manifest_summary, write_json
from common.bdpan_runtime import configure_runtime, describe_token_search_order, load_access_token


HEADERS = {"User-Agent": "netdisk;P2SP;3.0.20.80"}
PCS_FILE_URL = "https://pcs.baidu.com/rest/2.0/pcs/file"
XPAN_FILE_URL = "https://pan.baidu.com/rest/2.0/xpan/file"
SUPPORTED_ACTIONS = {"archive_remote", "mkdir_remote", "move_remote", "rename_remote"}

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


def parent_remote_path(remote_path: str) -> str:
    remote_path = normalize_remote_path(remote_path)
    parent = normalize_remote_path(str(Path(remote_path).parent).replace("\\", "/"))
    return "/" if parent == "." else parent


class RemoteMutator:
    def __init__(self, token: str):
        self.token = token
        self.inventory = BaiduPanInventoryClient(token)
        self.session = requests.Session()
        self.session.trust_env = False
        self.mkdir_cache: set[str] = set()

    def close(self) -> None:
        self.session.close()

    def _post_pcs(self, method: str, **params) -> dict:
        payload = {"method": method, "access_token": self.token, **params}
        response = self.session.post(PCS_FILE_URL, params=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()

    def _post_xpan_filemanager(self, opera: str, filelist: list[dict]) -> dict:
        params = {"method": "filemanager", "access_token": self.token, "opera": opera}
        data = {
            "async": "0",
            "filelist": json.dumps(filelist, ensure_ascii=False),
        }
        response = self.session.post(XPAN_FILE_URL, params=params, data=data, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()

    def remote_exists(self, remote_path: str) -> bool:
        return self.inventory.get_remote_entry(normalize_remote_path(remote_path)) is not None

    def remote_entry(self, remote_path: str) -> dict | None:
        return self.inventory.get_remote_entry(normalize_remote_path(remote_path))

    def ensure_remote_dir(self, remote_dir: str) -> tuple[bool, str]:
        remote_dir = normalize_remote_path(remote_dir)
        if remote_dir in {"", "/"}:
            return False, "root"
        if remote_dir in self.mkdir_cache:
            return False, "cached"
        existing = self.remote_entry(remote_dir)
        if existing is not None:
            if existing.get("type") != "dir":
                raise RuntimeError(f"目标路径已被文件占用: {remote_dir}")
            self.mkdir_cache.add(remote_dir)
            return False, "exists"

        parent = parent_remote_path(remote_dir)
        if parent != remote_dir:
            self.ensure_remote_dir(parent)

        result = self._post_pcs("mkdir", path=remote_dir)
        errno = result.get("errno", 0)
        if errno not in {0, -30}:
            raise RuntimeError(f"mkdir 失败: {remote_dir}, result={result}")
        self.mkdir_cache.add(remote_dir)
        return True, "created"

    def move_remote(self, source: str, target: str) -> dict:
        source = normalize_remote_path(source)
        target = normalize_remote_path(target)
        target_parent = parent_remote_path(target)
        target_name = Path(target).name
        self.ensure_remote_dir(target_parent)
        result = self._post_xpan_filemanager(
            "move",
            [{"path": source, "dest": target_parent, "newname": target_name, "ondup": "fail"}],
        )
        errno = result.get("errno", 0)
        if errno != 0:
            raise RuntimeError(f"move 失败: {source} -> {target}, result={result}")
        return result


def build_log(manifest: dict, mode: str) -> dict:
    return {
        "tool": "baidupan-apply",
        "generated_at": now_iso(),
        "mode": mode,
        "source_manifest": manifest,
        "results": [],
    }


def preview_manifest(manifest: dict) -> str:
    actions = manifest.get("actions", [])
    lines = [
        "Manifest Preview",
        "=" * 60,
        render_manifest_summary(manifest),
        "",
        "[actions]",
    ]
    for index, action in enumerate(actions, start=1):
        lines.append(f"{index}. {action.get('action')} -> {json.dumps(action, ensure_ascii=False)}")
    return "\n".join(lines)


def validate_actions(manifest: dict) -> None:
    unsupported = sorted({action.get("action", "unknown") for action in manifest.get("actions", []) if action.get("action") not in SUPPORTED_ACTIONS})
    if unsupported:
        raise ValueError(f"manifest 含有当前执行器不支持的动作: {', '.join(unsupported)}")


def execute_manifest(manifest: dict, continue_on_error: bool = False) -> dict:
    validate_actions(manifest)
    token = load_token()
    mutator = RemoteMutator(token)
    log = build_log(manifest, mode="execute")

    try:
        for index, action in enumerate(manifest.get("actions", []), start=1):
            action_name = action.get("action")
            row = {
                "index": index,
                "action": action_name,
                "status": "pending",
                "started_at": now_iso(),
                "source": action.get("source"),
                "target": action.get("target"),
            }
            try:
                if action_name == "mkdir_remote":
                    created, reason = mutator.ensure_remote_dir(action["target"])
                    row["status"] = "created" if created else "skipped"
                    row["detail"] = reason
                elif action_name in {"move_remote", "rename_remote", "archive_remote"}:
                    source = normalize_remote_path(action["source"])
                    target = normalize_remote_path(action["target"])
                    source_entry = mutator.remote_entry(source)
                    if source_entry is None:
                        raise RuntimeError(f"source 不存在: {source}")
                    if mutator.remote_entry(target) is not None:
                        raise RuntimeError(f"target 已存在: {target}")
                    mutator.move_remote(source, target)
                    row["status"] = "applied"
                    row["detail"] = "moved"
                else:
                    raise RuntimeError(f"不支持的动作: {action_name}")
            except Exception as exc:  # noqa: BLE001
                row["status"] = "failed"
                row["error"] = str(exc)
                log["results"].append(row)
                if not continue_on_error:
                    break
            else:
                log["results"].append(row)
    finally:
        mutator.close()

    return log


def render_execution_log(log: dict) -> str:
    results = log.get("results", [])
    succeeded = sum(1 for row in results if row.get("status") in {"created", "skipped", "applied"})
    failed = sum(1 for row in results if row.get("status") == "failed")
    lines = [
        "Apply Result",
        "=" * 60,
        f"mode: {log.get('mode')}",
        f"generated_at: {log.get('generated_at')}",
        f"results: {len(results)}",
        f"succeeded_or_skipped: {succeeded}",
        f"failed: {failed}",
        "",
        "[results]",
    ]
    for row in results:
        base = f"{row['index']}. {row['action']} [{row['status']}]"
        if row.get("source") or row.get("target"):
            base += f" source={row.get('source')} target={row.get('target')}"
        if row.get("detail"):
            base += f" detail={row['detail']}"
        if row.get("error"):
            base += f" error={row['error']}"
        lines.append(base)
    return "\n".join(lines)


def write_log(log: dict, path: str | None) -> None:
    if not path:
        return
    output_path = Path(path).expanduser().resolve()
    write_json(output_path, log)
    print(f"✅ 执行日志已保存到: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘 manifest 执行器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("manifest_file")
    manifest_parser.add_argument("--execute", action="store_true", help="真正执行 manifest")
    manifest_parser.add_argument("--yes", action="store_true", help="与 --execute 一起使用，表示已人工确认")
    manifest_parser.add_argument("--continue-on-error", action="store_true", help="某条失败后继续后续动作")
    manifest_parser.add_argument("--log", help="保存执行日志 JSON")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command != "manifest":
        parser.print_help()
        return 1

    manifest = read_json(Path(args.manifest_file).expanduser().resolve())
    validate_actions(manifest)

    if not args.execute:
        print(preview_manifest(manifest))
        print("\n⚠️ 当前为预览模式。需要真正执行时，使用 --execute --yes。")
        return 0

    if not args.yes:
        print("❌ 执行模式需要显式确认：请同时传入 --execute --yes")
        return 1

    log = execute_manifest(manifest, continue_on_error=args.continue_on_error)
    rendered = render_execution_log(log)
    print(rendered)
    write_log(log, args.log)

    if any(row.get("status") == "failed" for row in log.get("results", [])):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
