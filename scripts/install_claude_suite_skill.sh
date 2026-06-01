#!/usr/bin/env bash
set -euo pipefail

SUITE_ROOT="${1:-$HOME/tools/baidupan-tools}"
CLAUDE_SKILLS_DIR="${2:-$HOME/.claude/skills}"
SKILLS=(
  baidupan-apply
  baidupan-archive
  baidupan-batch-runner
  baidupan-cleanup
  baidupan-fs
  baidupan-index
  baidupan-monitor
  baidupan-reconcile
  baidupan-suite
  baidupan-sync
  baidupan-verify
  bypy-baidu-netdisk
  bypy-enhanced
)

if [ ! -f "$SUITE_ROOT/README.md" ]; then
  echo "ERROR: suite root not found: $SUITE_ROOT" >&2
  exit 1
fi

mkdir -p "$CLAUDE_SKILLS_DIR"

for skill in "${SKILLS[@]}"; do
  if [ ! -f "$SUITE_ROOT/$skill/SKILL.md" ]; then
    echo "ERROR: skill missing: $SUITE_ROOT/$skill/SKILL.md" >&2
    exit 1
  fi
  ln -sfn "$SUITE_ROOT/$skill" "$CLAUDE_SKILLS_DIR/$skill"
done

ln -sfn "$SUITE_ROOT/common" "$CLAUDE_SKILLS_DIR/common"

echo "Installed Claude skills:"
for skill in "${SKILLS[@]}"; do
  echo "  $CLAUDE_SKILLS_DIR/$skill -> $SUITE_ROOT/$skill"
done
echo "  $CLAUDE_SKILLS_DIR/common -> $SUITE_ROOT/common"
echo
echo "Next:"
echo "  1. Run: $SUITE_ROOT/.venv/bin/python $SUITE_ROOT/bypy-enhanced/scripts/bdpan_enhanced.py doctor"
echo "  2. If needed, run auth flow: $SUITE_ROOT/.venv/bin/python $SUITE_ROOT/bypy-enhanced/scripts/bdpan_enhanced.py auth"
echo "  3. Start a new Claude session"
