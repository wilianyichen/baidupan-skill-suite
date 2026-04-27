#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度网盘 bypy 命令行工具包装器
解决非交互模式下 token 读取问题
"""

import os
import sys
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


def prepare_bypy_token():
    try:
        config_dir = prepare_bypy_config_dir(__file__)
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
    return config_dir

def main():
    if len(sys.argv) < 2:
        print("用法：python bypy_cmd.py <command> [args...]")
        print("示例:")
        print("  python bypy_cmd.py info          - 查看网盘信息")
        print("  python bypy_cmd.py list /        - 列出根目录")
        print("  python bypy_cmd.py list -R /apps - 递归列出目录")
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    try:
        config_dir = prepare_bypy_token()
        ByPy = load_bypy()
        bp = ByPy(configdir=str(config_dir))
        
        if command == 'info':
            result = bp.info()
            if result == 0:
                print("✅ 网盘信息获取成功")
            else:
                print(f"❌ 获取失败：{result}")
        
        elif command == 'list':
            path = args[0] if args else '/'
            recursive = '-R' in args or '-r' in args
            if recursive:
                # 递归列出
                def list_tree(path='/', indent=0):
                    result = bp.list(path)
                    if result != 0:
                        return
                    files = result.get('list', [])
                    for f in files:
                        prefix = '  ' * indent
                        icon = '📁' if f.get('isdir') else '📄'
                        size = f.get('size', 0)
                        size_str = f" ({size/1024/1024:.1f}MB)" if size > 0 and not f.get('isdir') else ''
                        print(f"{prefix}{icon} {f['name']}{size_str}")
                        if f.get('isdir'):
                            list_tree(f"{path}/{f['name']}".replace('//', '/'), indent + 1)
                list_tree(path)
            else:
                result = bp.list(path)
                if result != 0:
                    print(f"❌ 列出失败：{result}")
                    return
                files = result.get('list', [])
                for f in files:
                    icon = '📁' if f.get('isdir') else '📄'
                    size = f.get('size', 0)
                    size_str = f" ({size/1024/1024:.1f}MB)" if size > 0 and not f.get('isdir') else ''
                    print(f"{icon} {f['name']}{size_str}")
        
        elif command == 'upload':
            if len(args) < 2:
                print("用法：upload <本地文件> <网盘路径>")
                sys.exit(1)
            local_file = args[0]
            remote_path = args[1]
            result = bp.upload(local_file, remote_path)
            if result == 0:
                print(f"✅ 上传成功：{local_file} → {remote_path}")
            else:
                print(f"❌ 上传失败：{result}")
        
        elif command == 'download':
            if len(args) < 2:
                print("用法：download <网盘路径> <本地路径>")
                sys.exit(1)
            remote_path = args[0]
            local_file = args[1]
            result = bp.download(remote_path, local_file)
            if result == 0:
                print(f"✅ 下载成功：{remote_path} → {local_file}")
            else:
                print(f"❌ 下载失败：{result}")
        
        elif command == 'search':
            if not args:
                print("用法：search <关键词>")
                sys.exit(1)
            keyword = args[0]
            result = bp.search(keyword)
            if result != 0:
                print(f"❌ 搜索失败：{result}")
                return
            # 处理搜索结果...
            print(f"搜索 '{keyword}' 的结果：{result}")
        
        else:
            print(f"❌ 未知命令：{command}")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ 错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
