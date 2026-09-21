"""macOS LaunchAgent helpers for starting iPhone Sync at login.

Replaces the Windows registry (``winreg`` Run key) approach with a per-user
LaunchAgent plist under ``~/Library/LaunchAgents``. Writing the plist is
enough for the agent to be picked up at the next login even if the live
``launchctl bootstrap``/``bootout`` call fails or macOS refuses it for the
current session (e.g. no active GUI session yet) — so those calls are always
best-effort and never allowed to raise out of the public API.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Callable

LAUNCH_AGENT_LABEL = "com.iphonesync.agent"

Runner = Callable[..., subprocess.CompletedProcess]


def _plist_path(home_dir: Path | None) -> Path:
    base = home_dir if home_dir is not None else Path.home()
    return base / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def program_arguments() -> list[str]:
    """Launch argv for the LaunchAgent.

    Frozen py2app bundles already point ``sys.executable`` at the app binary.
    Source installs still need ``python -m iphone_sync``.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "iphone_sync"]


def _run_best_effort(runner: Runner, argv: list[str]) -> None:
    try:
        runner(argv)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass


def set_start_at_login(
    enabled: bool,
    *,
    home_dir: Path | None = None,
    runner: Runner | None = None,
) -> None:
    """Enable or disable launching iPhone Sync at login via a LaunchAgent."""
    active_runner: Runner = runner if runner is not None else subprocess.run
    plist_path = _plist_path(home_dir)
    uid = os.getuid() if hasattr(os, "getuid") else 0

    if enabled:
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        with plist_path.open("wb") as fh:
            plistlib.dump(
                {
                    "Label": LAUNCH_AGENT_LABEL,
                    "RunAtLoad": True,
                    "ProgramArguments": program_arguments(),
                },
                fh,
            )
        _run_best_effort(
            active_runner,
            ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
        )
    else:
        _run_best_effort(
            active_runner,
            ["launchctl", "bootout", f"gui/{uid}/{LAUNCH_AGENT_LABEL}"],
        )
        try:
            plist_path.unlink()
        except FileNotFoundError:
            pass


def is_start_at_login(*, home_dir: Path | None = None) -> bool:
    """Return True if the LaunchAgent plist exists with RunAtLoad set."""
    plist_path = _plist_path(home_dir)
    if not plist_path.is_file():
        return False
    try:
        with plist_path.open("rb") as fh:
            data = plistlib.load(fh)
    except (OSError, ValueError):
        return False
    return bool(data.get("RunAtLoad", False))
