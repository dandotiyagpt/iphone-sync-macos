"""py2app packaging entry point — builds dist/iPhone Sync.app."""

from __future__ import annotations

import tomllib
from pathlib import Path

from setuptools import setup

ROOT = Path(__file__).resolve().parent


def _project_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


VERSION = _project_version()

APP = ["src/iphone_sync/__main__.py"]
DATA_FILES: list[str] = []
OPTIONS = {
    "argv_emulation": False,
    "packages": [
        "iphone_sync",
        "pymobiledevice3",
        "PySide6",
        "PIL",
        "pillow_heif",
        "av",
        "objc",
        "Foundation",
        "AppKit",
        "Cocoa",
    ],
    "includes": ["pymobiledevice3", "PySide6"],
    "excludes": ["tkinter", "unittest", "test"],
    "plist": {
        "CFBundleName": "iPhone Sync",
        "CFBundleDisplayName": "iPhone Sync",
        "CFBundleIdentifier": "com.iphonesync.app",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "12.0",
        "LSUIElement": False,
        "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": (
            "iPhone Sync needs to manage its Start at Login helper."
        ),
    },
}

setup(
    app=APP,
    name="iPhone Sync",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
