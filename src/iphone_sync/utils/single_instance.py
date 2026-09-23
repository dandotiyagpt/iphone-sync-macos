"""Single-instance lock so only one background agent runs at a time.

The app is designed to stay resident in the menu bar and is also started by a
LaunchAgent at login, so a user double-clicking the app afterwards would
otherwise end up with two device watchers polling usbmuxd. An advisory
``flock`` on a lock file keeps exactly one process alive; the lock is released
automatically by the OS when the holder exits or crashes.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import IO

_LOCK_FILENAME = "iphone-sync.lock"


class InstanceLock:
    """Advisory file lock; keep the returned object alive for the process."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._handle: IO[str] | None = None

    def acquire(self) -> bool:
        """Try to take the lock. False means another instance already holds it."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.lock_path, "a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._handle.close()
            self._handle = None


def lock_path(app_data_dir: Path) -> Path:
    return app_data_dir / _LOCK_FILENAME
