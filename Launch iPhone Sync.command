#!/usr/bin/env bash
# Double-click this file in Finder to launch iPhone Sync!
cd "$(dirname "$0")"

if [ -d "./iPhone Sync.app" ]; then
    open "./iPhone Sync.app"
    # Close this terminal tab/window automatically
    osascript -e 'tell application "Terminal" to close (every window whose name contains "Launch iPhone Sync")' &>/dev/null &
    exit 0
fi

if [ ! -x "./.venv/bin/python" ]; then
    echo "Virtual environment not found. Run ./install.sh first."
    read -n 1 -s -r -p "Press any key to continue..."
    exit 1
fi

./.venv/bin/python -m iphone_sync
