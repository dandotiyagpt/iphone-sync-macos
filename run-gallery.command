#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -x "./.venv/bin/python" ]; then
    echo "Virtual environment not found. Run install.sh first."
    read -n 1 -s -r -p "Press any key to continue..."
    exit 1
fi
./.venv/bin/python -m iphone_sync.gallery
status=$?
if [ $status -ne 0 ]; then
    echo ""
    echo "iPhone Photos gallery exited with an error."
    read -n 1 -s -r -p "Press any key to continue..."
fi
