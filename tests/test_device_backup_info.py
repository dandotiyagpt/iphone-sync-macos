"""Tests for device backup Info.plist / Manifest helpers."""

from __future__ import annotations

import plistlib
import sqlite3
from datetime import datetime
from pathlib import Path

from iphone_sync.core.device_backup_info import (
    WHATSAPP_BUNDLE_ID,
    format_size,
    inspect_device_backup,
    list_local_backups,
)


def _write_plist(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fd:
        plistlib.dump(data, fd)


def test_format_size():
    assert format_size(500) == "500 B"
    assert "KB" in format_size(2048)
    assert "MB" in format_size(5 * 1024 * 1024)


def test_inspect_encrypted_backup_with_whatsapp(tmp_path: Path):
    device = tmp_path / "UDID123"
    _write_plist(
        device / "Info.plist",
        {
            "Display Name": "Test iPhone",
            "Product Version": "18.0",
            "Installed Applications": [WHATSAPP_BUNDLE_ID, "com.apple.MobileSMS"],
            "Applications": {WHATSAPP_BUNDLE_ID: {}},
        },
    )
    _write_plist(device / "Manifest.plist", {"IsEncrypted": True})
    _write_plist(
        device / "Status.plist",
        {
            "Date": datetime(2026, 8, 30, 12, 0, 0),
            "SnapshotState": "finished",
            "IsFullBackup": True,
        },
    )
    (device / "dummy.bin").write_bytes(b"x" * 100)

    info = inspect_device_backup(device)
    assert info is not None
    assert info.is_encrypted is True
    assert info.whatsapp_installed is True
    assert info.device_name == "Test iPhone"
    assert "included" in info.whatsapp_status_label.lower() or "likely" in info.whatsapp_status_label.lower()
    assert info.whatsapp_ok is True


def test_unencrypted_backup_whatsapp_not_ok(tmp_path: Path):
    device = tmp_path / "UDID456"
    _write_plist(
        device / "Info.plist",
        {
            "Display Name": "Phone",
            "Installed Applications": [WHATSAPP_BUNDLE_ID],
        },
    )
    _write_plist(device / "Manifest.plist", {"IsEncrypted": False})
    _write_plist(device / "Status.plist", {"SnapshotState": "finished"})

    info = inspect_device_backup(device)
    assert info is not None
    assert info.whatsapp_ok is False
    assert "not encrypted" in info.whatsapp_status_label.lower()


def test_manifest_db_detects_whatsapp_domain(tmp_path: Path):
    device = tmp_path / "UDID789"
    _write_plist(
        device / "Info.plist",
        {"Display Name": "Phone", "Installed Applications": [WHATSAPP_BUNDLE_ID]},
    )
    _write_plist(device / "Manifest.plist", {"IsEncrypted": True})
    _write_plist(device / "Status.plist", {"SnapshotState": "finished"})

    db = device / "Manifest.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE Files (fileID TEXT, domain TEXT, relativePath TEXT)")
    conn.execute(
        "INSERT INTO Files VALUES (?, ?, ?)",
        ("abc", "AppDomain-net.whatsapp.WhatsApp", "Documents/ChatStorage.sqlite"),
    )
    conn.commit()
    conn.close()

    info = inspect_device_backup(device)
    assert info is not None
    assert info.whatsapp_in_manifest is True
    assert info.whatsapp_ok is True
    assert "WhatsApp: included" == info.whatsapp_status_label


def test_list_local_backups(tmp_path: Path):
    a = tmp_path / "AAA"
    b = tmp_path / "BBB"
    for folder, name, day in ((a, "A", 1), (b, "B", 2)):
        _write_plist(
            folder / "Info.plist",
            {"Display Name": name, "Installed Applications": []},
        )
        _write_plist(folder / "Manifest.plist", {"IsEncrypted": True})
        _write_plist(
            folder / "Status.plist",
            {
                "Date": datetime(2026, 8, day, 10, 0, 0),
                "SnapshotState": "finished",
            },
        )

    backups = list_local_backups(tmp_path)
    assert len(backups) == 2
    assert backups[0].device_name == "B"  # newest first
