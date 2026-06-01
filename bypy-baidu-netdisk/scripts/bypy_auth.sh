#!/usr/bin/env bash
# 百度网盘 bypy 授权和使用脚本（Linux 辅助脚本）
# 用法：./bypy_auth.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"
ENHANCED_SCRIPT="$REPO_ROOT/bypy-enhanced/scripts/bdpan_enhanced.py"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "错误：未找到虚拟环境 Python：$PYTHON_BIN"
    echo "请先执行：python3 $REPO_ROOT/scripts/bootstrap_min_venv.py"
    exit 1
fi

echo "======================================"
echo "  百度网盘授权工具"
echo "======================================"
echo ""
"$PYTHON_BIN" "$ENHANCED_SCRIPT" auth

echo ""
read -r -p "粘贴 Authorization Code（留空则退出）：" AUTH_CODE
if [ -z "$AUTH_CODE" ]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "正在授权并验证..."
"$PYTHON_BIN" "$ENHANCED_SCRIPT" auth --code "$AUTH_CODE"

echo ""
echo "======================================"
echo "  常用命令速查"
echo "======================================"
echo "$PYTHON_BIN $ENHANCED_SCRIPT doctor"
echo "$PYTHON_BIN $ENHANCED_SCRIPT info"
echo "$PYTHON_BIN $ENHANCED_SCRIPT whoami"
echo "$PYTHON_BIN $ENHANCED_SCRIPT list /"
echo "$PYTHON_BIN $ENHANCED_SCRIPT du /路径"
echo "======================================"
