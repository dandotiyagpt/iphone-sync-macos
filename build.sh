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
"$PY" -m pip install "setuptools>=68,<70" wheel
"$PY" -m pip install -e ".[dev]"

echo "Building app bundle..."
# py2app + setuptools error if [project] pyproject.toml sits next to setup.py:
# "install_requires is no longer supported". Hide it for the freeze only.
export IPHONE_SYNC_VERSION="$(
  "$PY" -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
)"
mv pyproject.toml .pyproject.toml.freeze
restore_pyproject() {
  if [[ -f .pyproject.toml.freeze ]]; then
    mv .pyproject.toml.freeze pyproject.toml
  fi
}
trap restore_pyproject EXIT
"$PY" setup.py py2app
restore_pyproject
trap - EXIT

echo "Building disk image..."
"$ROOT/scripts/package_dmg.sh"

echo "Done."
ls -lh dist/*.app dist/*.dmg
