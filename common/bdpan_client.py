#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘统一客户端：读写都走同一套 XPAN/PCS 接口。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from .bdpan_runtime import configure_requests_session, configure_runtime, load_access_token, request_timeout


HEADERS = {"User-Agent": "netdisk;P2SP;3.0.20.80"}
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://pan.baidu.com",
}
QUOTA_URL = "https://pan.baidu.com/api/quota"
XPN_FILE_URL = "https://pan.baidu.com/rest/2.0/xpan/file"
PCS_FILE_URL = "https://pcs.baidu.com/rest/2.0/pcs/file"
PCS_SUPERFILE2_URL = "https://c.pcs.baidu.com/rest/2.0/pcs/superfile2"
XPAN_MULTIMEDIA_URL = "https://pan.baidu.com/rest/2.0/xpan/multimedia"
XPAN_NAS_URL = "https://pan.baidu.com/rest/2.0/xpan/nas"


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
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def format_time(timestamp: int) -> str:
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


class BaiduNetdiskClient:
    def __init__(self, script_file: str):
        configure_runtime()
        self.script_file = script_file
        self.token = load_access_token(script_file)
        self.session = requests.Session()
        configure_requests_session(self.session)

    def close(self) -> None:
        self.session.close()

    def request_json(self, url: str, *, params: dict[str, Any] | None = None, data: dict[str, Any] | None = None, method: str = "GET", headers: dict[str, str] | None = None, timeout: int = 30, _retry_refreshed: bool = True) -> dict[str, Any]:
        request_headers = headers or HEADERS
        request_params = dict(params or {})
        request_params["access_token"] = self.token
        if method == "GET":
            response = self.session.get(url, params=request_params, headers=request_headers, timeout=request_timeout(timeout), stream=True)
        else:
            response = self.session.post(url, params=request_params, data=data, headers=request_headers, timeout=request_timeout(timeout), stream=True)

        # ── Token 过期自动刷新并重试一次 ──
        if _retry_refreshed and response.status_code in (400, 401):
            try:
                from .bdpan_refresh import refresh_and_save
                new_data = refresh_and_save(self.script_file)
                self.token = new_data["access_token"]
                return self.request_json(url, params=params, data=data,
                                         method=method, headers=headers,
                                         timeout=timeout, _retry_refreshed=False)
            except Exception:
                pass  # 刷新失败则让原始错误透出

        response.raise_for_status()
        return response.json()

    def list_dir(self, remote_path: str) -> list[dict[str, Any]]:
        remote_path = normalize_remote_path(remote_path)
        start = 0
        limit = 1000
        items: list[dict[str, Any]] = []
        while True:
            payload = self.request_json(
                XPN_FILE_URL,
                params={"method": "list", "dir": remote_path, "web": "1", "start": start, "limit": limit},
            )
            errno = payload.get("errno", 0)
            if errno != 0:
                raise RuntimeError(f"list 失败: {payload}")
            batch = payload.get("list", [])
            items.extend(batch)
            if len(batch) < limit:
                break
            start += len(batch)
        return items

    def get_quota(self) -> dict[str, Any]:
        payload = self.request_json(QUOTA_URL, params={}, method="GET", headers=HEADERS, timeout=30)
        if payload.get("errno", 0) not in {0, None}:
            raise RuntimeError(f"quota 失败: {payload}")
        return payload

    def get_user_info(self) -> dict[str, Any]:
        payload = self.request_json(XPAN_NAS_URL, params={"method": "uinfo"}, method="GET", headers=HEADERS, timeout=30)
        if payload.get("errno", 0) not in {0, None}:
            raise RuntimeError(f"uinfo 失败: {payload}")
        return payload

    def iter_listall(
        self,
        remote_path: str,
        *,
        recursion: bool = True,
        limit: int = 1000,
        order: str | None = None,
        desc: bool | None = None,
        web: bool = True,
        start: int = 0,
        page_counter: dict[str, int] | None = None,
    ):
        remote_path = normalize_remote_path(remote_path)
        cursor = start
        while True:
            params: dict[str, Any] = {
                "method": "listall",
                "path": remote_path,
                "recursion": "1" if recursion else "0",
                "start": cursor,
                "limit": limit,
            }
            if web:
                params["web"] = "1"
            if order:
                params["order"] = order
            if desc is not None:
                params["desc"] = "1" if desc else "0"
            payload = self.request_json(XPAN_MULTIMEDIA_URL, params=params, method="GET", headers=HEADERS, timeout=60)
            errno = payload.get("errno", 0)
            if errno != 0:
                raise RuntimeError(f"listall 失败: {payload}")
            if page_counter is not None:
                page_counter["pages"] = int(page_counter.get("pages", 0)) + 1
            for entry in payload.get("list", []):
                yield entry
            if not payload.get("has_more"):
                break
            next_cursor = payload.get("cursor")
            if next_cursor is None:
                break
            cursor = int(next_cursor)

    def search(self, keyword: str, remote_path: str = "/", *, recursion: bool = True, page: int = 1, num: int = 50) -> dict[str, Any]:
        payload = self.request_json(
            XPN_FILE_URL,
            params={
                "method": "search",
                "key": keyword,
                "dir": normalize_remote_path(remote_path),
                "recursion": "1" if recursion else "0",
                "page": page,
                "num": num,
            },
            method="GET",
            headers=HEADERS,
            timeout=30,
        )
        if payload.get("errno", 0) != 0:
            raise RuntimeError(f"search 失败: {payload}")
        return payload

    def filemetas(self, fsids: list[int], *, dlink: bool = False, thumb: bool = False, extra: bool = True) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for index in range(0, len(fsids), 100):
            batch = fsids[index : index + 100]
            payload = self.request_json(
                XPAN_MULTIMEDIA_URL,
                params={
                    "method": "filemetas",
                    "fsids": json.dumps(batch, ensure_ascii=False),
                    "dlink": "1" if dlink else "0",
                    "thumb": "1" if thumb else "0",
                    "extra": "1" if extra else "0",
                },
                method="GET",
                headers=HEADERS,
                timeout=30,
            )
            if payload.get("errno", 0) != 0:
                raise RuntimeError(f"filemetas 失败: {payload}")
            results.extend(payload.get("list", []))
        return results

    def summarize_path(self, remote_path: str, *, use_checkpoint: bool = False, resume: bool = False) -> dict[str, Any]:
        import time
        from .bdpan_scan_state import ScanCheckpoint

        remote_path = normalize_remote_path(remote_path)
        started = time.time()
        entry = self.get_entry(remote_path)
        if entry is None:
            raise RuntimeError(f"路径不存在: {remote_path}")
        if entry.get("type") == "file":
            return {
                "path": remote_path,
                "type": "file",
                "file_count": 1,
                "dir_count": 0,
                "total_size": int(entry.get("size", 0)),
                "scanned_count": 1,
                "page_count": 0,
                "elapsed_seconds": time.time() - started,
            }

        checkpoint = ScanCheckpoint(self.script_file, remote_path) if use_checkpoint else None
        summary = checkpoint.load() if checkpoint and resume else None
        total_size = int(summary.get("total_size", 0)) if summary else 0
        file_count = int(summary.get("file_count", 0)) if summary else 0
        dir_count = int(summary.get("dir_count", 0)) if summary else 0
        scanned_count = int(summary.get("scanned_count", 0)) if summary else 0
        page_counter = {"pages": int(summary.get("page_count", 0)) if summary else 0}
        # Cursor resume is intentionally conservative: we persist progress for observability,
        # but restart from the beginning because Baidu cursors may be short-lived and the
        # directory may have changed between runs.
        total_size = file_count = dir_count = scanned_count = 0
        page_counter = {"pages": 0}
        for item in self.iter_listall(remote_path, recursion=True, page_counter=page_counter):
            scanned_count += 1
            if int(item.get("isdir", 0)) == 1:
                dir_count += 1
            else:
                file_count += 1
                total_size += int(item.get("size", 0))
            if checkpoint and scanned_count % 1000 == 0:
                checkpoint.save({
                    "path": remote_path,
                    "total_size": total_size,
                    "file_count": file_count,
                    "dir_count": dir_count,
                    "scanned_count": scanned_count,
                    "page_count": page_counter["pages"],
                    "updated_at": int(time.time()),
                })
        result = {
            "path": remote_path,
            "type": "dir",
            "file_count": file_count,
            "dir_count": dir_count,
            "total_size": total_size,
            "scanned_count": scanned_count,
            "page_count": page_counter["pages"],
            "elapsed_seconds": time.time() - started,
        }
        if checkpoint:
            checkpoint.save(result)
        return result

    def get_entry(self, remote_path: str) -> dict[str, Any] | None:
        remote_path = normalize_remote_path(remote_path)
        if remote_path == "/":
            return {"path": "/", "name": "/", "type": "dir", "size": 0, "mtime": 0}
        parent = normalize_remote_path(str(Path(remote_path).parent))
        target_name = Path(remote_path).name
        for entry in self.list_dir(parent):
            name = entry.get("server_filename", entry.get("path", "").rsplit("/", 1)[-1])
            if name == target_name and normalize_remote_path(entry["path"]) == remote_path:
                return {
                    "path": remote_path,
                    "name": name,
                    "type": "dir" if entry.get("isdir", 0) == 1 else "file",
                    "size": int(entry.get("size", 0)),
                    "mtime": int(entry.get("server_mtime", 0)),
                    "raw": entry,
                }
        return None

    def ensure_dir(self, remote_dir: str) -> bool:
        remote_dir = normalize_remote_path(remote_dir)
        if remote_dir in {"", "/"}:
            return False
        if self.get_entry(remote_dir) is not None:
            return False
        payload = self.request_json(
            XPN_FILE_URL,
            params={"method": "create"},
            data={"path": remote_dir, "isdir": "1"},
            method="POST",
        )
        errno = payload.get("errno", 0)
        if errno != 0:
            raise RuntimeError(f"mkdir 失败: {payload}")
        return True

    def move(self, source: str, target: str) -> dict[str, Any]:
        source = normalize_remote_path(source)
        target = normalize_remote_path(target)
        target_parent = normalize_remote_path(str(Path(target).parent))
        target_name = Path(target).name
        self.ensure_dir(target_parent)
        payload = self.request_json(
            XPN_FILE_URL,
            params={"method": "filemanager", "opera": "move"},
            data={"async": "0", "filelist": json.dumps([{"path": source, "dest": target_parent, "newname": target_name, "ondup": "fail"}], ensure_ascii=False)},
            method="POST",
        )
        if payload.get("errno", 0) != 0:
            raise RuntimeError(f"move 失败: {payload}")
        return payload

    def copy(self, source: str, target: str) -> dict[str, Any]:
        source = normalize_remote_path(source)
        target = normalize_remote_path(target)
        target_parent = normalize_remote_path(str(Path(target).parent))
        target_name = Path(target).name
        self.ensure_dir(target_parent)
        payload = self.request_json(
            XPN_FILE_URL,
            params={"method": "filemanager", "opera": "copy"},
            data={"async": "0", "filelist": json.dumps([{"path": source, "dest": target_parent, "newname": target_name, "ondup": "fail"}], ensure_ascii=False)},
            method="POST",
        )
        if payload.get("errno", 0) != 0:
            raise RuntimeError(f"copy 失败: {payload}")
        return payload

    def delete(self, paths: list[str]) -> dict[str, Any]:
        payload = self.request_json(
            XPN_FILE_URL,
            params={"method": "filemanager", "opera": "delete"},
            data={"async": "0", "filelist": json.dumps([normalize_remote_path(p) for p in paths], ensure_ascii=False)},
            method="POST",
        )
        if payload.get("errno", 0) != 0:
            raise RuntimeError(f"delete 失败: {payload}")
        return payload

    def upload_file(self, local_path: Path, remote_path: str, chunk_size: int = 4 * 1024 * 1024) -> dict[str, Any]:
        if not local_path.is_file():
            raise ValueError(f"只能上传文件: {local_path}")
        remote_path = normalize_remote_path(remote_path)
        remote_parent = normalize_remote_path(str(Path(remote_path).parent))
        if remote_parent not in {"", "/"}:
            self.ensure_dir(remote_parent)
        file_size = local_path.stat().st_size
        block_md5s = []
        with local_path.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                block_md5s.append(hashlib.md5(chunk).hexdigest())

        precreate = self.request_json(
            XPN_FILE_URL,
            params={"method": "precreate", "clienttype": "0"},
            data={
                "path": remote_path,
                "size": str(file_size),
                "isdir": "0",
                "rtype": "3",
                "block_list": json.dumps(block_md5s, ensure_ascii=False),
                "autoinit": "1",
            },
            method="POST",
            headers=HEADERS,
            timeout=30,
        )
        if precreate.get("errno", 0) != 0:
            raise RuntimeError(f"precreate 失败: {precreate}")
        if precreate.get("return_type", 0) == 0:
            return precreate

        uploadid = precreate.get("uploadid")
        if not uploadid:
            raise RuntimeError(f"precreate 未返回 uploadid: {precreate}")

        upload_url = PCS_SUPERFILE2_URL
        with local_path.open("rb") as f:
            partseq = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                upload_params = {
                    "method": "upload",
                    "type": "tmpfile",
                    "path": remote_path,
                    "uploadid": uploadid,
                    "partseq": str(partseq),
                }
                resp = self.session.post(
                    upload_url,
                    params={**upload_params, "access_token": self.token},
                    files={"file": (local_path.name, chunk)},
                    timeout=request_timeout(120),
                )
                resp.raise_for_status()
                result = resp.json()
                if result.get("errno", 0) != 0 and "md5" not in result:
                    raise RuntimeError(f"分片上传失败: {result}")
                partseq += 1

        create = self.request_json(
            XPN_FILE_URL,
            params={"method": "create"},
            data={
                "path": remote_path,
                "size": str(file_size),
                "isdir": "0",
                "rtype": "3",
                "uploadid": uploadid,
                "block_list": json.dumps(block_md5s, ensure_ascii=False),
            },
            method="POST",
            headers=HEADERS,
            timeout=30,
        )
        if create.get("errno", 0) != 0:
            raise RuntimeError(f"create 失败: {create}")
        return create

    def download_file(self, remote_path: str, local_path: Path, *, resume: bool = True, chunk_size: int = 8192) -> None:
        remote_path = normalize_remote_path(remote_path)
        entry = self.get_entry(remote_path)
        if entry is None:
            raise FileNotFoundError(f"远端文件不存在: {remote_path}")
        if entry.get("type") == "dir":
            raise IsADirectoryError(f"不能下载目录: {remote_path}")
        local_path = local_path.expanduser().resolve()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        file_size = int(entry.get("size", 0))
        start_pos = 0
        if resume and local_path.exists():
            start_pos = local_path.stat().st_size
            if start_pos >= file_size:
                return
        headers = dict(DOWNLOAD_HEADERS)
        if start_pos > 0:
            headers["Range"] = f"bytes={start_pos}-"
        with self.session.get(PCS_FILE_URL, params={"method": "download", "access_token": self.token, "path": remote_path}, headers=headers, stream=True, timeout=request_timeout(60)) as resp:
            resp.raise_for_status()
            mode = "ab" if start_pos > 0 else "wb"
            with local_path.open(mode) as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)

    def download_file(self, remote_path: str, local_path: Path, *, resume: bool = True, chunk_size: int = 8192) -> None:
        remote_path = normalize_remote_path(remote_path)
        entry = self.get_entry(remote_path)
        if entry is None:
            raise FileNotFoundError(f"远端文件不存在: {remote_path}")
        if entry.get("type") == "dir":
            raise IsADirectoryError(f"不能下载目录: {remote_path}")

        local_path = local_path.expanduser().resolve()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        file_size = int(entry.get("size", 0))

        start_pos = 0
        if resume and local_path.exists():
            start_pos = local_path.stat().st_size
            if start_pos >= file_size:
                return

        headers = dict(DOWNLOAD_HEADERS)
        if start_pos > 0:
            headers["Range"] = f"bytes={start_pos}-"

        with self.session.get(PCS_FILE_URL, params={"method": "download", "access_token": self.token, "path": remote_path}, headers=headers, stream=True, timeout=request_timeout(60)) as resp:
            resp.raise_for_status()
            mode = "ab" if start_pos > 0 else "wb"
            with local_path.open(mode) as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
