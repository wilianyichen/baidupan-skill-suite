#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版百度网盘命令行工具
支持：tree, search, batch-download, stats, list, upload, delete, info
"""

import os
import sys
import json
import requests
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_runtime import configure_runtime, describe_token_search_order, load_access_token

# 配置
BASE_URL = "https://pan.baidu.com/rest/2.0/xpan"
HEADERS = {
    "User-Agent": "netdisk;P2SP;3.0.20.80"
}

# 下载专用的 headers
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://pan.baidu.com"
}

configure_runtime()

def get_token():
    """获取访问令牌"""
    try:
        return load_access_token(__file__)
    except (FileNotFoundError, KeyError) as exc:
        print(f"❌ {exc}")
        print("   已检查：")
        for candidate in describe_token_search_order(__file__):
            print(f"   - {candidate}")
        print("   可通过环境变量 BYPY_TOKEN_FILE 指定 token 文件")
        sys.exit(1)

def request_api(api_path, params=None, method='GET'):
    """调用百度 API"""
    token = get_token()
    url = f"{BASE_URL}{api_path}"
    
    if params is None:
        params = {}
    params['access_token'] = token
    
    # 创建 session 并禁用代理
    session = requests.Session()
    session.trust_env = False  # 禁用环境变量中的代理设置
    
    try:
        if method == 'GET':
            resp = session.get(url, params=params, headers=HEADERS, timeout=30, stream=True)
        else:
            resp = session.post(url, data=params, headers=HEADERS, timeout=30, stream=True)
        
        resp.raise_for_status()
        
        # 手动处理 gzip 解压
        import gzip
        from io import BytesIO
        
        if resp.headers.get('content-encoding') == 'gzip':
            try:
                decompressed = gzip.GzipFile(fileobj=BytesIO(resp.content)).read()
                return json.loads(decompressed)
            except Exception as e:
                # 如果 gzip 失败，尝试直接解析
                return resp.json()
        else:
            return resp.json()
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络错误：{e}")
        sys.exit(1)
    finally:
        session.close()

def get_quota():
    """获取网盘容量信息"""
    # 使用正确的 API 端点
    token = get_token()
    url = "https://pan.baidu.com/api/quota"
    
    params = {'access_token': token}
    
    session = requests.Session()
    session.trust_env = False
    
    try:
        resp = session.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络错误：{e}")
        sys.exit(1)
    finally:
        session.close()

def list_files(path='/'):
    """列出目录文件"""
    token = get_token()
    url = "https://pan.baidu.com/rest/2.0/xpan/file"
    page_size = 1000
    start = 0
    collected = []

    session = requests.Session()
    session.trust_env = False

    try:
        while True:
            params = {
                'method': 'list',
                'access_token': token,
                'dir': path,  # 使用 dir 而不是 path
                'web': '1',
                'limit': page_size,
                'start': start,
            }

            resp = session.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            result = resp.json()

            if 'errno' in result and result['errno'] != 0:
                if result['errno'] == -9:
                    print(f"❌ 目录不存在：{path}")
                else:
                    print(f"❌ API 错误：{result}")
                sys.exit(1)

            current_batch = result.get('list', [])
            collected.extend(current_batch)

            if len(current_batch) < page_size:
                break
            start += len(current_batch)

        return collected
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络错误：{e}")
        sys.exit(1)
    finally:
        session.close()

def build_tree_node(path='/', depth=2, current_depth=0):
    """构建带递归目录大小的树节点。

    depth 控制展示层级，但目录大小会继续递归计算到叶子节点。
    """
    files = list_files(path)
    children = []
    total_size = 0
    max_mtime = 0

    for entry in files:
        name = entry.get('server_filename', 'unknown')
        item_path = entry.get('path', '')
        if entry.get('isdir', 0) == 1:
            child = build_tree_node(item_path, depth=depth, current_depth=current_depth + 1)
            child['name'] = name
            child['path'] = item_path
            child['mtime'] = max(int(entry.get('server_mtime', 0)), child.get('mtime', 0))
        else:
            child = {
                'name': name,
                'path': item_path,
                'type': 'file',
                'size': int(entry.get('size', 0)),
                'mtime': int(entry.get('server_mtime', 0)),
                'children': [],
            }

        total_size += int(child.get('size', 0))
        max_mtime = max(max_mtime, int(child.get('mtime', 0)))

        if current_depth < depth:
            children.append(child)

    return {
        'name': '/' if path == '/' else Path(path).name,
        'path': path,
        'type': 'dir',
        'size': total_size,
        'mtime': max_mtime,
        'children': children,
    }


def render_tree_node(node, prefix='', current_depth=0):
    """渲染树节点。"""
    for index, child in enumerate(node.get('children', [])):
        is_last = index == len(node['children']) - 1
        connector = "" if current_depth == 0 else ("└── " if is_last else "├── ")
        if child['type'] == 'dir':
            print(f"{prefix}{connector}📁 {child['name']} ({format_size(int(child['size']))})")
            new_prefix = prefix + ("    " if is_last else "│   ")
            render_tree_node(child, new_prefix, current_depth + 1)
        else:
            print(f"{prefix}{connector}📄 {child['name']} ({format_size(int(child['size']))}, {format_time(int(child['mtime']))})")


def tree_print(path='/', depth=2):
    """打印带递归目录大小的目录树。"""
    tree = build_tree_node(path, depth=depth, current_depth=0)
    render_tree_node(tree, current_depth=0)

def format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def format_time(timestamp):
    """格式化时间戳"""
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')

def cmd_info():
    """显示账户信息"""
    result = get_quota()
    total = format_size(result['total'])
    used = format_size(result['used'])
    free = format_size(result['total'] - result['used'])
    
    print("📊 百度网盘账户信息")
    print("=" * 50)
    print(f"总容量：{total}")
    print(f"已使用：{used}")
    print(f"剩余：{free}")
    if result['total'] > 0:
        print(f"使用率：{result['used']/result['total']*100:.1f}%")

def cmd_list(path, recursive=False):
    """列出目录"""
    if recursive:
        tree_print(path, depth=10)
    else:
        files = list_files(path)
        print(f"📁 {path}")
        print("=" * 80)
        
        # 表头
        print(f"{'类型':<4} {'大小':>12} {'修改时间':>20}  名称")
        print("-" * 80)
        
        for f in files:
            name = f.get('server_filename', 'unknown')
            fpath = f.get('path', '')
            size = int(f.get('size', 0))
            is_dir = f.get('isdir', 0) == 1
            
            # 获取修改时间
            mtime = f.get('server_mtime', 0)
            if mtime:
                mtime_str = format_time(mtime)
            else:
                mtime_str = '-'
            
            if is_dir:
                print(f"📁   {'-':>12} {mtime_str:>20}  {name}")
            else:
                size_str = format_size(size)
                print(f"📄   {size_str:>12} {mtime_str:>20}  {name}")
        
        print("-" * 80)
        print(f"共 {len(files)} 个文件/目录")
        print("=" * 80)

def cmd_tree(path, depth):
    """显示目录树"""
    print(f"📁 {path}")
    print("=" * 60)
    tree_print(path, depth=depth)

def cmd_search(keyword, path='/'):
    """搜索文件"""
    print(f"🔍 搜索 \"{keyword}\" in {path}")
    print("=" * 60)
    
    def search_recursive(current_path):
        files = list_files(current_path)
        for f in files:
            if f['isdir'] == 1:
                search_recursive(f['path'])
            else:
                if keyword.lower() in f['server_filename'].lower():
                    size_str = format_size(int(f['size']))
                    print(f"📄 {f['path']} ({size_str})")
    
    search_recursive(path)

def cmd_stats(path='/'):
    """统计目录"""
    print(f"📊 统计：{path}")
    print("=" * 60)
    
    total_size = 0
    file_count = 0
    dir_count = 0
    
    def stats_recursive(current_path):
        nonlocal total_size, file_count, dir_count
        files = list_files(current_path)
        for f in files:
            if f['isdir'] == 1:
                dir_count += 1
                stats_recursive(f['path'])
            else:
                file_count += 1
                total_size += int(f['size'])
    
    stats_recursive(path)
    
    print(f"目录数：{dir_count}")
    print(f"文件数：{file_count}")
    print(f"总大小：{format_size(total_size)}")

def cmd_delete(path, confirm=False):
    """删除文件或目录"""
    if not confirm:
        print(f"⚠️  警告：即将删除 {path}")
        print("此操作不可恢复！")
        response = input("确认删除？输入 'yes' 确认：")
        if response.lower() != 'yes':
            print("❌ 已取消")
            return
    
    token = get_token()
    url = "https://pan.baidu.com/rest/2.0/xpan/file"
    
    # 获取文件的 fs_id
    parent_path = '/'.join(path.split('/')[:-1]) or '/'
    filename = path.split('/')[-1]
    
    files = list_files(parent_path)
    target = None
    for f in files:
        if f['server_filename'] == filename and f['path'] == path:
            target = f
            break
    
    if not target:
        print(f"❌ 文件不存在：{path}")
        sys.exit(1)
    
    fs_id = target['fs_id']
    
    params = {
        'method': 'filemanager',
        'access_token': token,
        'opera': 'delete',
        'filelist': json.dumps([fs_id])
    }
    
    session = requests.Session()
    session.trust_env = False
    
    try:
        resp = session.post(url, data=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        
        if result.get('errno') == 0:
            print(f"✅ 删除成功：{path}")
        else:
            print(f"❌ 删除失败：{result}")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络错误：{e}")
        sys.exit(1)
    finally:
        session.close()

def get_file_fs_id(path):
    """获取文件的 fs_id"""
    parent_path = '/'.join(path.split('/')[:-1]) or '/'
    filename = path.split('/')[-1]
    
    files = list_files(parent_path)
    for f in files:
        if f['server_filename'] == filename and f['path'] == path:
            return f
    return None

def cmd_download(path, output_path=None):
    """下载文件"""
    token = get_token()
    
    # 获取文件信息
    file_info = get_file_fs_id(path)
    if not file_info:
        print(f"❌ 文件不存在：{path}")
        sys.exit(1)
    
    if file_info['isdir'] == 1:
        print(f"❌ 不能下载目录，请使用 batch-download: {path}")
        sys.exit(1)
    
    fs_id = file_info['fs_id']
    filename = file_info['server_filename']
    file_size = int(file_info['size'])
    file_path = file_info['path']
    
    # 确定保存路径
    if output_path is None:
        output_path = os.path.join(os.getcwd(), filename)
    elif os.path.isdir(output_path):
        output_path = os.path.join(output_path, filename)
    
    # 检查是否已存在（断点续传）
    start_pos = 0
    if os.path.exists(output_path):
        start_pos = os.path.getsize(output_path)
        if start_pos >= file_size:
            print(f"✅ 文件已完整下载：{output_path}")
            return
        print(f"📥 续传：已下载 {format_size(start_pos)} / {format_size(file_size)}")
    
    # 使用 pcs 域名下载
    url = "https://d.pcs.baidu.com/rest/2.0/pcs/file"
    params = {
        'method': 'download',
        'access_token': token,
        'path': file_path
    }
    
    session = requests.Session()
    session.trust_env = False
    
    try:
        headers = dict(DOWNLOAD_HEADERS)
        if start_pos > 0:
            headers['Range'] = f'bytes={start_pos}-'
        
        print(f"📥 下载：{filename} ({format_size(file_size)})")
        
        with session.get(url, params=params, headers=headers, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            
            mode = 'ab' if start_pos > 0 else 'wb'
            downloaded = start_pos
            
            with open(output_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 显示进度
                        if downloaded % (1024 * 1024) < 8192:  # 每 MB 显示一次
                            percent = downloaded / file_size * 100
                            print(f"  进度：{format_size(downloaded)} / {format_size(file_size)} ({percent:.1f}%)", end='\r')
            
            print(f"\n✅ 下载完成：{output_path}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络错误：{e}")
        sys.exit(1)
    finally:
        session.close()

def calc_file_md5(filepath):
    """计算文件 MD5"""
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    return md5.hexdigest()

def cmd_upload(local_path, remote_path=None):
    """上传文件"""
    if not os.path.exists(local_path):
        print(f"❌ 本地文件不存在：{local_path}")
        sys.exit(1)
    
    if not os.path.isfile(local_path):
        print(f"❌ 只能上传文件，不能是目录：{local_path}")
        sys.exit(1)
    
    # 确定远程路径
    if remote_path is None:
        remote_path = '/' + os.path.basename(local_path)
    elif remote_path.endswith('/'):
        remote_path = remote_path + os.path.basename(local_path)
    
    file_size = os.path.getsize(local_path)
    file_md5 = calc_file_md5(local_path)
    
    print(f"📤 上传：{os.path.basename(local_path)}")
    print(f"   大小：{format_size(file_size)}")
    print(f"   MD5:  {file_md5}")
    print(f"   目标：{remote_path}")
    
    token = get_token()
    url = "https://pan.baidu.com/rest/2.0/xpan/file"
    
    # 小文件（<4MB）直接上传，大文件分片上传
    CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
    
    session = requests.Session()
    session.trust_env = False
    
    try:
        # 步骤 1: precreate
        params = {
            'method': 'precreate',
            'access_token': token,
            'clienttype': '0'
        }
        
        data = {
            'path': remote_path,
            'size': str(file_size),
            'isdir': '0',
            'rtype': '3',  # 覆盖已有文件
            'block_list': json.dumps([file_md5]),
            'autoinit': '1'
        }
        
        headers = {
            'User-Agent': 'netdisk;P2SP;3.0.20.80',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        print("\n📋 步骤 1/3: 预创建文件...")
        resp = session.post(url, params=params, data=data, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        
        if result.get('errno') != 0:
            print(f"❌ precreate 失败：{result}")
            sys.exit(1)
        
        # 检查 return_type
        return_type = result.get('return_type', 0)
        print(f"   return_type: {return_type}")
        
        if return_type == 0:
            print("✅ 秒传成功！文件已存在")
            return
        
        # 需要上传
        uploadid = result.get('uploadid')
        if not uploadid:
            # 尝试从 block_list 响应中获取
            print("⚠️  未获取到 uploadid，尝试其他方式...")
            # 某些情况下百度不返回 uploadid，需要重新尝试
            # 这里简化处理，直接报错
            print("❌ 无法获取 uploadid，可能是百度 API 限制")
            print("   建议使用 bypy 库或其他工具上传")
            sys.exit(1)
        
        print(f"   uploadid: {uploadid}")
        
        # 步骤 2: 上传分片
        print("\n📤 步骤 2/3: 上传文件内容...")
        upload_url = "https://c.pcs.baidu.com/rest/2.0/pcs/superfile2"
        
        partseq = 0
        uploaded_size = 0
        
        with open(local_path, 'rb') as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                upload_params = {
                    'method': 'upload',
                    'access_token': token,
                    'type': 'tmpfile',
                    'path': remote_path,
                    'uploadid': uploadid,
                    'partseq': str(partseq)
                }
                
                files = {'file': (os.path.basename(local_path), chunk)}
                
                resp = session.post(upload_url, params=upload_params, files=files, timeout=120)
                resp.raise_for_status()
                upload_result = resp.json()
                
                if upload_result.get('errno') != 0 and 'md5' not in upload_result:
                    print(f"❌ 上传分片失败：{upload_result}")
                    sys.exit(1)
                
                uploaded_size += len(chunk)
                percent = uploaded_size / file_size * 100
                print(f"   进度：{format_size(uploaded_size)} / {format_size(file_size)} ({percent:.1f}%)")
                
                partseq += 1
        
        # 步骤 3: create
        print("\n📦 步骤 3/3: 创建文件...")
        create_params = {
            'method': 'create',  # 使用 create 而不是 precreate
            'access_token': token
        }
        create_data = {
            'path': remote_path,
            'size': str(file_size),
            'isdir': '0',
            'rtype': '3',
            'uploadid': uploadid,
            'block_list': json.dumps([file_md5])
        }
        
        resp = session.post(url, params=create_params, data=create_data, headers=headers, timeout=30)
        resp.raise_for_status()
        create_result = resp.json()
        
        if create_result.get('errno') != 0:
            print(f"❌ create 失败：{create_result}")
            sys.exit(1)
        
        print(f"\n✅ 上传成功：{remote_path}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络错误：{e}")
        sys.exit(1)
    finally:
        session.close()

def cmd_batch_download(remote_path, local_dir=None):
    """批量下载目录"""
    token = get_token()
    
    # 获取目录下所有文件
    print(f"📥 批量下载：{remote_path}")
    print("📋 正在获取文件列表...")
    
    all_files = []
    
    def collect_files(path):
        """递归收集文件"""
        url = "https://pan.baidu.com/rest/2.0/xpan/file"
        params = {
            'method': 'list',
            'access_token': token,
            'dir': path
        }
        
        session = requests.Session()
        session.trust_env = False
        
        try:
            resp = session.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("errno") != 0:
                print(f"❌ 获取 {path} 失败：{data}")
                return
            
            for f in data.get("list", []):
                if f.get('isdir', 0) == 1:
                    # 递归子目录
                    collect_files(f['path'])
                else:
                    all_files.append({
                        'path': f['path'],
                        'size': int(f.get('size', 0)),
                        'filename': f.get('server_filename', 'unknown')
                    })
        except Exception as e:
            print(f"❌ 错误：{e}")
        finally:
            session.close()
    
    collect_files(remote_path)
    
    if not all_files:
        print("❌ 没有找到文件")
        return
    
    print(f"✅ 找到 {len(all_files)} 个文件，总大小：{format_size(sum(f['size'] for f in all_files))}")
    
    # 确定本地保存目录
    if local_dir is None:
        local_dir = os.path.join(os.getcwd(), os.path.basename(remote_path.rstrip('/')))
    
    os.makedirs(local_dir, exist_ok=True)
    print(f"📁 保存到：{local_dir}")
    print()
    
    # 下载每个文件
    downloaded = 0
    failed = 0
    skipped = 0
    
    for i, file_info in enumerate(all_files, 1):
        remote_file = file_info['path']
        filename = file_info['filename']
        
        # 计算本地路径（保持目录结构）
        rel_path = remote_file.replace(remote_path.rstrip('/') + '/', '')
        local_path = os.path.join(local_dir, rel_path)
        
        # 创建父目录
        local_parent = os.path.dirname(local_path)
        if local_parent:
            os.makedirs(local_parent, exist_ok=True)
        
        # 检查是否已存在
        if os.path.exists(local_path):
            local_size = os.path.getsize(local_path)
            if local_size >= file_info['size']:
                print(f"[{i}/{len(all_files)}] ⏭️  跳过：{filename}")
                skipped += 1
                continue
        
        # 下载
        print(f"[{i}/{len(all_files)}] 📥 下载：{filename} ({format_size(file_info['size'])})")
        
        try:
            url = "https://d.pcs.baidu.com/rest/2.0/pcs/file"
            params = {
                'method': 'download',
                'access_token': token,
                'path': remote_file
            }
            
            session = requests.Session()
            session.trust_env = False
            
            with session.get(url, params=params, headers=DOWNLOAD_HEADERS, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                
                with open(local_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            
            print(f"      ✅ 完成")
            downloaded += 1
            session.close()
            
        except Exception as e:
            print(f"      ❌ 失败：{e}")
            failed += 1
            try:
                session.close()
            except:
                pass
    
    print()
    print("=" * 60)
    print(f"批量下载完成！")
    print(f"  成功：{downloaded} 个")
    print(f"  跳过：{skipped} 个")
    print(f"  失败：{failed} 个")
    print(f"  保存位置：{local_dir}")
    print("=" * 60)

def main():
    if len(sys.argv) < 2:
        print("用法：bdpan_enhanced.py <命令> [参数]")
        print("命令：info, list, tree, search, stats, delete, download, upload, batch-download")
        print("示例:")
        print("  bdpan_enhanced.py info")
        print("  bdpan_enhanced.py tree /开智 -d 2")
        print("  bdpan_enhanced.py search mp4 /开智")
        print("  bdpan_enhanced.py stats /开智")
        print("  bdpan_enhanced.py delete /path/to/file (会要求确认)")
        print("  bdpan_enhanced.py download /path/to/file [保存路径]")
        print("  bdpan_enhanced.py upload 本地文件.txt [/网盘/路径/]")
        print("  bdpan_enhanced.py batch-download /网盘/目录 [本地保存目录]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'info':
        cmd_info()
    elif cmd == 'list':
        path = sys.argv[2] if len(sys.argv) > 2 else '/'
        recursive = '-R' in sys.argv
        cmd_list(path, recursive)
    elif cmd == 'tree':
        path = sys.argv[2] if len(sys.argv) > 2 else '/'
        depth = 2
        if '-d' in sys.argv:
            idx = sys.argv.index('-d')
            if idx + 1 < len(sys.argv):
                depth = int(sys.argv[idx + 1])
        cmd_tree(path, depth)
    elif cmd == 'search':
        keyword = sys.argv[2] if len(sys.argv) > 2 else ''
        path = sys.argv[3] if len(sys.argv) > 3 else '/'
        cmd_search(keyword, path)
    elif cmd == 'stats':
        path = sys.argv[2] if len(sys.argv) > 2 else '/'
        cmd_stats(path)
    elif cmd == 'delete':
        if len(sys.argv) < 3:
            print("❌ 用法：bdpan_enhanced.py delete /path/to/file")
            sys.exit(1)
        path = sys.argv[2]
        cmd_delete(path, confirm=False)  # 交互式确认
    elif cmd == 'download':
        if len(sys.argv) < 3:
            print("❌ 用法：bdpan_enhanced.py download /网盘/文件路径 [本地保存路径]")
            sys.exit(1)
        path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_download(path, output_path)
    elif cmd == 'upload':
        if len(sys.argv) < 3:
            print("❌ 用法：bdpan_enhanced.py upload 本地文件.txt [/网盘/路径/]")
            sys.exit(1)
        local_path = sys.argv[2]
        remote_path = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_upload(local_path, remote_path)
    elif cmd == 'batch-download':
        if len(sys.argv) < 3:
            print("❌ 用法：bdpan_enhanced.py batch-download /网盘/目录 [本地保存目录]")
            sys.exit(1)
        remote_path = sys.argv[2]
        local_dir = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_batch_download(remote_path, local_dir)
    else:
        print(f"❌ 未知命令：{cmd}")
        sys.exit(1)

if __name__ == '__main__':
    main()
