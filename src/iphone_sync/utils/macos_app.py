"""AppKit glue for running as a menu bar agent.

Qt has no API for the macOS activation policy, so the Dock-icon behavior and
foreground activation go through AppKit. Every call is best-effort: if AppKit
is unavailable the app still runs, just with ordinary Dock-app behavior.
"""

from __future__ import annotations

try:  # pragma: no cover - import availability differs per environment
    from AppKit import (
        NSApp,
        NSApplication,
        NSApplicationActivationPolicyAccessory,
        NSApplicationActivationPolicyRegular,
    )

    APPKIT_AVAILABLE = True
except Exception:  # pragma: no cover - headless / non-macOS fallback
    APPKIT_AVAILABLE = False


def _shared_app():
    """Qt creates the process-wide NSApplication; ``NSApp()`` can still be nil."""
    try:
        app = NSApp()
    except Exception:
        app = None
    if app is not None:
        return app
    try:
        return NSApplication.sharedApplication()
    except Exception:
        return None


def set_menu_bar_only(enabled: bool) -> bool:
    """Hide (or restore) the Dock icon. Returns True if the policy was set.

    Python.app has no ``LSUIElement``, so a ``python -m`` launch shows a Dock
    icon unless this policy is applied. Qt also resets it when a window is
    created, so callers should apply it again after the window exists.
    """
    if not APPKIT_AVAILABLE:
        return False
    policy = (
        NSApplicationActivationPolicyAccessory
        if enabled
        else NSApplicationActivationPolicyRegular
    )
    try:
        app = _shared_app()
        if app is None:
            return False
        app.setActivationPolicy_(policy)
        return True
    except Exception:
        return False


def activate_app() -> bool:
    """Bring the app forward — accessory apps are not activated automatically."""
    if not APPKIT_AVAILABLE:
        return False
    try:
        app = _shared_app()
        if app is None:
            return False
        app.activateIgnoringOtherApps_(True)
        return True
    except Exception:
        return False
