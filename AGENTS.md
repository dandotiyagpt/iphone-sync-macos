# iPhone Sync (macOS) — Agent Guide

This is the canonical instructions file for this project, read by every AI
coding assistant that works in it. `CLAUDE.md`, `GEMINI.md`, and
`.cursorrules` are symlinks to this file — edit **this** file, not those, so
Claude Code, Gemini CLI, and Cursor never drift out of sync with each other.
See `/Users/jyotithapak/Hemant/AGENTS.md` for the cross-project multi-agent
coordination protocol (claiming work, worktrees for parallel edits, handoff
notes) — read that too before starting non-trivial work, and check this
project's `.ai/STATUS.md` for what's currently in flight.

## What this is

A local, offline USB sync bridge between iOS and macOS: plug in an iPhone and
it auto-backs-up Camera Roll photos/videos (via AFC), Files-app documents, and
optionally full encrypted MobileBackup2 device backups — no iCloud, no
network calls. Ships as a PySide6/Qt6 desktop app with a menu-bar daemon and a
standalone media gallery viewer. Full feature/architecture writeup is in
`README.md` (including a mermaid diagram of the USB→AFC/MB2→SyncEngine→
Manifest→Storage→UI dataflow) — read that for the "why", this file is for the
"how to work on it."

- Repo: `github.com/dandotiyagpt/iphone-sync-macos`, single branch `main` in
  use today (no other branches as of 2026-09-22).
- Python ≥3.11, deps in `pyproject.toml` (PySide6, pymobiledevice3, Pillow/
  pillow-heif, PyAV, pyobjc). `.venv/` already exists at repo root (created by
  `install.sh`) — activate it rather than creating a second one.

## Commands

```bash
./install.sh                 # creates .venv, installs core + dev deps, shortcuts
python -m iphone_sync         # launch main sync daemon + dashboard
iphone-sync-macos             # same, via installed console-script entry point
iphone-gallery-macos           # launch gallery viewer directly
./build.sh                    # package standalone dist/iPhone Sync.app

pytest                        # full test suite (tests/, pythonpath=src)
pytest -m unit                # fast unit tests only
pytest --cov=iphone_sync tests/   # with coverage
```

Double-clickable alternatives in Finder: `run-sync.command`,
`run-gallery.command`, `Launch iPhone Sync.command`.

## Architecture (source layout)

- `src/iphone_sync/core/` — device I/O and sync logic: `afc_client.py`
  (AFC/DCIM access), `sync_engine.py` (incremental photo/video sync),
  `files_backup_engine.py` (Files-app media folders only; no per-app
  sandboxes), `whatsapp_backup_engine.py` + `device_backup_info.py`
  (encrypted MobileBackup2 snapshot stored and judged as a WhatsApp backup),
  `device_watcher.py` (usbmuxd hotplug events), `manifest.py` (SQLite
  incremental-sync index).
- `src/iphone_sync/ui/` — PySide6 UI: `main_window.py` (dashboard),
  `settings_dialog.py`, `backup_dialogs.py`, `theme.py`, `tray_popover.py`,
  `widgets/progress.py`; `gallery/` subpackage holds the media gallery
  (`gallery_widget.py`, `thumbnail_cache.py`/`thumbnail_loader.py`,
  `image_loader.py`, `preview_pane.py`, `viewer_dialog.py`, `media_scanner.py`,
  `device_discovery.py`).
- `src/iphone_sync/models/sync_record.py` — sync record data model.
  `src/iphone_sync/utils/` — `paths.py` (storage locations, extension sets),
  `atomic_copy.py`, `exif.py`, `prerequisites.py` (macOS/Xcode CLT checks),
  `startup.py` (LaunchAgent install/removal), `macos_app.py` (Dock policy),
  `single_instance.py`, `tray_icon.py`, `usbmux_helpers.py`.
- `app.py` / `gallery_app.py` — the two entry points (dashboard app vs.
  standalone gallery), wired to the `[project.scripts]` in `pyproject.toml`.

## Current state

The app is a menu-bar agent: login starts it with `--background`, closing the
window leaves it running, and Quit is the only way out. Photos, Files-app
media folders, and the WhatsApp MobileBackup2 snapshot are three separate
destinations. Themes live in `ui/theme.py`. `iPhone Sync.app/` is a local
build product and is gitignored.

Before editing, check `.ai/STATUS.md`. If another tool has an in-progress
claim on the same files, use a `git worktree` (see the workspace `AGENTS.md`)
instead of this working tree. `ui/main_window.py` and `ui/gallery/` are the
files most likely to conflict.

## Testing notes

- `pytest.ini_options` sets `pythonpath = ["src"]`, so tests import
  `iphone_sync` directly without an editable install.
- Tests needing real hardware (USB/usbmuxd/device pairing) aren't part of
  this suite by nature — check `conftest.py` and existing tests for the
  mocking pattern used for `usbmuxd`/AFC before adding new device-dependent
  tests.
