#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/3] 创建最小虚拟环境"
python3 "$ROOT_DIR/scripts/bootstrap_min_venv.py"

echo "[2/3] 验证增强脚本"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/bypy-enhanced/scripts/bdpan_enhanced.py" info

echo "[3/3] 完成"
echo "后续可直接使用："
echo "  $ROOT_DIR/.venv/bin/python $ROOT_DIR/bypy-enhanced/scripts/bdpan_enhanced.py list /"
echo "  $ROOT_DIR/.venv/bin/python $ROOT_DIR/baidupan-reconcile/scripts/bdpan_reconcile.py --help"
