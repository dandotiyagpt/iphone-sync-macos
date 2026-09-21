"""py2app packaging entry point — builds dist/iPhone Sync.app."""

from __future__ import annotations

from setuptools import setup

APP = ["src/iphone_sync/__main__.py"]
DATA_FILES: list[str] = []
OPTIONS = {
    "argv_emulation": False,
    "packages": ["iphone_sync"],
    "includes": ["pymobiledevice3", "PySide6"],
    "plist": {
        "CFBundleName": "iPhone Sync",
        "CFBundleDisplayName": "iPhone Sync",
        "CFBundleIdentifier": "com.iphonesync.app",
        "CFBundleShortVersionString": "1.0.0",
        "LSUIElement": False,
    },
}

setup(
    app=APP,
    name="iPhone Sync",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
