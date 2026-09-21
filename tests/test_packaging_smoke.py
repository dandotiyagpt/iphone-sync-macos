"""Packaging smoke tests for the macOS iPhone Sync distribution.

These checks guard the two things that most easily rot in a sibling-port:
that the `iphone_sync` package (and the modules this port is responsible
for) can actually be imported after an editable install, and that the
Windows-only dependencies (`pywin32`, `pyinstaller`) never creep back into
`pyproject.toml`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.unit
@pytest.mark.parametrize(
    "module_name",
    [
        "iphone_sync",
        "iphone_sync.core.manifest",
        "iphone_sync.utils.paths",
    ],
)
def test_package_modules_import(module_name: str) -> None:
    """Each core module should import cleanly after `pip install -e .`.

    Skips (rather than fails) when the package isn't installed yet, so
    collection never breaks a clean checkout before `install.sh` has run.
    """
    pytest.importorskip(
        module_name,
        reason=(
            f"{module_name!r} is not importable — run install.sh "
            "(pip install -e '.[dev]') before running this test"
        ),
    )


@pytest.mark.unit
def test_pyproject_excludes_windows_only_dependencies() -> None:
    """pyproject.toml must never reintroduce Windows-only build tooling."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "pywin32" not in pyproject_text
    assert "pyinstaller" not in pyproject_text
