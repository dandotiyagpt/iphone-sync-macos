"""Tests for the macOS LaunchAgent-based start-at-login helpers."""

from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

from iphone_sync.utils.startup import (
    LAUNCH_AGENT_LABEL,
    is_start_at_login,
    program_arguments,
    set_start_at_login,
)


def _plist_path(home_dir: Path) -> Path:
    return home_dir / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


class _FakeRunner:
    """Records subprocess.run-style calls and optionally raises."""

    def __init__(self, side_effect: Exception | None = None) -> None:
        self.side_effect = side_effect
        self.calls: list[list[str]] = []

    def __call__(self, argv, *args, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append(list(argv))
        if self.side_effect is not None:
            raise self.side_effect
        return subprocess.CompletedProcess(argv, 0)


def test_enable_creates_plist_with_correct_contents(tmp_path: Path) -> None:
    runner = _FakeRunner()

    set_start_at_login(True, home_dir=tmp_path, runner=runner)

    plist_path = _plist_path(tmp_path)
    assert plist_path.is_file()

    with plist_path.open("rb") as fh:
        data = plistlib.load(fh)

    assert data["Label"] == LAUNCH_AGENT_LABEL
    assert data["RunAtLoad"] is True
    assert data["ProgramArguments"] == [sys.executable, "-m", "iphone_sync"]


def test_is_start_at_login_false_before_and_true_after(tmp_path: Path) -> None:
    runner = _FakeRunner()

    assert is_start_at_login(home_dir=tmp_path) is False

    set_start_at_login(True, home_dir=tmp_path, runner=runner)

    assert is_start_at_login(home_dir=tmp_path) is True


def test_enabling_twice_is_idempotent(tmp_path: Path) -> None:
    runner = _FakeRunner()

    set_start_at_login(True, home_dir=tmp_path, runner=runner)
    set_start_at_login(True, home_dir=tmp_path, runner=runner)

    plist_path = _plist_path(tmp_path)
    assert plist_path.is_file()
    with plist_path.open("rb") as fh:
        data = plistlib.load(fh)
    assert data["Label"] == LAUNCH_AGENT_LABEL
    assert data["RunAtLoad"] is True
    assert is_start_at_login(home_dir=tmp_path) is True


def test_disabling_removes_plist_and_flips_flag(tmp_path: Path) -> None:
    runner = _FakeRunner()

    set_start_at_login(True, home_dir=tmp_path, runner=runner)
    assert is_start_at_login(home_dir=tmp_path) is True

    set_start_at_login(False, home_dir=tmp_path, runner=runner)

    plist_path = _plist_path(tmp_path)
    assert not plist_path.exists()
    assert is_start_at_login(home_dir=tmp_path) is False


def test_disabling_with_no_plist_is_safe_noop(tmp_path: Path) -> None:
    runner = _FakeRunner()

    # Should not raise even though nothing was ever enabled.
    set_start_at_login(False, home_dir=tmp_path, runner=runner)

    assert not _plist_path(tmp_path).exists()
    assert is_start_at_login(home_dir=tmp_path) is False


def test_enable_swallows_launchctl_bootstrap_failure(tmp_path: Path) -> None:
    runner = _FakeRunner(
        side_effect=subprocess.CalledProcessError(returncode=1, cmd=["launchctl"])
    )

    # Should not raise, and the plist should still be written.
    set_start_at_login(True, home_dir=tmp_path, runner=runner)

    assert _plist_path(tmp_path).is_file()
    assert is_start_at_login(home_dir=tmp_path) is True


def test_disable_swallows_launchctl_bootout_failure(tmp_path: Path) -> None:
    enable_runner = _FakeRunner()
    set_start_at_login(True, home_dir=tmp_path, runner=enable_runner)

    disable_runner = _FakeRunner(
        side_effect=subprocess.CalledProcessError(returncode=1, cmd=["launchctl"])
    )

    # Should not raise, and the plist should still be removed.
    set_start_at_login(False, home_dir=tmp_path, runner=disable_runner)

    assert not _plist_path(tmp_path).exists()


@pytest.mark.parametrize("exc", [FileNotFoundError(), OSError("boom")])
def test_enable_swallows_other_subprocess_errors(tmp_path: Path, exc: Exception) -> None:
    runner = _FakeRunner(side_effect=exc)

    set_start_at_login(True, home_dir=tmp_path, runner=runner)

    assert _plist_path(tmp_path).is_file()


def test_runner_invoked_with_launchctl_bootstrap_argv(tmp_path: Path) -> None:
    runner = _FakeRunner()

    set_start_at_login(True, home_dir=tmp_path, runner=runner)

    assert len(runner.calls) == 1
    argv = runner.calls[0]
    assert argv[0] == "launchctl"
    assert argv[1] == "bootstrap"
    assert argv[2].startswith("gui/")
    assert argv[3] == str(_plist_path(tmp_path))


def test_runner_invoked_with_launchctl_bootout_argv(tmp_path: Path) -> None:
    enable_runner = _FakeRunner()
    set_start_at_login(True, home_dir=tmp_path, runner=enable_runner)

    disable_runner = _FakeRunner()
    set_start_at_login(False, home_dir=tmp_path, runner=disable_runner)

    assert len(disable_runner.calls) == 1
    argv = disable_runner.calls[0]
    assert argv[0] == "launchctl"
    assert argv[1] == "bootout"
    assert argv[2].startswith("gui/")
    assert f"gui/" in argv[2] and argv[2].endswith(f"/{LAUNCH_AGENT_LABEL}")


def test_is_start_at_login_false_when_runatload_false(tmp_path: Path) -> None:
    plist_path = _plist_path(tmp_path)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as fh:
        plistlib.dump(
            {
                "Label": LAUNCH_AGENT_LABEL,
                "RunAtLoad": False,
                "ProgramArguments": [sys.executable, "-m", "iphone_sync"],
            },
            fh,
        )

    assert is_start_at_login(home_dir=tmp_path) is False


def test_source_program_arguments_use_module_flag() -> None:
    assert program_arguments() == [sys.executable, "-m", "iphone_sync"]


def test_frozen_program_arguments_use_executable_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert program_arguments() == [sys.executable]


def test_frozen_launch_agent_plist_omits_module_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    runner = _FakeRunner()

    set_start_at_login(True, home_dir=tmp_path, runner=runner)

    with _plist_path(tmp_path).open("rb") as fh:
        data = plistlib.load(fh)

    assert data["ProgramArguments"] == [sys.executable]
