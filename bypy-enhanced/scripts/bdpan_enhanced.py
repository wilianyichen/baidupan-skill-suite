#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增强版百度网盘命令行工具。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_client import (  # noqa: E402
    BaiduNetdiskClient,
    DOWNLOAD_HEADERS,
    HEADERS,
    PCS_FILE_URL,
    XPN_FILE_URL,
    format_size,
    format_time,
    normalize_remote_path,
)
from common.bdpan_inventory import file_suffix  # noqa: E402
from common.bdpan_runtime import (  # noqa: E402
    configure_requests_session,
    configure_runtime,
    describe_token_search_order,
    load_access_token,
    project_python,
    request_timeout,
)

configure_runtime()


def get_token() -> str:
    """获取访问令牌。"""
    try:
        return load_access_token(__file__)
    except (FileNotFoundError, KeyError) as exc:
        print(f"❌ {exc}")
        print("   已检查：")
        for candidate in describe_token_search_order(__file__):
            print(f"   - {candidate}")
        print("   可通过环境变量 BYPY_TOKEN_FILE 指定 token 文件")
        raise SystemExit(1) from exc


def request_api(api_path: str, params: dict[str, Any] | None = None, method: str = "GET") -> dict[str, Any]:
    """调用百度 XPAN API。"""
    url = f"https://pan.baidu.com/rest/2.0/xpan{api_path}"
    client = BaiduNetdiskClient(__file__)
    try:
        return client.request_json(url, params=params or {}, method=method)
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        raise SystemExit(1) from exc
    finally:
        client.close()


def list_files(path: str = "/") -> list[dict[str, Any]]:
    """列出目录文件。"""
    client = BaiduNetdiskClient(__file__)
    try:
        return client.list_dir(path)
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(f"❌ {exc}")
        raise SystemExit(1) from exc
    finally:
        client.close()


def get_quota() -> dict[str, Any]:
    """获取网盘容量信息。"""
    client = BaiduNetdiskClient(__file__)
    try:
        return client.get_quota()
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(f"❌ {exc}")
        raise SystemExit(1) from exc
    finally:
        client.close()


def summarize_remote_path(path: str, *, use_checkpoint: bool = False, resume: bool = False) -> dict[str, Any]:
    """递归统计目录大小，文件路径则返回单文件统计。"""
    client = BaiduNetdiskClient(__file__)
    try:
        return client.summarize_path(path, use_checkpoint=use_checkpoint, resume=resume)
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(f"❌ {exc}")
        raise SystemExit(1) from exc
    finally:
        client.close()


def remote_relative_path(remote_root: str, remote_path: str) -> str:
    root = normalize_remote_path(remote_root).rstrip("/")
    path = normalize_remote_path(remote_path)
    if root == "":
        return path.lstrip("/")
    if path == root:
        return ""
    prefix = root + "/"
    if path.startswith(prefix):
        return path[len(prefix) :]
    return path.lstrip("/")


def build_tree_node(path: str = "/", depth: int = 2, current_depth: int = 0, size_mode: str = "none") -> dict[str, Any]:
    """构建目录树。

    size_mode:
    - none: 目录大小不计算
    - shallow: 只累计已经展开层级内的文件大小
    - recursive: 对展示出的目录逐个递归统计完整大小
    """
    files = list_files(path)
    children: list[dict[str, Any]] = []
    total_size = 0
    max_mtime = 0

    for entry in files:
        name = entry.get("server_filename", "unknown")
        item_path = entry.get("path", "")
        entry_mtime = int(entry.get("server_mtime", 0))
        is_dir = int(entry.get("isdir", 0)) == 1

        if is_dir:
            if current_depth < depth:
                child = build_tree_node(item_path, depth=depth, current_depth=current_depth + 1, size_mode=size_mode)
                child["name"] = name
                child["path"] = item_path
                child["mtime"] = max(entry_mtime, int(child.get("mtime", 0)))
            else:
                child = {
                    "name": name,
                    "path": item_path,
                    "type": "dir",
                    "size": None,
                    "mtime": entry_mtime,
                    "children": [],
                    "size_computed": False,
                }
            if size_mode == "recursive" and current_depth < depth:
                summary = summarize_remote_path(item_path)
                child["size"] = int(summary["total_size"])
                child["size_computed"] = True
        else:
            child = {
                "name": name,
                "path": item_path,
                "type": "file",
                "size": int(entry.get("size", 0)),
                "mtime": entry_mtime,
                "children": [],
                "size_computed": True,
            }

        child_size = child.get("size")
        if isinstance(child_size, int):
            total_size += child_size
        max_mtime = max(max_mtime, int(child.get("mtime", 0)))
        if current_depth < depth:
            children.append(child)

    node_size: int | None
    if size_mode in {"shallow", "recursive"}:
        node_size = total_size
    else:
        node_size = None

    return {
        "name": "/" if path == "/" else Path(path).name,
        "path": path,
        "type": "dir",
        "size": node_size,
        "mtime": max_mtime,
        "children": children,
        "size_computed": size_mode in {"shallow", "recursive"},
    }


def render_size(value: Any, *, directory: bool = False) -> str:
    if isinstance(value, int):
        return format_size(value)
    if directory:
        return "size not computed"
    return "-"


def render_tree_node(node: dict[str, Any], prefix: str = "", current_depth: int = 0) -> None:
    """渲染树节点。"""
    for index, child in enumerate(node.get("children", [])):
        is_last = index == len(node["children"]) - 1
        connector = "" if current_depth == 0 else ("└── " if is_last else "├── ")
        if child["type"] == "dir":
            print(f"{prefix}{connector}📁 {child['name']} ({render_size(child.get('size'), directory=True)})")
            new_prefix = prefix + ("    " if is_last else "│   ")
            render_tree_node(child, new_prefix, current_depth + 1)
        else:
            print(f"{prefix}{connector}📄 {child['name']} ({format_size(int(child['size']))}, {format_time(int(child['mtime']))})")


def tree_print(path: str = "/", depth: int = 2, size_mode: str = "none") -> None:
    """打印目录树。"""
    tree = build_tree_node(path, depth=depth, current_depth=0, size_mode=size_mode)
    render_tree_node(tree, current_depth=0)


def cmd_info(args: argparse.Namespace) -> int:
    """显示账户信息。"""
    result = get_quota()
    total = int(result["total"])
    used = int(result["used"])
    free = total - used
    print("📊 百度网盘账户信息")
    print("=" * 50)
    print(f"总容量：{format_size(total)}")
    print(f"已使用：{format_size(used)}")
    print(f"剩余：{format_size(free)}")
    if total > 0:
        print(f"使用率：{used / total * 100:.1f}%")
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    """显示当前授权用户。"""
    client = BaiduNetdiskClient(__file__)
    try:
        info = client.get_user_info()
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    finally:
        client.close()
    print("👤 百度网盘授权用户")
    print("=" * 50)
    print(f"百度用户名：{info.get('baidu_name', '-')}")
    print(f"网盘名：{info.get('netdisk_name') or '-'}")
    print(f"UK：{info.get('uk', '-')}")
    print(f"VIP 类型：{info.get('vip_type', '-')}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """检查当前环境是否已具备运行条件。"""
    issues: list[str] = []
    warnings: list[str] = []
    suite_root = REPO_ROOT
    python_path = project_python(__file__)
    current_python = Path(sys.executable).resolve()
    print("🩺 百度网盘工具自检")
    print("=" * 60)
    print(f"suite_root: {suite_root}")
    print(f"recommended_python: {python_path}")
    print(f"current_python: {current_python}")
    print(f"proxy_mode: {os.environ.get('BDPAN_PROXY_MODE', 'auto')}")

    if python_path.exists():
        print("✅ 推荐虚拟环境 Python 存在")
    elif current_python.exists() and current_python.name.startswith('python'):
        warnings.append(f"未找到仓库内 .venv，当前将使用外部 Python：{current_python}")
    else:
        issues.append(f"未找到可用 Python：推荐路径 {python_path} 不存在")

    try:
        token = get_token()
        print("✅ 已找到 token 文件")
        print(f"   access_token length: {len(token)}")
    except SystemExit:
        issues.append("未找到可用 token")

    try:
        from common.bdpan_refresh import authorization_url, check_status

        status = check_status(__file__)
        print(f"token_status: {status['status']}")
        if status.get('expires_at'):
            print(f"token_expires_at: {status['expires_at']}")
        if status['status'] in {'expired', 'expiring_soon', 'missing', 'no_refresh_token'}:
            warnings.append(f"token 状态为 {status['status']}")
        print(f"auth_url: {authorization_url()}")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"无法检查 token 状态：{exc}")

    claude_skill_dir = Path.home() / '.claude' / 'skills' / 'baidupan-suite'
    if claude_skill_dir.exists():
        print(f"✅ 检测到 Claude skill: {claude_skill_dir}")
    else:
        warnings.append(f"未检测到 Claude skill 安装：{claude_skill_dir}")

    codex_skill_dir = Path.home() / '.codex' / 'skills' / 'baidupan-suite'
    if codex_skill_dir.exists():
        print(f"✅ 检测到 Codex skill: {codex_skill_dir}")
    else:
        warnings.append(f"未检测到 Codex skill 安装：{codex_skill_dir}")

    if warnings:
        print()
        print("⚠️ 警告")
        for item in warnings:
            print(f"- {item}")

    if issues:
        print()
        print("❌ 阻塞项")
        for item in issues:
            print(f"- {item}")
        print()
        print("建议：")
        print(f"- 如未创建虚拟环境，先运行: python3 {suite_root / 'scripts' / 'bootstrap_min_venv.py'}")
        print(f"- 再运行: {project_python(__file__)} {suite_root / 'bypy-enhanced' / 'scripts' / 'bdpan_enhanced.py'} auth")
        return 1

    print()
    print("✅ 自检通过")
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    """打印授权链接或用授权码换 token，并执行最小验证。"""
    from common.bdpan_refresh import authorize_and_save, authorization_url, check_status

    print("🔐 百度网盘授权向导")
    print("=" * 60)
    print("1. 在浏览器打开下面链接并授权：")
    print(authorization_url())
    print("2. 拿到 Authorization Code 后再次执行：")
    print(f"   {project_python(__file__)} {Path(__file__).resolve()} auth --code <YOUR_CODE>")

    if not args.code:
        status = check_status(__file__)
        print()
        print(f"当前 token 状态：{status['status']}")
        return 0

    try:
        result = authorize_and_save(__file__, args.code.strip())
    except RuntimeError as exc:
        print(f"❌ 授权失败：{exc}")
        return 1

    print("✅ 授权成功，token 已写入：")
    for path in result['_written']:
        print(f"- {path}")

    print()
    print("正在做最小验证...")
    if cmd_whoami(argparse.Namespace()) != 0:
        return 1
    print()
    return cmd_info(argparse.Namespace())


def cmd_list(args: argparse.Namespace) -> int:
    """列出目录。"""
    path = args.path
    if args.recursive:
        tree_print(path, depth=args.depth, size_mode=args.size)
        return 0

    files = list_files(path)
    print(f"📁 {path}")
    print("=" * 80)
    print(f"{'类型':<4} {'大小':>18} {'修改时间':>20}  名称")
    print("-" * 80)
    for item in files:
        name = item.get("server_filename", "unknown")
        size = int(item.get("size", 0))
        is_dir = int(item.get("isdir", 0)) == 1
        mtime = int(item.get("server_mtime", 0))
        mtime_str = format_time(mtime) if mtime else "-"
        if is_dir:
            print(f"📁   {'-':>18} {mtime_str:>20}  {name}")
        else:
            print(f"📄   {format_size(size):>18} {mtime_str:>20}  {name}")
    print("-" * 80)
    print(f"共 {len(files)} 个文件/目录")
    print("=" * 80)
    return 0


def cmd_tree(args: argparse.Namespace) -> int:
    """显示目录树。"""
    print(f"📁 {args.path}")
    print("=" * 60)
    tree_print(args.path, depth=args.depth, size_mode=args.size)
    return 0


def print_du_summary(summary: dict[str, Any]) -> None:
    print(f"📊 {summary['path']}")
    print("=" * 60)
    print(f"类型：{summary['type']}")
    print(f"文件数：{summary['file_count']}")
    print(f"目录数：{summary['dir_count']}")
    print(f"总大小：{format_size(int(summary['total_size']))}")
    print(f"扫描条目：{summary.get('scanned_count', 0)}")
    print(f"API 页数：{summary.get('page_count', 0)}")
    print(f"耗时：{summary.get('elapsed_seconds', 0):.2f}s")


def cmd_du(args: argparse.Namespace) -> int:
    """递归统计目录大小。"""
    paths = args.paths or ["/"]
    concurrency = max(1, int(args.concurrency))
    summaries: list[dict[str, Any]] = []
    if len(paths) == 1 or concurrency == 1:
        for path in paths:
            summaries.append(summarize_remote_path(path, use_checkpoint=args.resume, resume=args.resume))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_map = {
                executor.submit(summarize_remote_path, path, use_checkpoint=args.resume, resume=args.resume): path
                for path in paths
            }
            for future in as_completed(future_map):
                path = future_map[future]
                try:
                    summaries.append(future.result())
                except Exception as exc:  # noqa: BLE001
                    summaries.append({"path": path, "error": str(exc)})

    for index, summary in enumerate(summaries):
        if index:
            print()
        if "error" in summary:
            print(f"❌ {summary['path']}: {summary['error']}")
        else:
            print_du_summary(summary)
    return 0 if all("error" not in item for item in summaries) else 1


def cmd_stats(args: argparse.Namespace) -> int:
    """统计目录。"""
    client = BaiduNetdiskClient(__file__)
    start_time = time.time()
    file_count = 0
    dir_count = 0
    total_size = 0
    suffixes: dict[str, dict[str, int]] = {}
    largest: list[dict[str, Any]] = []
    newest: list[dict[str, Any]] = []
    try:
        entry = client.get_entry(args.path)
        if entry is None:
            print(f"❌ 路径不存在：{args.path}")
            return 1
        if entry.get("type") == "file":
            items: Iterable[dict[str, Any]] = [entry.get("raw", entry)]
        else:
            items = client.iter_listall(args.path, recursion=True)
        for item in items:
            is_dir = int(item.get("isdir", 0)) == 1 or item.get("type") == "dir"
            if is_dir:
                dir_count += 1
                continue
            file_count += 1
            size = int(item.get("size", 0))
            total_size += size
            name = item.get("server_filename") or item.get("filename") or item.get("name") or item.get("path", "")
            suffix = file_suffix(name)
            bucket = suffixes.setdefault(suffix, {"count": 0, "size": 0})
            bucket["count"] += 1
            bucket["size"] += size
            record = {
                "path": item.get("path", ""),
                "name": name,
                "size": size,
                "mtime": int(item.get("server_mtime", item.get("mtime", 0)) or 0),
            }
            largest.append(record)
            newest.append(record)
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    finally:
        client.close()

    largest.sort(key=lambda item: item["size"], reverse=True)
    newest.sort(key=lambda item: item["mtime"], reverse=True)
    suffix_rows = sorted(suffixes.items(), key=lambda item: item[1]["size"], reverse=True)

    print(f"📊 统计：{normalize_remote_path(args.path)}")
    print("=" * 60)
    print(f"目录数：{dir_count}")
    print(f"文件数：{file_count}")
    print(f"总大小：{format_size(total_size)}")
    print(f"耗时：{time.time() - start_time:.2f}s")
    print()
    print("后缀分布：")
    for suffix, data in suffix_rows[: args.top]:
        print(f"- {suffix:<10} {data['count']:>6} files  {format_size(data['size']):>10}")
    print()
    print("最大文件：")
    for item in largest[: args.top]:
        print(f"- {format_size(item['size']):>10}  {item['path']}")
    print()
    print("最近修改：")
    for item in newest[: args.top]:
        print(f"- {format_time(item['mtime'])}  {format_size(item['size']):>10}  {item['path']}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """使用百度原生搜索接口搜索文件。"""
    client = BaiduNetdiskClient(__file__)
    try:
        payload = client.search(args.keyword, args.path, recursion=args.recursive, page=args.page, num=args.limit)
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    finally:
        client.close()

    items = payload.get("list", [])
    print(f"🔍 搜索 \"{args.keyword}\" in {normalize_remote_path(args.path)}")
    print("=" * 60)
    print(f"结果数：{len(items)} / display_count={payload.get('display_count', '-')}, has_more={payload.get('has_more', '-')}")
    for item in items[: args.limit]:
        is_dir = int(item.get("isdir", 0)) == 1
        icon = "📁" if is_dir else "📄"
        size = "-" if is_dir else format_size(int(item.get("size", 0)))
        print(f"{icon} {item.get('path', '')} ({size})")
    return 0


def get_file_entry(path: str) -> dict[str, Any] | None:
    client = BaiduNetdiskClient(__file__)
    try:
        return client.get_entry(path)
    finally:
        client.close()


def cmd_metas(args: argparse.Namespace) -> int:
    """显示文件/目录元信息。"""
    client = BaiduNetdiskClient(__file__)
    try:
        fsids = []
        by_path: dict[int, str] = {}
        for path in args.paths:
            entry = client.get_entry(path)
            if entry is None:
                print(f"❌ 路径不存在：{path}")
                continue
            raw = entry.get("raw") or entry
            fs_id = raw.get("fs_id")
            if fs_id is None:
                print(f"❌ 无 fs_id：{path}")
                continue
            fs_id_int = int(fs_id)
            fsids.append(fs_id_int)
            by_path[fs_id_int] = path
        if not fsids:
            return 1
        metas = client.filemetas(fsids, dlink=args.dlink, extra=True)
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    finally:
        client.close()

    print("🧾 文件元信息")
    print("=" * 60)
    for item in metas:
        is_dir = str(item.get("isdir", 0)) == "1"
        name = item.get("server_filename") or item.get("filename") or Path(item.get("path", "")).name
        size_note = "directory size is not recursive" if is_dir else format_size(int(item.get("size", 0)))
        print(f"- {name}")
        print(f"  path: {item.get('path', by_path.get(int(item.get('fs_id', 0)), '-'))}")
        print(f"  fs_id: {item.get('fs_id', '-')}")
        print(f"  type: {'dir' if is_dir else 'file'}")
        print(f"  size: {size_note}")
        if item.get("md5"):
            print(f"  md5: {item.get('md5')}")
        if args.dlink and item.get("dlink"):
            print("  dlink: <redacted; use download command>")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """删除文件或目录。"""
    path = args.path
    if not args.yes:
        print(f"⚠️  警告：即将删除 {path}")
        print("此操作不可恢复！")
        response = input("确认删除？输入 'yes' 确认：")
        if response.lower() != "yes":
            print("❌ 已取消")
            return 1
    client = BaiduNetdiskClient(__file__)
    try:
        result = client.delete([path])
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ 删除失败：{exc}")
        return 1
    finally:
        client.close()
    print(f"✅ 删除成功：{path}")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def calc_file_md5(filepath: str | Path) -> str:
    """计算文件 MD5。"""
    md5 = hashlib.md5()
    with open(filepath, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def cmd_download(args: argparse.Namespace) -> int:
    """下载文件。"""
    path = args.path
    output_path = args.output_path
    client = BaiduNetdiskClient(__file__)
    try:
        entry = client.get_entry(path)
        if entry is None:
            print(f"❌ 文件不存在：{path}")
            return 1
        if entry.get("type") == "dir":
            print(f"❌ 不能下载目录，请使用 batch-download: {path}")
            return 1
        raw = entry.get("raw") or entry
        filename = raw.get("server_filename") or raw.get("name") or Path(path).name
        if output_path is None:
            local_path = Path.cwd() / filename
        else:
            local_path = Path(output_path).expanduser()
            if local_path.is_dir():
                local_path = local_path / filename
        print(f"📥 下载：{filename} ({format_size(int(entry.get('size', 0)))})")
        client.download_file(path, local_path, resume=not args.no_resume)
        print(f"✅ 下载完成：{local_path}")
        return 0
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except (RuntimeError, OSError) as exc:
        print(f"❌ 下载失败：{exc}")
        return 1
    finally:
        client.close()


def cmd_upload(args: argparse.Namespace) -> int:
    """上传文件。"""
    local_path = Path(args.local_path).expanduser()
    if not local_path.exists():
        print(f"❌ 本地文件不存在：{local_path}")
        return 1
    if not local_path.is_file():
        print(f"❌ 只能上传文件，不能是目录：{local_path}")
        return 1
    remote_path = args.remote_path
    if remote_path is None:
        remote_path = "/" + local_path.name
    elif remote_path.endswith("/"):
        remote_path = remote_path + local_path.name
    print(f"📤 上传：{local_path.name}")
    print(f"   大小：{format_size(local_path.stat().st_size)}")
    print(f"   目标：{remote_path}")
    client = BaiduNetdiskClient(__file__)
    try:
        result = client.upload_file(local_path, remote_path)
        print(f"✅ 上传成功：{remote_path}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ 上传失败：{exc}")
        return 1
    finally:
        client.close()


def cmd_batch_download(args: argparse.Namespace) -> int:
    """批量下载目录。"""
    remote_path = normalize_remote_path(args.remote_path)
    local_dir = Path(args.local_dir or Path.cwd() / Path(remote_path.rstrip("/")).name).expanduser()
    local_dir.mkdir(parents=True, exist_ok=True)
    client = BaiduNetdiskClient(__file__)
    try:
        files = [item for item in client.iter_listall(remote_path, recursion=True) if int(item.get("isdir", 0)) == 0]
        print(f"✅ 找到 {len(files)} 个文件，总大小：{format_size(sum(int(f.get('size', 0)) for f in files))}")
        downloaded = failed = skipped = 0
        for index, item in enumerate(files, start=1):
            rel_path = remote_relative_path(remote_path, item["path"])
            local_path = local_dir / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            if local_path.exists() and local_path.stat().st_size >= int(item.get("size", 0)):
                print(f"[{index}/{len(files)}] ⏭️  跳过：{rel_path}")
                skipped += 1
                continue
            print(f"[{index}/{len(files)}] 📥 下载：{rel_path} ({format_size(int(item.get('size', 0)))})")
            try:
                client.download_file(item["path"], local_path, resume=True)
                downloaded += 1
            except Exception as exc:  # noqa: BLE001
                print(f"      ❌ 失败：{exc}")
                failed += 1
        print("=" * 60)
        print("批量下载完成！")
        print(f"  成功：{downloaded} 个")
        print(f"  跳过：{skipped} 个")
        print(f"  失败：{failed} 个")
        print(f"  保存位置：{local_dir}")
        return 0 if failed == 0 else 1
    except requests.exceptions.RequestException as exc:
        print(f"❌ 网络错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    finally:
        client.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="增强版百度网盘命令行工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("info", help="显示账户容量信息").set_defaults(func=cmd_info)
    subparsers.add_parser("whoami", help="显示当前授权用户").set_defaults(func=cmd_whoami)
    subparsers.add_parser("doctor", help="检查环境、token 与 skill 安装状态").set_defaults(func=cmd_doctor)

    auth_parser = subparsers.add_parser("auth", help="打印授权链接或用授权码换 token")
    auth_parser.add_argument("--code", help="浏览器授权后返回的 Authorization Code")
    auth_parser.set_defaults(func=cmd_auth)

    list_parser = subparsers.add_parser("list", help="列出目录")
    list_parser.add_argument("path", nargs="?", default="/")
    list_parser.add_argument("-R", "--recursive", action="store_true")
    list_parser.add_argument("-d", "--depth", type=int, default=10)
    list_parser.add_argument("--size", choices=["none", "shallow", "recursive"], default="none")
    list_parser.set_defaults(func=cmd_list)

    tree_parser = subparsers.add_parser("tree", help="显示目录树")
    tree_parser.add_argument("path", nargs="?", default="/")
    tree_parser.add_argument("-d", "--depth", type=int, default=2)
    tree_parser.add_argument("--size", choices=["none", "shallow", "recursive"], default="none")
    tree_parser.set_defaults(func=cmd_tree)

    du_parser = subparsers.add_parser("du", help="递归统计目录大小")
    du_parser.add_argument("paths", nargs="+", help="一个或多个网盘路径")
    du_parser.add_argument("--concurrency", type=int, default=1, help="多路径统计并发数，单路径分页不并行")
    du_parser.add_argument("--resume", action="store_true", help="启用 checkpoint 记录/恢复")
    du_parser.set_defaults(func=cmd_du)

    stats_parser = subparsers.add_parser("stats", help="递归统计目录并输出聚合信息")
    stats_parser.add_argument("path", nargs="?", default="/")
    stats_parser.add_argument("--top", type=int, default=10)
    stats_parser.set_defaults(func=cmd_stats)

    search_parser = subparsers.add_parser("search", help="使用百度搜索接口搜索")
    search_parser.add_argument("keyword")
    search_parser.add_argument("path", nargs="?", default="/")
    search_parser.add_argument("--recursive", action="store_true", default=True)
    search_parser.add_argument("--page", type=int, default=1)
    search_parser.add_argument("--limit", type=int, default=50)
    search_parser.set_defaults(func=cmd_search)

    metas_parser = subparsers.add_parser("metas", help="查看文件/目录元信息")
    metas_parser.add_argument("paths", nargs="+")
    metas_parser.add_argument("--dlink", action="store_true", help="请求下载链接但不打印明文")
    metas_parser.set_defaults(func=cmd_metas)

    delete_parser = subparsers.add_parser("delete", help="删除文件或目录")
    delete_parser.add_argument("path")
    delete_parser.add_argument("--yes", action="store_true")
    delete_parser.set_defaults(func=cmd_delete)

    download_parser = subparsers.add_parser("download", help="下载文件")
    download_parser.add_argument("path")
    download_parser.add_argument("output_path", nargs="?")
    download_parser.add_argument("--no-resume", action="store_true")
    download_parser.set_defaults(func=cmd_download)

    upload_parser = subparsers.add_parser("upload", help="上传文件")
    upload_parser.add_argument("local_path")
    upload_parser.add_argument("remote_path", nargs="?")
    upload_parser.set_defaults(func=cmd_upload)

    batch_parser = subparsers.add_parser("batch-download", help="批量下载目录")
    batch_parser.add_argument("remote_path")
    batch_parser.add_argument("local_dir", nargs="?")
    batch_parser.set_defaults(func=cmd_batch_download)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
