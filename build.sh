#!/usr/bin/env bash
set -euo pipefail

echo "Installing dependencies..."
pip install -e ".[dev]"

echo "Building app bundle..."
python setup.py py2app

echo "Done. App bundle at dist/iPhone Sync.app"
