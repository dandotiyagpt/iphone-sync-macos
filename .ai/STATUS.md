# iPhone Sync (macOS) — Task Board

Shared handoff log for Claude Code, Gemini CLI, and Cursor. Read before
starting work; update when you start, pause, or finish. See `../AGENTS.md`
(this project) and `/Users/jyotithapak/Hemant/AGENTS.md` (workspace) for the
full protocol.

Format:
```
- [YYYY-MM-DD] <tool> — <task>
  status: in-progress | blocked | done
  area: <files/dirs>
  worktree/branch: <branch name, or "main working tree">
  notes: <handoff detail — what's left, gotchas, why an approach was chosen>
```

## Log

- [2026-09-23] Cursor — Review the working tree and open a pull request
  status: done
  area: app, ui, core backup engines, tests, AGENTS.md, .gitignore
  worktree/branch: menu-bar-agent
  notes: pytest 136 passed. Shipped the menu-bar agent, themes, gallery, and WhatsApp backup rename. Left `iPhone Sync.app/` untracked and gitignored. Restore still calls MobileBackup2 with settings on and apps not skipped; success is judged on WhatsApp presence. README diagram still labels the engine DeviceBackupEngine.

- [2026-09-23] Cursor — Keep iPhone Sync in the menu bar and start it at login
  status: done
  area: src/iphone_sync/utils/startup.py, src/iphone_sync/utils/macos_app.py, src/iphone_sync/app.py, src/iphone_sync/ui/main_window.py, src/iphone_sync/ui/settings_dialog.py, iPhone Sync.app/Contents/MacOS/launcher, tests/test_startup_launchagent.py
  worktree/branch: main working tree
  notes: LaunchAgent was ProcessType Background, so launchd spawned it as a daemon. It exited 0 (no menu bar) and KeepAlive does not restart a clean exit, so nothing came back after boot. Plist is now an Aqua Interactive login agent (RunAtLoad, KeepAlive on crash only). Reloaded in this session: pid under gui/501, --background, Dock hidden. Quit from the menu bar still stays quit. A menu-bar app cannot start before the user logs in; login is the boot-time start.

- [2026-09-23] Gemini 3.8 Flash — Compact & minimal TrayPopover widget (iStat style)
  status: done
  area: src/iphone_sync/ui/tray_popover.py, src/iphone_sync/ui/main_window.py, tests/test_tray_popover.py
  worktree/branch: main working tree
  notes: Implemented lightweight frameless TrayPopover anchored directly below macOS menu bar icon. Displays live device telemetry, battery pill with charging indicator, segmented StorageBarWidget (Photos, Files, WhatsApp, Free), sync progress bar, and quick action buttons (Sync Now, Gallery, Settings, Open Dashboard). Wired into MainWindow tray activation and tested with 135 passing tests.

- [2026-09-22] Gemini 3.8 Flash — Multi-theme palette engine & settings integration
  status: done
  area: src/iphone_sync/ui/theme.py, src/iphone_sync/config.py, src/iphone_sync/ui/settings_dialog.py, src/iphone_sync/ui/main_window.py, src/iphone_sync/app.py, src/iphone_sync/gallery_app.py, tests/test_theme.py, tests/test_config_paths_macos.py
  worktree/branch: main working tree
  notes: Implemented 4 selectable themes matching the generated UI mockups (Dark Obsidian, Midnight Navy, Cupertino Light, Titanium Amber). Added theme dropdown to SettingsDialog, live stylesheet reload on save, Settings persistence, and test suite verification (131 tests passing).

- [2026-09-22] Claude Sonnet 5 — set up multi-agent environment (AGENTS.md +
  CLAUDE.md/GEMINI.md/.cursorrules symlinks + this STATUS.md) for the whole
  `~/Hemant` workspace.
  status: done
  area: AGENTS.md, CLAUDE.md, GEMINI.md, .cursorrules, .cursor/rules/, .ai/
  worktree/branch: main working tree
  notes: No code changes. Also surfaced (didn't touch) a pre-existing large
  uncommitted UI/gallery diff already sitting on `main` — see "Current state"
  section in `../AGENTS.md` for details (new `ui/theme.py` +
  `ui/gallery/device_discovery.py`, big rewrites in `main_window.py`,
  `gallery_widget.py`, `preview_pane.py`, `thumbnail_loader.py`,
  `backup_dialogs.py`, `widgets/progress.py`, plus two new untracked test
  files). That work has no branch/commit/stash backing it — whoever picks it
  up next should add a claim entry above before editing those files, and
  probably get it committed or branched first if working on anything else in
  `ui/` in parallel.
