#!/usr/bin/env bash
# 百度网盘 bypy 授权和使用脚本（Linux 辅助脚本）
# 用法：./bypy_auth.sh

set -e

# 清除代理设置（直连网络）
export http_proxy=""
export https_proxy=""
export HTTP_PROXY=""
export HTTPS_PROXY=""

if ! command -v bypy >/dev/null 2>&1; then
    echo "错误：当前环境未找到 bypy 命令"
    echo "请先执行：pip install bypy"
    exit 1
fi

echo "======================================"
echo "  百度网盘 bypy 授权工具"
echo "======================================"
echo ""
echo "步骤 1: 复制以下链接到浏览器打开"
echo "--------------------------------------"
echo "https://openapi.baidu.com/oauth/2.0/authorize?client_id=q8WE4EpCsau1oS0MplgMKNBn&response_type=code&redirect_uri=oob&scope=basic+netdisk"
echo "--------------------------------------"
echo ""
echo "步骤 2: 登录百度账号并授权"
echo "步骤 3: 复制授权码（Authorization Code）"
echo ""
read -p "粘贴授权码并按回车：" AUTH_CODE

if [ -z "$AUTH_CODE" ]; then
    echo "错误：未输入授权码"
    exit 1
fi

echo ""
echo "正在授权..."
bypy -c "info" <<< "$AUTH_CODE"

echo ""
echo "授权完成！测试连接..."
bypy info

echo ""
echo "======================================"
echo "  常用命令速查"
echo "======================================"
echo "bypy list              - 列出根目录"
echo "bypy list -R /path     - 递归列出目录（类似 tree）"
echo "bypy upload 本地文件 网盘路径  - 上传文件"
echo "bypy download 网盘路径 本地路径  - 下载文件"
echo "bypy search 关键词      - 搜索文件"
echo "bypy info              - 查看网盘空间"
echo "======================================"
