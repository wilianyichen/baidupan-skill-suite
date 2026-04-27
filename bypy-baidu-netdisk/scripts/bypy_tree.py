#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度网盘目录树查看工具
功能：递归列出百度网盘指定目录的所有文件和子目录，支持过滤和格式化输出
"""

import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_runtime import configure_runtime, describe_token_search_order, prepare_bypy_config_dir

configure_runtime()


def load_bypy():
    try:
        from bypy import ByPy
    except ModuleNotFoundError:
        print("❌ 当前 Python 环境未安装 bypy")
        print("请先执行：pip install bypy")
        sys.exit(1)
    return ByPy


def create_bypy_instance():
    ByPy = load_bypy()
    config_dir = prepare_bypy_config_dir(__file__)
    return ByPy(configdir=str(config_dir))

def print_tree(path='/', indent=0, prefix=''):
    """
    递归打印百度网盘目录树结构
    
    Args:
        path: 网盘路径
        indent: 当前缩进级别
        prefix: 前缀符号
    """
    bp = create_bypy_instance()
    
    try:
        result = bp.list(path)
        
        if result != 0:
            print(f"❌ 无法访问目录：{path}")
            return
        
        files = result.get('list', [])
        
        # 分离目录和文件
        dirs = [f for f in files if f.get('isdir', False)]
        files_list = [f for f in files if not f.get('isdir', False)]
        
        # 打印目录
        for i, dir_item in enumerate(dirs):
            is_last = (i == len(dirs) - 1) and (len(files_list) == 0)
            symbol = '└── ' if is_last else '├── '
            size_str = f" ({format_size(dir_item.get('size', 0))})" if dir_item.get('size', 0) > 0 else ""
            print(f"{prefix}{symbol}📁 {dir_item['name']}{size_str}")
            
            # 递归子目录
            next_prefix = prefix + ('    ' if is_last else '│   ')
            print_tree(f"{path}/{dir_item['name']}".replace('//', '/'), indent + 1, next_prefix)
        
        # 打印文件
        for i, file_item in enumerate(files_list):
            is_last = (i == len(files_list) - 1)
            symbol = '└── ' if is_last else '├── '
            size_str = format_size(file_item.get('size', 0))
            print(f"{prefix}{symbol}📄 {file_item['name']} ({size_str})")
            
    except Exception as e:
        print(f"{prefix}❌ 错误：{str(e)}")

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
    else:
        return f"{size:.2f} {units[unit_index]}"

def show_summary(path='/'):
    """显示目录统计信息"""
    bp = create_bypy_instance()
    
    try:
        result = bp.list(path)
        if result == 0:
            files = result.get('list', [])
            total_dirs = sum(1 for f in files if f.get('isdir', False))
            total_files = sum(1 for f in files if not f.get('isdir', False))
            total_size = sum(f.get('size', 0) for f in files if not f.get('isdir', False))
            
            print(f"\n📊 统计信息:")
            print(f"   目录数：{total_dirs}")
            print(f"   文件数：{total_files}")
            print(f"   总大小：{format_size(total_size)}")
    except Exception as e:
        print(f"无法获取统计信息：{str(e)}")

def main():
    try:
        prepare_bypy_config_dir(__file__)
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        print("已检查：")
        for candidate in describe_token_search_order(__file__):
            print(f"  - {candidate}")
        sys.exit(1)
    except OSError as exc:
        print(f"❌ 无法为 bypy 准备 token：{exc}")
        print("请确认当前工作目录或 BYPY_CONFIG_DIR 指向的位置可写")
        sys.exit(1)

    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        target_path = '/'
    
    print(f"🔍 百度网盘目录树：{target_path}")
    print("=" * 60)
    
    print_tree(target_path)
    show_summary(target_path)
    
    print("\n" + "=" * 60)
    print("💡 提示：可以使用 'bypy tree /path > output.txt' 保存结果")

if __name__ == '__main__':
    main()
