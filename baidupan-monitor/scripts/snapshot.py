#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快照存储工具。"""

from __future__ import annotations

import gzip
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def slugify_remote_path(remote_path: str) -> str:
    normalized = remote_path.strip() or "/"
    normalized = normalized.strip("/").replace("/", "__")
    normalized = re.sub(r"[^0-9A-Za-z_\-.]+", "_", normalized)
    return normalized or "root"


def get_snapshot_dir() -> Path:
    override = os.environ.get("BDPAN_SNAPSHOT_DIR")
    candidates = snapshot_dir_candidates(override)

    last_error: Exception | None = None
    for target in candidates:
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError as exc:
            last_error = exc
            continue

    raise OSError(f"无法创建快照目录: {last_error}")


def snapshot_dir_candidates(override: str | None = None) -> list[Path]:
    candidates: list[Path] = []
    if override:
        candidates.append(Path(os.path.expanduser(override)))
    else:
        candidates.extend(
            [
                PROJECT_ROOT / ".bdpan_snapshots",
                Path.home() / ".bdpan_snapshots",
                Path.cwd() / ".bdpan_snapshots",
                Path(tempfile.gettempdir()) / ".bdpan_snapshots",
            ]
        )
    return candidates


def resolve_snapshot_path(remote_path: str, name: str | None = None) -> Path:
    filename = f"{name or slugify_remote_path(remote_path)}.json.gz"
    for base_dir in snapshot_dir_candidates(os.environ.get("BDPAN_SNAPSHOT_DIR")):
        candidate = base_dir / filename
        if candidate.exists():
            return candidate
    return get_snapshot_dir() / filename


def normalize_remote_path(path: str) -> str:
    if not path:
        return "/"
    normalized = path.replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized or "/"


def format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} PB"


def format_mtime(timestamp: int) -> str:
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


class MonitoredSnapshot:
    """把监视快照视为一个可查询、可导出的对象。"""

    def __init__(self, remote_path: str, root: dict, generated_at: str | None = None, snapshot_path: Path | None = None):
        self.remote_path = normalize_remote_path(remote_path)
        self.root = root
        self.generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
        self.snapshot_path = snapshot_path

    @classmethod
    def from_root(cls, remote_path: str, root: dict, snapshot_path: Path | None = None) -> "MonitoredSnapshot":
        return cls(remote_path=remote_path, root=root, snapshot_path=snapshot_path)

    @classmethod
    def from_dict(cls, payload: dict, snapshot_path: Path | None = None) -> "MonitoredSnapshot":
        return cls(
            remote_path=payload["remote_path"],
            root=payload["root"],
            generated_at=payload.get("generated_at"),
            snapshot_path=snapshot_path,
        )

    @classmethod
    def load(cls, path: Path) -> "MonitoredSnapshot":
        return cls.from_dict(load_snapshot(path), snapshot_path=path)

    def to_dict(self) -> dict:
        return {
            "remote_path": self.remote_path,
            "generated_at": self.generated_at,
            "root": self.root,
        }

    def save(self, path: Path | None = None) -> Path:
        target = path or self.snapshot_path
        if target is None:
            raise ValueError("缺少 snapshot_path，无法保存快照")
        save_snapshot(self.to_dict(), target)
        self.snapshot_path = target
        return target

    def resolve_branch_path(self, branch: str | None = None) -> str:
        if not branch or branch in {".", "/"}:
            return self.remote_path

        branch = branch.strip()
        if branch.startswith("/"):
            return normalize_remote_path(branch)

        if self.remote_path == "/":
            return normalize_remote_path(branch)
        return normalize_remote_path(f"{self.remote_path.rstrip('/')}/{branch}")

    def find_node(self, branch: str | None = None) -> dict:
        target_path = self.resolve_branch_path(branch)
        if target_path == self.root["path"]:
            return self.root

        root_path = normalize_remote_path(self.root["path"])
        if root_path != "/" and target_path.startswith(root_path.rstrip("/") + "/"):
            relative_target = target_path[len(root_path.rstrip("/")) :].strip("/")
        else:
            relative_target = target_path.strip("/")

        current = self.root
        for part in relative_target.split("/"):
            if not part:
                continue
            child = current.get("children", {}).get(part)
            if child is None:
                raise KeyError(f"分支不存在: {target_path}")
            current = child
        return current

    def render_tree(self, branch: str | None = None, max_depth: int | None = None) -> str:
        branch_node = self.find_node(branch)
        lines: list[str] = []
        branch_path = branch_node["path"]

        def render_label(node: dict) -> str:
            if node.get("type") == "dir":
                child_count = len(node.get("children", {}))
                return f"📁 {node.get('name', node['path'])} ({format_size(int(node.get('size', 0)))}, {child_count} items, {format_mtime(node.get('mtime', 0))})"
            return f"📄 {node.get('name', node['path'])} ({format_size(int(node.get('size', 0)))}, {format_mtime(node.get('mtime', 0))})"

        def walk(node: dict, prefix: str, depth: int) -> None:
            children = list(node.get("children", {}).values())
            for index, child in enumerate(children):
                is_last = index == len(children) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{render_label(child)}")
                if child.get("type") == "dir" and (max_depth is None or depth < max_depth):
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    walk(child, next_prefix, depth + 1)

        lines.append(f"📁 {branch_path}")
        lines.append("=" * 60)
        walk(branch_node, "", 1)
        return "\n".join(lines)

    def export_tree(self, output_path: Path, branch: str | None = None, max_depth: int | None = None) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = self.render_tree(branch=branch, max_depth=max_depth)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        return output_path

    def _normalized_segment(self, node: dict, ignore_extension: bool) -> str:
        name = node.get("name", "")
        if node.get("type") == "file" and ignore_extension:
            return Path(name).stem
        return name

    def _collect_branch_index(self, branch: str | None = None, ignore_extension: bool = False) -> tuple[dict[str, list[dict]], list[dict]]:
        branch_node = self.find_node(branch)
        index: dict[str, list[dict]] = {}
        collisions: list[dict] = []

        def register(rel_path: str, node: dict) -> None:
            payload = {
                "relative_path": rel_path,
                "original_path": node["path"],
                "name": node.get("name"),
                "type": node.get("type"),
            }
            index.setdefault(rel_path, []).append(payload)
            if len(index[rel_path]) == 2:
                collisions.append(
                    {
                        "relative_path": rel_path,
                        "entries": index[rel_path],
                    }
                )

        def walk(node: dict, prefix: str) -> None:
            for child in node.get("children", {}).values():
                segment = self._normalized_segment(child, ignore_extension=ignore_extension)
                rel_path = segment if not prefix else f"{prefix}/{segment}"
                register(rel_path, child)
                if child.get("type") == "dir":
                    walk(child, rel_path)

        walk(branch_node, "")
        return index, collisions

    def compare_branches(self, left_branch: str, right_branch: str, ignore_extension: bool = False) -> dict:
        left_path = self.resolve_branch_path(left_branch)
        right_path = self.resolve_branch_path(right_branch)
        left_index, left_collisions = self._collect_branch_index(left_branch, ignore_extension=ignore_extension)
        right_index, right_collisions = self._collect_branch_index(right_branch, ignore_extension=ignore_extension)

        left_keys = set(left_index)
        right_keys = set(right_index)
        common_keys = sorted(left_keys & right_keys)

        type_mismatches: list[dict] = []
        for rel_path in common_keys:
            left_types = sorted({entry["type"] for entry in left_index[rel_path]})
            right_types = sorted({entry["type"] for entry in right_index[rel_path]})
            if left_types != right_types:
                type_mismatches.append(
                    {
                        "relative_path": rel_path,
                        "left_entries": left_index[rel_path],
                        "right_entries": right_index[rel_path],
                    }
                )

        return {
            "left_branch": left_path,
            "right_branch": right_path,
            "ignore_extension": ignore_extension,
            "left_only": [left_index[key] for key in sorted(left_keys - right_keys)],
            "right_only": [right_index[key] for key in sorted(right_keys - left_keys)],
            "type_mismatches": type_mismatches,
            "left_collisions": left_collisions,
            "right_collisions": right_collisions,
            "matched_count": len(common_keys) - len(type_mismatches),
        }

    def render_comparison(self, left_branch: str, right_branch: str, ignore_extension: bool = False, limit: int | None = None) -> str:
        report = self.compare_branches(left_branch, right_branch, ignore_extension=ignore_extension)
        lines = [
            "分支结构比较",
            "=" * 60,
            f"左侧：{report['left_branch']}",
            f"右侧：{report['right_branch']}",
            f"忽略扩展名：{'是' if report['ignore_extension'] else '否'}",
            f"匹配项：{report['matched_count']}",
            f"仅左侧存在：{len(report['left_only'])}",
            f"仅右侧存在：{len(report['right_only'])}",
            f"类型不一致：{len(report['type_mismatches'])}",
            f"左侧归一化冲突：{len(report['left_collisions'])}",
            f"右侧归一化冲突：{len(report['right_collisions'])}",
        ]

        def flatten(entries: list[list[dict]]) -> list[dict]:
            return [group[0] for group in entries]

        def append_section(title: str, entries: list[dict], formatter) -> None:
            if not entries:
                return
            lines.append("")
            lines.append(f"[{title}]")
            display_entries = entries if limit is None else entries[:limit]
            for entry in display_entries:
                lines.append(formatter(entry))
            if limit is not None and len(entries) > limit:
                lines.append(f"... 其余 {len(entries) - limit} 条未显示")

        append_section("仅左侧存在", flatten(report["left_only"]), lambda entry: f"- {entry['relative_path']} ({entry['type']})")
        append_section("仅右侧存在", flatten(report["right_only"]), lambda entry: f"- {entry['relative_path']} ({entry['type']})")
        append_section(
            "类型不一致",
            report["type_mismatches"],
            lambda entry: f"- {entry['relative_path']} (left={','.join(sorted({item['type'] for item in entry['left_entries']}))}, right={','.join(sorted({item['type'] for item in entry['right_entries']}))})",
        )
        append_section(
            "左侧归一化冲突",
            report["left_collisions"],
            lambda entry: f"- {entry['relative_path']} -> {', '.join(item['original_path'] for item in entry['entries'])}",
        )
        append_section(
            "右侧归一化冲突",
            report["right_collisions"],
            lambda entry: f"- {entry['relative_path']} -> {', '.join(item['original_path'] for item in entry['entries'])}",
        )
        return "\n".join(lines)

    def export_comparison(
        self,
        output_path: Path,
        left_branch: str,
        right_branch: str,
        ignore_extension: bool = False,
        limit: int | None = None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = self.render_comparison(left_branch, right_branch, ignore_extension=ignore_extension, limit=limit)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        return output_path


def save_snapshot(snapshot: dict, path: Path) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)


def load_snapshot(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)
