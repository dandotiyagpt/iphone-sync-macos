#!/usr/bin/env bash
set -euo pipefail

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Upgrading pip..."
./.venv/bin/pip install --upgrade pip

echo "Installing iPhone Sync..."
./.venv/bin/pip install -e ".[dev]"

echo "Done! Run the apps with:"
echo "  ./run-sync.command     — photo sync + encrypted device backup (WhatsApp)"
echo "  ./run-gallery.command  — browse synced photos"
