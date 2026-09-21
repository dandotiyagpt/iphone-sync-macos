"""Inspect local MobileBackup2 folders (Info.plist / Manifest.plist)."""

from __future__ import annotations

import plistlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

WHATSAPP_BUNDLE_ID = "net.whatsapp.WhatsApp"
WHATSAPP_DOMAIN_MARKERS = (
    "AppDomain-net.whatsapp.WhatsApp",
    "AppDomainGroup-group.net.whatsapp.WhatsApp.shared",
)


@dataclass
class LocalBackupInfo:
    udid: str
    path: Path
    device_name: str
    product_version: str
    last_backup: datetime | None
    is_encrypted: bool
    size_bytes: int
    whatsapp_installed: bool
    whatsapp_in_manifest: bool | None  # None = could not check (encrypted Manifest.db)
    status: str

    @property
    def whatsapp_ok(self) -> bool:
        """Best-effort: encrypted + WhatsApp listed; manifest domain confirmed when readable."""
        if not self.is_encrypted:
            return False
        if not self.whatsapp_installed:
            return False
        if self.whatsapp_in_manifest is False:
            return False
        return True

    @property
    def whatsapp_status_label(self) -> str:
        if not self.is_encrypted:
            return "WhatsApp: missing — backup not encrypted"
        if not self.whatsapp_installed:
            return "WhatsApp: not installed on device at backup time"
        if self.whatsapp_in_manifest is False:
            return "WhatsApp: missing from backup payload"
        if self.whatsapp_in_manifest is True:
            return "WhatsApp: included"
        return "WhatsApp: likely included (encrypted — Manifest.db not scanned)"


def _folder_size(path: Path) -> int:
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _read_plist(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as fd:
            data = plistlib.load(fd)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _whatsapp_in_info(info: dict) -> bool:
    apps = info.get("Installed Applications") or []
    if WHATSAPP_BUNDLE_ID in apps:
        return True
    applications = info.get("Applications") or {}
    if isinstance(applications, dict) and WHATSAPP_BUNDLE_ID in applications:
        return True
    return False


def _whatsapp_in_manifest_db(device_dir: Path) -> bool | None:
    """Return True/False if Manifest.db is readable; None if missing/encrypted/unreadable."""
    db_path = device_dir / "Manifest.db"
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            # Encrypted DBs often fail here or return empty/garbage.
            rows = conn.execute(
                "SELECT domain FROM Files WHERE domain LIKE ? OR domain LIKE ? LIMIT 1",
                ("%whatsapp%", "%WhatsApp%"),
            ).fetchall()
            if rows:
                return True
            # Table readable but no WhatsApp domain
            count = conn.execute("SELECT COUNT(*) FROM Files").fetchone()
            if count and count[0] > 0:
                return False
            return None
        finally:
            conn.close()
    except Exception:
        return None


def inspect_device_backup(device_dir: Path) -> LocalBackupInfo | None:
    if not device_dir.is_dir():
        return None
    info = _read_plist(device_dir / "Info.plist")
    manifest = _read_plist(device_dir / "Manifest.plist")
    status_plist = _read_plist(device_dir / "Status.plist")

    if not info and not (device_dir / "Status.plist").exists():
        return None

    last_backup = None
    date_val = status_plist.get("Date") or info.get("Last Backup Date")
    if isinstance(date_val, datetime):
        last_backup = date_val
    elif isinstance(date_val, str):
        try:
            last_backup = datetime.fromisoformat(date_val)
        except ValueError:
            pass

    is_encrypted = bool(manifest.get("IsEncrypted", False))
    whatsapp_installed = _whatsapp_in_info(info)
    whatsapp_in_manifest = _whatsapp_in_manifest_db(device_dir)

    snapshot = status_plist.get("SnapshotState", "")
    if snapshot == "finished" or (device_dir / "Manifest.plist").exists():
        status = "ready"
    elif snapshot:
        status = str(snapshot)
    else:
        status = "incomplete"

    return LocalBackupInfo(
        udid=device_dir.name,
        path=device_dir,
        device_name=str(info.get("Display Name") or info.get("Device Name") or device_dir.name),
        product_version=str(info.get("Product Version") or ""),
        last_backup=last_backup,
        is_encrypted=is_encrypted,
        size_bytes=_folder_size(device_dir),
        whatsapp_installed=whatsapp_installed,
        whatsapp_in_manifest=whatsapp_in_manifest,
        status=status,
    )


def list_local_backups(backup_root: Path) -> list[LocalBackupInfo]:
    if not backup_root.exists():
        return []
    results: list[LocalBackupInfo] = []
    for entry in sorted(backup_root.iterdir()):
        if not entry.is_dir():
            continue
        info = inspect_device_backup(entry)
        if info:
            results.append(info)
    results.sort(key=lambda b: b.last_backup or datetime.min, reverse=True)
    return results


def format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{num_bytes} B"
