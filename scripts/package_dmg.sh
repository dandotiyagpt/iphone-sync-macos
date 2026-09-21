#!/usr/bin/env bash
# Wrap dist/iPhone Sync.app into a drag-to-Applications DMG.
# Version is read from pyproject.toml (one writer).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP="$ROOT/dist/iPhone Sync.app"
if [[ ! -d "$APP" ]]; then
  echo "Missing: $APP" >&2
  echo "Run ./build.sh on macOS first." >&2
  exit 1
fi

PY="${PYTHON_BIN:-python3}"
VERSION="$(
  "$PY" -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
)"
DMG_NAME="iPhoneSync-macos-${VERSION}.dmg"
OUT="$ROOT/dist/${DMG_NAME}"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/iphone-sync-dmg.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

rm -f "$OUT"
hdiutil create \
  -volname "iPhone Sync" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$OUT"

echo "Disk image: $OUT"
