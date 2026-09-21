"""Guards for the macOS DMG packager and GitHub Release workflow.

These are text-level checks so they run on Windows CI clones too. The actual
hdiutil / py2app build only runs on macOS (local ./build.sh or GHA macos-14).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.unit
def test_dmg_script_uses_pyproject_version_and_hdiutil() -> None:
    script = (REPO_ROOT / "scripts" / "package_dmg.sh").read_text(encoding="utf-8")

    assert "pyproject.toml" in script
    assert "PYTHON_BIN" in script
    assert "hdiutil create" in script
    assert "/Applications" in script
    assert "iPhoneSync-macos-" in script


@pytest.mark.unit
def test_build_sh_invokes_py2app_then_dmg_script() -> None:
    script = (REPO_ROOT / "build.sh").read_text(encoding="utf-8")

    assert "setup.py py2app" in script
    assert "scripts/package_dmg.sh" in script
    assert "setuptools>=68,<81" in script
    assert "PYTHON_BIN" in script


@pytest.mark.unit
def test_release_workflow_builds_on_macos_and_uploads_dmg() -> None:
    workflow = (
        REPO_ROOT / ".github" / "workflows" / "macos-release.yml"
    ).read_text(encoding="utf-8")

    assert "macos-14" in workflow
    assert "dist/*.dmg" in workflow
    assert "softprops/action-gh-release@v2" in workflow
    assert "PYTHON_BIN" in workflow
    assert "bash ./build.sh" in workflow
    assert "chmod +x" in workflow
    assert "pyinstaller" not in workflow.lower()


@pytest.mark.unit
def test_setup_py_reads_version_from_pyproject() -> None:
    setup_text = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "pyproject.toml" in setup_text
    assert "version = \"" in pyproject
    assert "py2app" in setup_text
    assert "pyinstaller" not in setup_text.lower()
