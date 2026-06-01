#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘 OAuth Token 自动刷新模块。

功能：
- 用 refresh_token 向百度 OAuth 换取新的 access_token
- 更新所有已配置位置的 token 文件
- 可独立运行或作为库调用
- 支持"--check-only"仅检查过期状态，不执行刷新

用法：
  # 主动刷新（用于 cron）
  python common/bdpan_refresh.py /path/to/script_using_token.py

  # 仅检查 token 是否即将过期（用于监控）
  python common/bdpan_refresh.py --check-only /path/to/script_using_token.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from .bdpan_runtime import configure_requests_session, request_timeout
except ImportError:
    from bdpan_runtime import configure_requests_session, request_timeout

# ── 百度 OAuth 常量 ──────────────────────────────────────────────
# 与 bypy 内置的一致，不走 bypy 服务器代理，直接调百度 API
CLIENT_ID = "q8WE4EpCsau1oS0MplgMKNBn"
CLIENT_SECRET = "PA4MhwB5RE7DacKtoP2i8ikCnNzAqYTD"
TOKEN_URL = "https://openapi.baidu.com/oauth/2.0/token"

# 过期前多少秒开始视为"需要刷新"（默认提前 5 天）
REFRESH_BEFORE_SECONDS = 5 * 24 * 3600  # 5 days

# 所有 token 文件候选位置（入参 script_file 决定仓库根目录）
TOKEN_FILENAME = "bypy.token.json"
BYPY_NATIVE_FILENAME = "bypy.json"


def _repo_root(script_file: str) -> Path:
    return Path(script_file).resolve().parents[2]


def _all_token_paths(script_file: str) -> list[Path]:
    """返回所有应该被更新的 token 文件路径（去重）。"""
    root = _repo_root(script_file)
    candidates = [
        Path.home() / ".bypy" / TOKEN_FILENAME,
        Path.home() / ".bypy" / BYPY_NATIVE_FILENAME,
        root / TOKEN_FILENAME,
        root / BYPY_NATIVE_FILENAME,
    ]
    seen: set[str] = set()
    result: list[Path] = []
    for p in candidates:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


def _load_refresh_token(script_file: str) -> tuple[str | None, list[Path]]:
    """从现有 token 文件中读取 refresh_token 和找到的文件列表。"""
    paths = _all_token_paths(script_file)
    for path in paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                rt = data.get("refresh_token")
                if rt:
                    return rt, paths
            except (json.JSONDecodeError, OSError):
                continue
    return None, paths


def save_token(script_file: str, access_token: str, refresh_token: str,
               expires_in: int = 2592000) -> list[str]:
    """将 token 数据写入所有候选位置，返回已写入的路径列表。"""
    now_ts = int(time.time())
    data = {
        "access_token": access_token,
        "expires_in": expires_in,
        "refresh_token": refresh_token,
        "scope": "basic netdisk",
        "session_key": "",
        "session_secret": "",
        "_obtained_at": now_ts,
        "_obtained_at_human": datetime.fromtimestamp(now_ts, tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    written: list[str] = []
    for path in _all_token_paths(script_file):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.chmod(path, 0o600)
            written.append(str(path))
        except OSError:
            pass
    return written


def refresh_access_token(script_file: str) -> dict:
    """用 refresh_token 向百度 OAuth 换取新的 access_token。

    Returns:
        {"access_token": str, "refresh_token": str, "expires_in": int}

    Raises:
        RuntimeError: 刷新失败
    """
    old_refresh_token, _ = _load_refresh_token(script_file)
    if not old_refresh_token:
        raise RuntimeError("找不到可用的 refresh_token，需要重新在浏览器授权")

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": old_refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    session = requests.Session()
    configure_requests_session(session)
    resp = session.post(TOKEN_URL, data=payload, timeout=request_timeout(30))
    result = resp.json()

    if resp.status_code != 200 or "error" in result:
        error_desc = result.get("error_description", result.get("error", "未知错误"))
        raise RuntimeError(f"Token 刷新失败: {error_desc}")

    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", old_refresh_token),
        "expires_in": result.get("expires_in", 2592000),
    }


def refresh_and_save(script_file: str) -> dict:
    """刷新 token 并保存到所有位置。返回新的 token 数据。"""
    new_data = refresh_access_token(script_file)
    written = save_token(
        script_file,
        access_token=new_data["access_token"],
        refresh_token=new_data["refresh_token"],
        expires_in=new_data["expires_in"],
    )
    new_data["_written"] = written
    return new_data


def check_status(script_file: str) -> dict:
    """检查 token 状态，不执行刷新。

    Returns:
        {"status": "ok"|"expired"|"expiring_soon"|"missing"|"no_refresh_token",
         "days_remaining": int|None,
         "obtained_at": str|None}
    """
    old_rt, paths = _load_refresh_token(script_file)
    if old_rt is None:
        return {"status": "missing", "days_remaining": None, "obtained_at": None}

    # 读取现有 access_token 和获取时间
    for path in paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                obtained_at = data.get("_obtained_at")
                expires_in = data.get("expires_in", 2592000)
                if obtained_at:
                    age = int(time.time()) - obtained_at
                    remaining = expires_in - age
                    days = remaining / 86400
                    expiry_time = obtained_at + expires_in
                    if remaining <= 0:
                        return {
                            "status": "expired",
                            "days_remaining": round(days, 1),
                            "obtained_at": datetime.fromtimestamp(
                                obtained_at, tz=timezone.utc
                            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "expires_at": datetime.fromtimestamp(
                                expiry_time, tz=timezone.utc
                            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                    if remaining <= REFRESH_BEFORE_SECONDS:
                        return {
                            "status": "expiring_soon",
                            "days_remaining": round(days, 1),
                            "obtained_at": datetime.fromtimestamp(
                                obtained_at, tz=timezone.utc
                            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "expires_at": datetime.fromtimestamp(
                                expiry_time, tz=timezone.utc
                            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                    return {
                        "status": "ok",
                        "days_remaining": round(days, 1),
                        "obtained_at": datetime.fromtimestamp(
                            obtained_at, tz=timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "expires_at": datetime.fromtimestamp(
                            expiry_time, tz=timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
            except (json.JSONDecodeError, OSError, KeyError):
                continue

    return {"status": "no_refresh_token", "days_remaining": None, "obtained_at": None}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="百度网盘 OAuth Token 自动刷新工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python bdpan_refresh.py /path/to/suite/bypy-enhanced/scripts/bdpan_enhanced.py
  python bdpan_refresh.py --check-only /path/to/suite/bypy-enhanced/scripts/bdpan_enhanced.py
        """,
    )
    parser.add_argument("script_file", help="工具套件中的任意脚本文件路径")
    parser.add_argument(
        "--check-only", action="store_true",
        help="仅检查 token 过期状态，不执行刷新",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="即使 token 未过期也强制刷新",
    )
    args = parser.parse_args()

    if args.check_only:
        status = check_status(args.script_file)
        print(f"状态: {status['status']}")
        if status.get("obtained_at"):
            print(f"获取时间: {status['obtained_at']}")
        if status.get("expires_at"):
            print(f"过期时间: {status['expires_at']}")
        if status.get("days_remaining") is not None:
            print(f"剩余天数: {status['days_remaining']:.1f}")
        sys.exit(0 if status["status"] == "ok" else 1)

    if not args.force:
        status = check_status(args.script_file)
        if status["status"] == "ok":
            print(f"Token 状态正常（{status['days_remaining']:.1f} 天后过期），跳过刷新")
            print(f"过期时间: {status.get('expires_at', '未知')}")
            return

    print("正在刷新百度网盘 access_token ...")
    try:
        result = refresh_and_save(args.script_file)
        print("✅ Token 刷新成功！")
        print(f"  已写入 {len(result['_written'])} 个位置:")
        for p in result["_written"]:
            print(f"    - {p}")
        print(f"  expires_in: {result['expires_in']} 秒 ({result['expires_in'] // 86400} 天)")
    except RuntimeError as e:
        print(f"❌ 刷新失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
