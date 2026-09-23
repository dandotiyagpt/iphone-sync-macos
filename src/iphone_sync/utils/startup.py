"""macOS LaunchAgent helpers for starting iPhone Sync at login.

Replaces the Windows registry (``winreg`` Run key) approach with a per-user
LaunchAgent plist under ``~/Library/LaunchAgents``. The job is an Aqua login
item — the same graphical session as the menu bar — so it can show a status
item with ``ProcessType=Interactive``. A ``Background`` job has no status
bar: the Qt app exits immediately, and launchd then leaves it stopped because
a clean exit is not restarted.

Writing the plist is enough for the agent to be picked up at the next login
even if the live ``launchctl`` calls fail, so those calls are best-effort and
never raise out of the public API.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

LAUNCH_AGENT_LABEL = "com.iphonesync.agent"
LAUNCHD_ENV_FLAG = "IPHONE_SYNC_LAUNCHD"

Runner = Callable[..., subprocess.CompletedProcess]


def _plist_path(home_dir: Path | None) -> Path:
    base = home_dir if home_dir is not None else Path.home()
    return base / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def _log_dir(home_dir: Path | None) -> Path:
    base = home_dir if home_dir is not None else Path.home()
    return base / "Library" / "Logs" / "iPhoneSync"


def _project_root() -> Path | None:
    """Repo root when running from a source checkout, else None."""
    root = Path(__file__).resolve().parents[3]
    if (root / "pyproject.toml").is_file() and (root / "src" / "iphone_sync").is_dir():
        return root
    return None


def _program_arguments() -> list[str]:
    """Launch hidden at login — the app lives in the menu bar."""
    return [sys.executable, "-m", "iphone_sync", "--background"]


def _agent_environment(project_root: Path | None) -> dict[str, str]:
    environment = {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        LAUNCHD_ENV_FLAG: "1",
        "PYTHONUNBUFFERED": "1",
    }
    if project_root is not None:
        src = project_root / "src"
        environment["PYTHONPATH"] = str(src)
    return environment


def _run_best_effort(runner: Runner, argv: list[str]) -> None:
    try:
        runner(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    except TypeError:
        try:
            runner(argv)
        except Exception:
            pass


def _bootstrap_agent(runner: Runner, uid: int, plist_path: Path) -> None:
    """Load the agent. Retry the short race after bootout unloads the old job."""
    argv = ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)]
    for attempt in range(4):
        try:
            result = runner(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except TypeError:
            try:
                runner(argv)
            except Exception:
                pass
            return
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return
        if getattr(result, "returncode", 0) == 0:
            return
        err = str(getattr(result, "stderr", "") or "")
        # Already resident in this session. The on-disk plist applies next login.
        if "already" in err.lower():
            return
        if attempt < 3:
            time.sleep(0.35)


def _service_target(uid: int) -> str:
    return f"gui/{uid}/{LAUNCH_AGENT_LABEL}"


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
    target = _service_target(uid)

    if enabled:
        log_dir = _log_dir(home_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        project_root = _project_root()
        payload: dict[str, object] = {
            "Label": LAUNCH_AGENT_LABEL,
            "RunAtLoad": True,
            # Restart after a crash or a login race (non-zero exit). A clean
            # Quit from the menu bar exits 0 and is not relaunched.
            "KeepAlive": {"SuccessfulExit": False},
            # Interactive keeps USB backups off the daemon throttle. Background
            # is the wrong class: that spawn has no menu bar, so the app exits
            # and launchd does not bring it back.
            "ProcessType": "Interactive",
            # Aqua is the graphical login session — the one that owns the menu bar.
            "LimitLoadToSessionType": "Aqua",
            "AssociatedBundleIdentifiers": ["com.iphonesync.launcher"],
            "ProgramArguments": _program_arguments(),
            "EnvironmentVariables": _agent_environment(project_root),
            "StandardOutPath": str(log_dir / "launchd.log"),
            "StandardErrorPath": str(log_dir / "launchd.err.log"),
        }
        if project_root is not None:
            payload["WorkingDirectory"] = str(project_root)
        with plist_path.open("wb") as fh:
            plistlib.dump(payload, fh)
        # Enable before bootstrap. A disabled service refuses to load, which
        # is how macOS drops login items the user (or a previous bootout)
        # turned off.
        _run_best_effort(active_runner, ["launchctl", "enable", target])
        # Reloading from inside the launchd job would kill this process and
        # start another copy. The on-disk plist is what the next login reads.
        if os.environ.get(LAUNCHD_ENV_FLAG) != "1":
            _run_best_effort(active_runner, ["launchctl", "bootout", target])
        _bootstrap_agent(active_runner, uid, plist_path)
    else:
        _run_best_effort(active_runner, ["launchctl", "bootout", target])
        _run_best_effort(active_runner, ["launchctl", "disable", target])
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
