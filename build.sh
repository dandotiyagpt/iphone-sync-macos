#!/usr/bin/env bash
# Build dist/iPhone Sync.app (py2app) then wrap it in a DMG.
# Must run on macOS. GitHub Actions macos-14 is the CI path.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PY="$PYTHON_BIN"
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  PY=python3
fi

echo "Using interpreter: $PY ($("$PY" -c 'import sys; print(sys.executable)'))"

echo "Installing dependencies..."
"$PY" -m pip install -U pip
# py2app still uses python setup.py; setuptools 81+ drops install_requires.
"$PY" -m pip install "setuptools>=68,<81" wheel
"$PY" -m pip install -e ".[dev]"

echo "Building app bundle..."
"$PY" setup.py py2app

echo "Building disk image..."
"$ROOT/scripts/package_dmg.sh"

echo "Done."
ls -lh dist/*.app dist/*.dmg
