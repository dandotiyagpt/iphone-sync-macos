"""QApplication bootstrap — menu bar resident agent."""

from __future__ import annotations

import argparse
import sys
import time

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from iphone_sync.config import Settings
from iphone_sync.ui.main_window import MainWindow
from iphone_sync.ui.theme import get_theme_stylesheet
from iphone_sync.utils.macos_app import set_menu_bar_only
from iphone_sync.utils.single_instance import InstanceLock, lock_path
from iphone_sync.utils.startup import set_start_at_login


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="iphone-sync-macos", add_help=True)
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start hidden in the menu bar without opening the window (used at login).",
    )
    args, _unknown = parser.parse_known_args(argv)
    return args


def _wait_for_menu_bar(*, background: bool) -> bool:
    """Menu bar apps started at login can beat the status bar by a few seconds."""
    if QSystemTrayIcon.isSystemTrayAvailable():
        return True
    if not background:
        return False
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        time.sleep(0.25)
        QApplication.processEvents()
        if QSystemTrayIcon.isSystemTrayAvailable():
            return True
    return False


def main() -> None:
    args = _parse_args(sys.argv[1:])

    app = QApplication(sys.argv)
    app.setApplicationName("iPhone Sync")
    app.setOrganizationName("iPhoneSync")
    # The menu bar item — not a window — owns the app lifetime.
    app.setQuitOnLastWindowClosed(False)

    settings = Settings.load()
    app.setStyleSheet(get_theme_stylesheet(settings.theme))

    instance_lock = InstanceLock(lock_path(Settings.app_data_dir()))
    if not instance_lock.acquire():
        # Already resident in the menu bar; a second watcher would double-poll.
        # A login/relaunch duplicate exits silently — only a user-initiated
        # launch gets a dialog, since nobody is there to dismiss the other one.
        if not args.background:
            QMessageBox.information(
                None,
                "iPhone Sync",
                "iPhone Sync is already running — look for the icon in your menu bar.",
            )
        return
    app.aboutToQuit.connect(instance_lock.release)

    if not _wait_for_menu_bar(background=args.background):
        # A login start must exit non-zero. KeepAlive ignores a clean exit,
        # so returning here would leave the Mac with no menu-bar agent.
        if args.background:
            sys.exit(1)
        QMessageBox.critical(
            None,
            "iPhone Sync",
            "The macOS menu bar is unavailable, so iPhone Sync cannot run in the background.",
        )
        return

    set_menu_bar_only(settings.menu_bar_only)

    # Keep the login item in step with the saved preference.
    set_start_at_login(settings.start_at_login)

    window = MainWindow(settings)
    # Qt resets the Dock policy while creating the window.
    set_menu_bar_only(settings.menu_bar_only)
    if args.background and settings.run_in_background:
        window.start_hidden()
    else:
        window.show_foreground()

    sys.exit(app.exec())
