#!/usr/bin/env bash
set -euo pipefail

BUNDLE_PATH="${1:-}"
INSTALL_PARENT="${2:-$HOME/tools}"
ROOT_NAME="${3:-baidupan-tools}"
TARGET_DIR="$INSTALL_PARENT/$ROOT_NAME"

if [ -z "$BUNDLE_PATH" ]; then
  echo "Usage: bash update_linux_bundle.sh <bundle.tar.gz> [install_parent] [root_name]" >&2
  exit 1
fi

if [ ! -f "$BUNDLE_PATH" ]; then
  echo "ERROR: bundle not found: $BUNDLE_PATH" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${TARGET_DIR}.bak-${STAMP}"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "[1/7] extract bundle"
mkdir -p "$INSTALL_PARENT"
tar -xzf "$BUNDLE_PATH" -C "$TMP_DIR"

if [ ! -d "$TMP_DIR/$ROOT_NAME" ]; then
  echo "ERROR: extracted root not found: $TMP_DIR/$ROOT_NAME" >&2
  exit 1
fi

if [ -d "$TARGET_DIR" ]; then
  echo "[2/7] backup current install -> $BACKUP_DIR"
  mv "$TARGET_DIR" "$BACKUP_DIR"
else
  echo "[2/7] no previous install, skip backup"
fi

echo "[3/7] deploy new files"
mv "$TMP_DIR/$ROOT_NAME" "$TARGET_DIR"

if [ -d "$BACKUP_DIR" ]; then
  echo "[4/7] restore runtime data"
  for item in bypy.token.json bypy.json; do
    if [ -f "$BACKUP_DIR/$item" ] && [ ! -f "$TARGET_DIR/$item" ]; then
      cp -f "$BACKUP_DIR/$item" "$TARGET_DIR/$item"
    fi
  done

  for dir in .bdpan_snapshots .bypy_runtime .venv; do
    if [ -d "$BACKUP_DIR/$dir" ] && [ ! -e "$TARGET_DIR/$dir" ]; then
      cp -a "$BACKUP_DIR/$dir" "$TARGET_DIR/$dir"
    fi
  done
else
  echo "[4/7] no backup runtime data to restore"
fi

echo "[5/7] rebuild or validate venv"
if command -v python3 >/dev/null 2>&1; then
  python3 "$TARGET_DIR/scripts/bootstrap_min_venv.py"
else
  echo "WARN: python3 not found, skipped bootstrap_min_venv.py" >&2
fi

echo "[6/7] install or refresh Codex suite skill"
if [ -f "$TARGET_DIR/scripts/install_codex_suite_skill.sh" ] && [ -f "$TARGET_DIR/baidupan-suite/SKILL.md" ]; then
  bash "$TARGET_DIR/scripts/install_codex_suite_skill.sh" "$TARGET_DIR"
else
  echo "WARN: baidupan-suite or install_codex_suite_skill.sh not found, skipped skill install" >&2
fi

echo "[7/7] smoke test"
if [ -x "$TARGET_DIR/.venv/bin/python" ]; then
  "$TARGET_DIR/.venv/bin/python" "$TARGET_DIR/bypy-enhanced/scripts/bdpan_enhanced.py" info
else
  echo "WARN: venv python not found, skipped smoke test" >&2
fi

echo
echo "Update completed."
echo "Current install: $TARGET_DIR"
if [ -d "$BACKUP_DIR" ]; then
  echo "Backup kept at:  $BACKUP_DIR"
fi
