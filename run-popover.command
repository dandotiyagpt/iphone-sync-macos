#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -x "./.venv/bin/python" ]; then
    echo "Virtual environment not found. Run ./install.sh first."
    read -n 1 -s -r -p "Press any key to continue..."
    exit 1
fi
./.venv/bin/python -m iphone_sync.ui.tray_popover
