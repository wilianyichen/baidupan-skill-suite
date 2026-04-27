#!/usr/bin/env bash
set -euo pipefail

SUITE_ROOT="${1:-$HOME/tools/baidupan-tools}"
CODEX_SKILLS_DIR="${2:-$HOME/.codex/skills}"
SKILL_NAME="baidupan-suite"

if [ ! -f "$SUITE_ROOT/$SKILL_NAME/SKILL.md" ]; then
  echo "ERROR: skill not found: $SUITE_ROOT/$SKILL_NAME/SKILL.md" >&2
  exit 1
fi

mkdir -p "$CODEX_SKILLS_DIR"
ln -sfn "$SUITE_ROOT/$SKILL_NAME" "$CODEX_SKILLS_DIR/$SKILL_NAME"

echo "Installed skill:"
echo "  $CODEX_SKILLS_DIR/$SKILL_NAME -> $SUITE_ROOT/$SKILL_NAME"
echo
echo "Next:"
echo "  1. Start a new Codex session"
echo "  2. Use prompts like:"
echo "     - 用 baidupan-suite 查看百度网盘根目录"
echo "     - 用 baidupan-suite 比较本地目录和 /开智/录屏整理"
echo "     - 用 baidupan-suite 预览 archive manifest"
