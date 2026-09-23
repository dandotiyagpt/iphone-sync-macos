"""Shared pytest fixtures/config for the iphone-sync-macos test suite.

The package should already be importable via `pythonpath = ["src"]` in
pyproject.toml's [tool.pytest.ini_options], but we add a belt-and-braces
sys.path fallback here in case pytest is invoked in a way that doesn't pick
up the pyproject config (e.g. running a single test file directly).
"""

import os
import sys
from pathlib import Path

# Belt-and-braces: ensure src/ is importable even if pyproject's
# pythonpath setting isn't honored by the invocation method.
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Force headless Qt so any test that transitively imports PySide6 widgets
# runs safely without a display (must be set before any Qt import happens).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Ensure headless QApplication exists for all tests involving Qt objects."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
