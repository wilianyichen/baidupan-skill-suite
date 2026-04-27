#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘目录快照与差异计算。"""

from __future__ import annotations

import hashlib
from typing import Dict, List


def _digest(parts: List[str]) -> str:
    md5 = hashlib.md5()
    md5.update("|".join(parts).encode("utf-8"))
    return md5.hexdigest()


def file_signature(path: str, size: int, mtime: int) -> str:
    """基于路径、大小、修改时间生成文件签名。"""
    return _digest([path, str(size), str(mtime)])


def directory_signature(children: Dict[str, dict]) -> str:
    """根据子节点签名生成目录签名。"""
    parts = []
    for name in sorted(children):
        child = children[name]
        parts.append(f"{name}:{child.get('hash', '')}:{child.get('type', '')}")
    return _digest(parts)


def build_file_node(entry: dict) -> dict:
    """从 API 条目构造文件节点。"""
    path = entry["path"]
    size = int(entry.get("size", 0))
    mtime = int(entry.get("server_mtime", 0))
    return {
        "path": path,
        "name": entry.get("server_filename", path.rsplit("/", 1)[-1]),
        "type": "file",
        "size": size,
        "mtime": mtime,
        "hash": file_signature(path, size, mtime),
    }


def build_dir_node(path: str, children: Dict[str, dict]) -> dict:
    """构造目录节点。"""
    child_values = list(children.values())
    return {
        "path": path,
        "name": path.rstrip("/").rsplit("/", 1)[-1] if path != "/" else "/",
        "type": "dir",
        "size": sum(child.get("size", 0) for child in child_values),
        "mtime": max((child.get("mtime", 0) for child in child_values), default=0),
        "file_count": sum(1 for child in child_values if child.get("type") == "file"),
        "dir_count": sum(1 for child in child_values if child.get("type") == "dir"),
        "children": children,
        "hash": directory_signature(children),
    }


def flatten_nodes(node: dict) -> Dict[str, dict]:
    """把树结构拍平成 path -> 节点摘要。"""
    flattened: Dict[str, dict] = {}

    def walk(current: dict) -> None:
        flattened[current["path"]] = {
            "path": current["path"],
            "name": current.get("name"),
            "type": current.get("type"),
            "size": current.get("size", 0),
            "mtime": current.get("mtime", 0),
            "hash": current.get("hash"),
            "file_count": current.get("file_count", 0),
            "dir_count": current.get("dir_count", 0),
        }
        for child in current.get("children", {}).values():
            walk(child)

    walk(node)
    return flattened


def diff_snapshots(old_root: dict, new_root: dict) -> List[dict]:
    """比较两个快照并返回变化列表。"""
    old_map = flatten_nodes(old_root)
    new_map = flatten_nodes(new_root)

    changes: List[dict] = []
    all_paths = sorted(set(old_map) | set(new_map))

    for path in all_paths:
        old_node = old_map.get(path)
        new_node = new_map.get(path)

        if old_node is None:
            changes.append({"kind": "added", "path": path, "new": new_node})
            continue
        if new_node is None:
            changes.append({"kind": "removed", "path": path, "old": old_node})
            continue
        if old_node["hash"] != new_node["hash"] or old_node["type"] != new_node["type"]:
            changes.append({"kind": "modified", "path": path, "old": old_node, "new": new_node})

    return changes
