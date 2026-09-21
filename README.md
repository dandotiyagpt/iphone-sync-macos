# iPhone Sync (macOS)

Automatically copy photos and videos from your iPhone when you plug it in via USB. On subsequent connections, only new files are copied.

## Features

- **Auto-sync on plug-in** — detects your iPhone and starts copying automatically
- **Incremental sync** — tracks what was already copied; skips existing files
- **Photos and videos** — copies HEIC, JPG, MOV, MP4, Live Photo pairs, and more from `/DCIM`
- **Organized output** — files saved to `~/Pictures/iPhone Sync/{DeviceName}_{UDID}/YYYY/MonthName/` (e.g. `2026/August/`)
- **Photo library** — built-in gallery to browse, view photos, and play videos
- **Menu bar** — runs in the background, minimizes to the menu bar
- **Open at Login** — optional auto-start via a LaunchAgent

## Prerequisites

Before using iPhone Sync, you need:

1. **usbmuxd** — ships built into macOS, no separate driver install needed
2. **iPhone unlocked** with **"Trust This Computer"** accepted when prompted
3. Photos stored **locally on the device** — iCloud-optimized-only photos won't appear over USB
4. **Xcode Command Line Tools** — required to build native wheels for some dependencies (`xcode-select --install`)

## Installation (Development)

**Recommended:** Python 3.11 or 3.12.

```bash
git clone https://github.com/dandotiyagpt/iphone-sync-macos.git
cd iphone-sync-macos
./install.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running

```bash
python -m iphone_sync
```

Or after install:

```bash
iphone-sync-macos
```

## Building an App Bundle

```bash
pip install -e ".[dev]"
./build.sh
```

The app bundle will be at `dist/iPhone Sync.app`.

## Usage

1. Launch iPhone Sync (it can start at login automatically)
2. Plug in your iPhone via USB
3. Unlock the phone and tap **Trust** if prompted
4. Sync starts automatically (or click **Sync Now**)
5. New photos and videos are copied to your destination folder
6. Open the **Library** tab to browse all synced photos and videos in a gallery

## Library (Gallery)

Click the **Library** tab (or **View → Library**) to see all synced photos and videos in one grid, newest first.

- **Click any item** to open the viewer
- **Photos** display full-size with Previous/Next navigation
- **Videos** play inline with Play/Pause (Spacebar) and arrow keys to navigate
- Click **Refresh** after a sync to update the grid

## Settings

Open **File → Settings** to configure:

| Setting | Default | Description |
|---------|---------|-------------|
| Destination folder | `~/Pictures/iPhone Sync` | Where files are saved |
| Auto-sync on plug-in | On | Start sync when iPhone is detected |
| Organize by date | On | Save files in `YYYY/MM` subfolders |
| `start_at_login` | On | Launch at login via LaunchAgent |
| Minimize to menu bar | On | Close button hides to menu bar instead of quitting |

## How Incremental Sync Works

The app maintains a SQLite database at `~/Library/Application Support/iPhoneSync/manifest.db`. Each file is tracked by:

- Device UDID
- Device path (e.g. `/DCIM/100APPLE/IMG_1234.HEIC`)
- File size

On each sync, files matching a previously copied entry with the same size are skipped. Changed or new files are copied.

Cached thumbnails live under `~/Library/Caches/iPhoneSync`.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Device not detected | Confirm the iPhone is unlocked and reconnect the USB cable |
| "Unlock and tap Trust" | Unlock iPhone, tap Trust on the prompt |
| Missing photos | Ensure photos are downloaded to device (not iCloud-only) |
| Sync is slow on first run | Normal for large libraries; subsequent syncs are fast |
| Native extension build fails | Run `xcode-select --install` to get Command Line Tools, then retry |

## License

MIT
