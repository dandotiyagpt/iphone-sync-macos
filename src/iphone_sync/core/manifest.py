"""SQLite manifest for incremental sync state."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from iphone_sync.models.sync_record import DeviceFile, SyncRecord, SyncStatus


class Manifest:
    """Thread-safe manifest using a fresh SQLite connection per operation."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        if str(self._db_path) == ":memory:":
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        else:
            conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        pass  # connections are per-operation

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sync_records (
                        device_udid TEXT NOT NULL,
                        device_path TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        mtime REAL NOT NULL,
                        dest_path TEXT NOT NULL,
                        copied_at REAL NOT NULL,
                        status TEXT NOT NULL,
                        PRIMARY KEY (device_udid, device_path)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sync_udid ON sync_records(device_udid)"
                )
                conn.commit()
            finally:
                conn.close()

    def get_record(self, udid: str, device_path: str) -> SyncRecord | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM sync_records WHERE device_udid = ? AND device_path = ?",
                    (udid, device_path),
                ).fetchone()
            finally:
                conn.close()
        if not row:
            return None
        return self._row_to_record(row)

    def should_skip(self, udid: str, device_file: DeviceFile) -> bool:
        record = self.get_record(udid, device_file.device_path)
        if not record:
            return False
        if record.status != SyncStatus.COPIED:
            return False
        return record.size_bytes == device_file.size_bytes

    def needs_copy(self, udid: str, device_file: DeviceFile) -> bool:
        return not self.should_skip(udid, device_file)

    def upsert(
        self,
        udid: str,
        device_file: DeviceFile,
        dest_path: str,
        status: SyncStatus,
    ) -> None:
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO sync_records
                        (device_udid, device_path, size_bytes, mtime, dest_path, copied_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(device_udid, device_path) DO UPDATE SET
                        size_bytes = excluded.size_bytes,
                        mtime = excluded.mtime,
                        dest_path = excluded.dest_path,
                        copied_at = excluded.copied_at,
                        status = excluded.status
                    """,
                    (
                        udid,
                        device_file.device_path,
                        device_file.size_bytes,
                        device_file.mtime,
                        dest_path,
                        now,
                        status.value,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def mark_partial(self, udid: str, device_file: DeviceFile, dest_path: str) -> None:
        self.upsert(udid, device_file, dest_path, SyncStatus.PARTIAL)

    def mark_copied(self, udid: str, device_file: DeviceFile, dest_path: str) -> None:
        self.upsert(udid, device_file, dest_path, SyncStatus.COPIED)

    def mark_failed(self, udid: str, device_file: DeviceFile, dest_path: str) -> None:
        self.upsert(udid, device_file, dest_path, SyncStatus.FAILED)

    def count_for_device(self, udid: str) -> int:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM sync_records WHERE device_udid = ? AND status = ?",
                    (udid, SyncStatus.COPIED.value),
                ).fetchone()
            finally:
                conn.close()
        return int(row["cnt"]) if row else 0

    def total_copied_count(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM sync_records WHERE status = ?",
                    (SyncStatus.COPIED.value,),
                ).fetchone()
            finally:
                conn.close()
        return int(row["cnt"]) if row else 0

    def clear_all(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM sync_records")
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SyncRecord:
        return SyncRecord(
            device_udid=row["device_udid"],
            device_path=row["device_path"],
            size_bytes=row["size_bytes"],
            mtime=row["mtime"],
            dest_path=row["dest_path"],
            copied_at=row["copied_at"],
            status=SyncStatus(row["status"]),
        )
