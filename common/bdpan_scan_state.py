#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘长扫描任务状态记录。

当前 checkpoint 用于观测和审计长任务进度。由于百度 listall cursor 可能短期有效，
恢复时默认从头扫描，避免目录变化后产生不一致统计。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .bdpan_runtime import BYPY_RUNTIME_DIRNAME, get_repo_root


def _safe_name(remote_path: str) -> str:
    digest = hashlib.sha256(remote_path.encode("utf-8")).hexdigest()[:16]
    slug = remote_path.strip("/").replace("/", "__") or "root"
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "_" for ch in slug)
    return f"{slug[:80]}-{digest}.json"


class ScanCheckpoint:
    def __init__(self, script_file: str, remote_path: str):
        root = get_repo_root(script_file)
        self.path = root / BYPY_RUNTIME_DIRNAME / "listall-checkpoints" / _safe_name(remote_path)

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        tmp.replace(self.path)
