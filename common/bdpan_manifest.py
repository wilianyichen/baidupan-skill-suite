#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manifest 读写与摘要工具。"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def summarize_actions(actions: list[dict]) -> dict:
    counter = Counter(action.get("action", "unknown") for action in actions)
    return {
        "count": len(actions),
        "by_action": dict(sorted(counter.items())),
    }


def summarize_manifest(manifest: dict) -> dict:
    return {
        "tool": manifest.get("tool", "unknown"),
        "generated_at": manifest.get("generated_at", "-"),
        "action_summary": summarize_actions(manifest.get("actions", [])),
    }


def render_manifest_summary(manifest: dict) -> str:
    summary = summarize_manifest(manifest)
    lines = [
        f"tool: {summary['tool']}",
        f"generated_at: {summary['generated_at']}",
        f"actions: {summary['action_summary']['count']}",
    ]
    for action, count in summary["action_summary"]["by_action"].items():
        lines.append(f"  - {action}: {count}")
    return "\n".join(lines)


def merge_manifests(manifests: list[dict], tool_name: str = "baidupan-batch-runner") -> dict:
    merged_actions: list[dict] = []
    sources: list[str] = []
    for manifest in manifests:
        merged_actions.extend(manifest.get("actions", []))
        source = manifest.get("source_manifest")
        if source:
            sources.append(source)
    return {
        "tool": tool_name,
        "generated_at": now_iso(),
        "actions": merged_actions,
        "sources": sources,
    }


def render_runbook(manifest: dict, limit: int | None = None) -> str:
    actions = manifest.get("actions", [])
    lines = [
        "Manifest Runbook",
        "=" * 60,
        render_manifest_summary(manifest),
        "",
        "[actions]",
    ]
    visible_actions = actions if limit is None else actions[:limit]
    for index, action in enumerate(visible_actions, start=1):
        lines.append(f"{index}. {action.get('action', 'unknown')} -> {json.dumps(action, ensure_ascii=False)}")
    if limit is not None and len(actions) > limit:
        lines.append(f"... 其余 {len(actions) - limit} 条未显示")
    return "\n".join(lines)
