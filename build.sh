#!/usr/bin/env bash
# Build dist/iPhone Sync.app (py2app) then wrap it in a DMG.
# Must run on macOS. GitHub Actions macos-14 is the CI path.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "Installing dependencies..."
python3 -m pip install -U pip
python3 -m pip install -e ".[dev]"

echo "Building app bundle..."
python3 setup.py py2app

echo "Building disk image..."
"$ROOT/scripts/package_dmg.sh"

echo "Done."
ls -lh dist/*.app dist/*.dmg
