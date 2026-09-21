"""Atomic file copy with .partial temp files."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def atomic_write(
    dest: Path,
    data: bytes,
    expected_size: int,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    partial.write_bytes(data)
    if partial.stat().st_size != expected_size:
        partial.unlink(missing_ok=True)
        raise IOError(f"Size mismatch: expected {expected_size}, got {partial.stat().st_size}")
    partial.replace(dest)


def stream_to_file(
    dest: Path,
    read_chunk: Callable[[], bytes | None],
    expected_size: int,
    on_progress: Callable[[int], None] | None = None,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    transferred = 0

    with partial.open("wb") as out:
        while True:
            chunk = read_chunk()
            if not chunk:
                break
            out.write(chunk)
            transferred += len(chunk)
            if on_progress:
                on_progress(transferred)

    if partial.stat().st_size != expected_size:
        partial.unlink(missing_ok=True)
        raise IOError(f"Size mismatch: expected {expected_size}, got {partial.stat().st_size}")

    partial.replace(dest)
