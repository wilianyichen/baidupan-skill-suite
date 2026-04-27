#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度网盘命令行工具 - 使用原生 API
绕过 bypy 的交互式认证问题
"""

import os
import sys
import requests
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_runtime import configure_runtime, describe_token_search_order, load_access_token

configure_runtime()
ACCESS_TOKEN = None
API_BASE = 'https://pan.baidu.com/rest/2.0/xpan'

def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"

def format_time(timestamp):
    """格式化时间戳"""
    if timestamp == 0:
        return "N/A"
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')

def api_request(method, endpoint, params=None, data=None, post=False):
    """调用百度网盘 API"""
    url = f"{API_BASE}{endpoint}"
    if params is None:
        params = {}
    params['access_token'] = ACCESS_TOKEN
    params['method'] = method
    
    if post:
        response = requests.post(url, params=params, data=data, timeout=60)
    else:
        response = requests.get(url, params=params, timeout=60)
    
    return response.json()

def cmd_info(args):
    """查看网盘信息"""
    result = api_request('uinfo', '/nas')
    if 'baidu_name' in result:
        print(f"✅ 百度网盘 - {result['baidu_name']}")
        print(f"   用户名：{result.get('name', 'N/A')}")
        quota = result.get('quota', 0)
        used = result.get('used', 0)
        print(f"   总容量：{format_size(quota)}")
        print(f"   已使用：{format_size(used)}")
        print(f"   剩余：{format_size(quota - used)}")
        if quota > 0:
            print(f"   使用率：{used/quota*100:.1f}%")
    else:
        print(f"❌ 获取失败：{result}")

def cmd_list(args):
    """列出目录"""
    recursive = False
    path = '/'
    
    for arg in args:
        if arg in ['-R', '-r', '--recursive']:
            recursive = True
        elif not arg.startswith('-'):
            path = arg
    
    def list_dir(path, indent=0):
        result = api_request('list', '/file', {'path': path, 'dir': path})
        if result.get('errno') != 0:
            print(f"❌ 无法访问：{path} (错误码：{result.get('errno')})")
            return
        
        files = result.get('list', [])
        if not files:
            print("  " * indent + "📂 (空目录)")
            return
        
        # 分离目录和文件
        dirs = [f for f in files if f.get('isdir') == 1]
        files_list = [f for f in files if f.get('isdir') == 0]
        
        # 打印目录
        for i, d in enumerate(dirs):
            is_last = (i == len(dirs) - 1) and (len(files_list) == 0)
            symbol = '└── ' if is_last else '├── '
            name = d.get('server_filename', d.get('name', 'Unknown'))
            mtime = format_time(d.get('server_mtime', 0))
            print(f"{'  ' * indent}{symbol}📁 {name} ({mtime})")
            if recursive:
                next_path = f"{path}/{name}".replace('//', '/')
                list_dir(next_path, indent + 1)
        
        # 打印文件
        for i, f in enumerate(files_list):
            is_last = (i == len(files_list) - 1)
            symbol = '└── ' if is_last else '├── '
            name = f.get('server_filename', f.get('name', 'Unknown'))
            size = format_size(f.get('size', 0))
            mtime = format_time(f.get('server_mtime', 0))
            print(f"{'  ' * indent}{symbol}📄 {name} ({size}, {mtime})")
    
    print(f"📁 {path}")
    print("=" * 60)
    list_dir(path)
    print("=" * 60)

def cmd_search(args):
    """搜索文件"""
    if not args:
        print("用法：search <关键词>")
        return
    
    keyword = args[0]
    # 百度网盘搜索 API 需要特殊权限，这里使用简化版本
    print(f"🔍 搜索：{keyword}")
    print("注意：完整搜索功能需要更高权限，当前仅支持列出目录后手动查找")

def cmd_tree(args):
    """树形显示目录（类似 tree 命令）"""
    path = args[0] if args else '/'
    print(f"🌳 百度网盘目录树：{path}")
    print("=" * 60)
    cmd_list(['-R', path])

def cmd_help(args):
    """显示帮助"""
    print("""
📖 百度网盘命令行工具 - 使用说明

用法：python bdpan.py <命令> [参数]

命令:
  info              查看网盘信息（容量、用户名等）
  list [路径]       列出目录内容
  list -R [路径]    递归列出目录（tree 模式）
  tree [路径]       树形显示目录
  search <关键词>   搜索文件
  help              显示此帮助信息

示例:
  python bdpan.py info              # 查看网盘信息
  python bdpan.py list /            # 列出根目录
  python bdpan.py list -R /apps     # 递归列出/apps 目录
  python bdpan.py tree /            # 树形显示根目录

Token 查找优先级：
  1. BYPY_TOKEN_FILE
  2. ~/.bypy/bypy.token.json
  3. ./bypy.token.json
  4. 项目根目录下的 bypy.token.json
""")

def main():
    global ACCESS_TOKEN

    try:
        ACCESS_TOKEN = load_access_token(__file__)
    except (FileNotFoundError, KeyError) as exc:
        print(f"❌ {exc}")
        print("已检查：")
        for candidate in describe_token_search_order(__file__):
            print(f"  - {candidate}")
        print("运行：bypy info 完成授权，或在当前目录放置 bypy.token.json")
        sys.exit(1)

    if len(sys.argv) < 2:
        cmd_help([])
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    commands = {
        'info': cmd_info,
        'list': cmd_list,
        'tree': cmd_tree,
        'search': cmd_search,
        'help': cmd_help,
        '--help': cmd_help,
        '-h': cmd_help,
    }
    
    if command in commands:
        commands[command](args)
    else:
        print(f"❌ 未知命令：{command}")
        print("运行 'python bdpan.py help' 查看使用说明")
        sys.exit(1)

if __name__ == '__main__':
    main()
