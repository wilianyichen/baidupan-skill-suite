#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘技能项目的跨平台运行时工具。"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


TOKEN_ENV_VAR = "BYPY_TOKEN_FILE"
TOKEN_FILENAME = "bypy.token.json"
BYPY_NATIVE_TOKEN_FILENAME = "bypy.json"
BYPY_CONFIG_DIR_ENV = "BYPY_CONFIG_DIR"
DEFAULT_BYPY_DIRNAME = ".bypy"
BYPY_RUNTIME_DIRNAME = ".bypy_runtime"


def configure_stdio() -> None:
    """尽量把标准输出切到 UTF-8，减少 Windows 终端乱码。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            continue


def disable_proxy_env() -> None:
    """禁用代理环境变量，避免百度网盘 API 误走代理。"""
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ[key] = ""
    os.environ["NO_PROXY"] = "*"


def configure_runtime() -> None:
    configure_stdio()
    disable_proxy_env()


def get_repo_root(script_file: str) -> Path:
    return Path(script_file).resolve().parents[2]


def default_bypy_token_path() -> Path:
    return Path.home() / DEFAULT_BYPY_DIRNAME / TOKEN_FILENAME


def default_bypy_native_token_path() -> Path:
    return Path.home() / DEFAULT_BYPY_DIRNAME / BYPY_NATIVE_TOKEN_FILENAME


def token_candidates(script_file: str) -> list[Path]:
    repo_root = get_repo_root(script_file)
    cwd_token = Path.cwd() / TOKEN_FILENAME
    cwd_native_token = Path.cwd() / BYPY_NATIVE_TOKEN_FILENAME
    repo_token = repo_root / TOKEN_FILENAME
    repo_native_token = repo_root / BYPY_NATIVE_TOKEN_FILENAME

    candidates: list[Path] = []
    env_token = os.environ.get(TOKEN_ENV_VAR)
    if env_token:
        candidates.append(Path(os.path.expanduser(env_token)))

    candidates.append(default_bypy_token_path())
    candidates.append(default_bypy_native_token_path())
    candidates.append(cwd_token)
    candidates.append(cwd_native_token)
    if repo_token != cwd_token:
        candidates.append(repo_token)
    if repo_native_token != cwd_native_token:
        candidates.append(repo_native_token)

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate.expanduser().resolve(strict=False))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate.expanduser())
    return deduped


def resolve_token_file(script_file: str) -> Path | None:
    for candidate in token_candidates(script_file):
        if candidate.exists():
            return candidate
    return None


def describe_token_search_order(script_file: str) -> list[str]:
    return [str(path) for path in token_candidates(script_file)]


def load_token_data(script_file: str) -> tuple[Path, dict]:
    token_path = resolve_token_file(script_file)
    if token_path is None:
        raise FileNotFoundError("未找到可用的 token 文件")
    with open(token_path, "r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    return token_path, data


def load_access_token(script_file: str) -> str:
    _, data = load_token_data(script_file)
    token = data.get("access_token")
    if not token:
        raise KeyError("token 文件缺少 access_token 字段")
    return token


def ensure_bypy_token_file(script_file: str) -> Path:
    """确保 bypy 能从默认位置读到 token。

    优先级保持不变：
    1. 环境变量指定的 token
    2. ~/.bypy/bypy.token.json
    3. 当前工作目录 ./bypy.token.json
    4. 项目根目录 bypy.token.json

    如果命中了 3/4 且默认位置不存在，就复制到默认位置供 bypy 使用。
    """
    resolved = resolve_token_file(script_file)
    if resolved is None:
        raise FileNotFoundError("未找到可用的 token 文件")

    native_default_path = default_bypy_native_token_path()
    if native_default_path.exists():
        return native_default_path
    if resolved == native_default_path:
        return resolved

    native_default_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(resolved, native_default_path)
    return native_default_path


def prepare_bypy_config_dir(script_file: str) -> Path:
    """准备 bypy 可用的配置目录，并返回 configdir。"""
    env_config_dir = os.environ.get(BYPY_CONFIG_DIR_ENV)
    if env_config_dir:
        config_dir = Path(os.path.expanduser(env_config_dir))
    else:
        config_dir = Path.cwd() / BYPY_RUNTIME_DIRNAME

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        fallback = Path(tempfile.gettempdir()) / BYPY_RUNTIME_DIRNAME
        fallback.mkdir(parents=True, exist_ok=True)
        config_dir = fallback

    resolved = resolve_token_file(script_file)
    if resolved is None:
        raise FileNotFoundError("未找到可用的 token 文件")

    native_token_path = config_dir / BYPY_NATIVE_TOKEN_FILENAME
    if native_token_path.resolve(strict=False) != resolved.resolve(strict=False):
        shutil.copyfile(resolved, native_token_path)
    return config_dir


def python_command() -> str:
    return sys.executable or "python"


def shell_join(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return " ".join(shlex.quote(part) for part in parts)
