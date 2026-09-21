"""Data models for device files and sync manifest entries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SyncStatus(str, Enum):
    COPIED = "copied"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class DeviceFile:
    device_path: str
    size_bytes: int
    mtime: float
    filename: str

    @property
    def extension(self) -> str:
        return self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""


@dataclass
class SyncRecord:
    device_udid: str
    device_path: str
    size_bytes: int
    mtime: float
    dest_path: str
    copied_at: float
    status: SyncStatus
