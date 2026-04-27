#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘本地/远端目录清单与树结构工具。"""

from __future__ import annotations

import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Dict

import requests


HEADERS = {"User-Agent": "netdisk;P2SP;3.0.20.80"}
LIST_URL = "https://pan.baidu.com/rest/2.0/xpan/file"


def normalize_remote_path(path: str) -> str:
    if not path:
        return "/"
    normalized = path.replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized or "/"


def format_size(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} PB"


def format_mtime(timestamp: int) -> str:
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def should_include(rel_path: str, includes: list[str] | None = None, excludes: list[str] | None = None) -> bool:
    includes = includes or []
    excludes = excludes or []
    include_match = True if not includes else any(fnmatch.fnmatch(rel_path, pattern) for pattern in includes)
    exclude_match = any(fnmatch.fnmatch(rel_path, pattern) for pattern in excludes)
    return include_match and not exclude_match


class BaiduPanInventoryClient:
    def __init__(self, token: str):
        self.token = token

    def list_dir(self, remote_path: str, missing_ok: bool = False) -> list[dict]:
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
                    if errno == -9 and missing_ok:
                        return []
                    raise RuntimeError(f"API 错误: {payload}")
                batch = payload.get("list", [])
                items.extend(batch)
                if len(batch) < limit:
                    break
                start += len(batch)
        finally:
            session.close()

        return items

    def get_remote_entry(self, remote_path: str) -> dict | None:
        remote_path = normalize_remote_path(remote_path)
        if remote_path == "/":
            return {
                "path": "/",
                "name": "/",
                "type": "dir",
                "size": 0,
                "mtime": 0,
                "children": {},
            }

        parent = normalize_remote_path(str(Path(remote_path).parent).replace("\\", "/"))
        if parent == ".":
            parent = "/"
        target_name = Path(remote_path).name
        for entry in self.list_dir(parent, missing_ok=True):
            name = entry.get("server_filename", entry.get("path", "").rsplit("/", 1)[-1])
            if name == target_name and normalize_remote_path(entry["path"]) == remote_path:
                return {
                    "path": remote_path,
                    "name": name,
                    "type": "dir" if entry.get("isdir", 0) == 1 else "file",
                    "size": int(entry.get("size", 0)),
                    "mtime": int(entry.get("server_mtime", 0)),
                }
        return None

    def build_remote_tree(self, remote_root: str) -> dict:
        remote_root = normalize_remote_path(remote_root)
        name = "/" if remote_root == "/" else Path(remote_root).name
        children: dict[str, dict] = {}

        for entry in sorted(self.list_dir(remote_root), key=lambda item: (item.get("isdir", 0) == 0, item.get("server_filename", ""))):
            child_name = entry.get("server_filename", entry.get("path", "").rsplit("/", 1)[-1])
            child_path = normalize_remote_path(entry["path"])
            if entry.get("isdir", 0) == 1:
                child = self.build_remote_tree(child_path)
            else:
                child = {
                    "name": child_name,
                    "path": child_path,
                    "type": "file",
                    "size": int(entry.get("size", 0)),
                    "mtime": int(entry.get("server_mtime", 0)),
                }
            children[child_name] = child

        return {
            "name": name,
            "path": remote_root,
            "type": "dir",
            "size": sum(child.get("size", 0) for child in children.values()),
            "mtime": max((child.get("mtime", 0) for child in children.values()), default=0),
            "children": children,
        }


def build_local_tree(local_root: Path) -> dict:
    local_root = local_root.expanduser().resolve()
    if not local_root.exists():
        raise FileNotFoundError(f"本地路径不存在: {local_root}")
    if not local_root.is_dir():
        raise NotADirectoryError(f"本地路径不是目录: {local_root}")

    def walk(path: Path) -> dict:
        if path.is_file():
            stat = path.stat()
            return {
                "name": path.name,
                "path": str(path),
                "type": "file",
                "size": int(stat.st_size),
                "mtime": int(stat.st_mtime),
            }

        children: dict[str, dict] = {}
        for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            children[child.name] = walk(child)

        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "type": "dir",
            "size": sum(child.get("size", 0) for child in children.values()),
            "mtime": int(stat.st_mtime),
            "children": children,
        }

    root = walk(local_root)
    root["name"] = local_root.name or str(local_root)
    return root


def tree_to_entries(root: dict, include_dirs: bool = True, include_files: bool = True) -> Dict[str, dict]:
    entries: Dict[str, dict] = {}

    def walk(node: dict, prefix: str = "") -> None:
        for child in node.get("children", {}).values():
            rel_path = child["name"] if not prefix else f"{prefix}/{child['name']}"
            if child.get("type") == "dir":
                if include_dirs:
                    entries[rel_path] = {
                        "relative_path": rel_path,
                        "absolute_path": child["path"],
                        "name": child["name"],
                        "type": "dir",
                        "size": child.get("size", 0),
                        "mtime": child.get("mtime", 0),
                    }
                walk(child, rel_path)
            elif include_files:
                entries[rel_path] = {
                    "relative_path": rel_path,
                    "absolute_path": child["path"],
                    "name": child["name"],
                    "type": "file",
                    "size": child.get("size", 0),
                    "mtime": child.get("mtime", 0),
                }

    walk(root)
    return entries


def scan_local_entries(
    local_root: Path,
    includes: list[str] | None = None,
    excludes: list[str] | None = None,
    include_dirs: bool = True,
    include_files: bool = True,
    allow_missing: bool = False,
) -> Dict[str, dict]:
    local_root = local_root.expanduser().resolve()
    if not local_root.exists():
        if allow_missing:
            return {}
        raise FileNotFoundError(f"本地目录不存在: {local_root}")
    if not local_root.is_dir():
        raise NotADirectoryError(f"本地路径不是目录: {local_root}")

    tree = build_local_tree(local_root)
    entries = tree_to_entries(tree, include_dirs=include_dirs, include_files=include_files)
    return {path: entry for path, entry in entries.items() if should_include(path, includes, excludes)}


def scan_remote_entries(
    client: BaiduPanInventoryClient,
    remote_root: str,
    includes: list[str] | None = None,
    excludes: list[str] | None = None,
    include_dirs: bool = True,
    include_files: bool = True,
) -> Dict[str, dict]:
    tree = client.build_remote_tree(remote_root)
    entries = tree_to_entries(tree, include_dirs=include_dirs, include_files=include_files)
    return {path: entry for path, entry in entries.items() if should_include(path, includes, excludes)}
