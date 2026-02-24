from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import fcntl

MAX_AUDIT_BYTES = 2 * 1024 * 1024
ROTATED_AUDIT_FILES = 3


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def _audit_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _rotate_if_needed(path: Path, max_bytes: int | None = None, keep: int | None = None) -> None:
    max_bytes = MAX_AUDIT_BYTES if max_bytes is None else max_bytes
    keep = ROTATED_AUDIT_FILES if keep is None else keep
    if not path.exists():
        return
    if path.stat().st_size < max_bytes:
        return

    oldest = path.with_name(f"{path.name}.{keep}")
    if oldest.exists():
        oldest.unlink()

    for idx in range(keep - 1, 0, -1):
        src = path.with_name(f"{path.name}.{idx}")
        dst = path.with_name(f"{path.name}.{idx + 1}")
        if src.exists():
            src.replace(dst)

    path.replace(path.with_name(f"{path.name}.1"))


def write_audit_log(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(entry, ensure_ascii=True) + "\n").encode("utf-8")
    lock_path = path.with_name(f"{path.name}.lock")

    with _audit_lock(lock_path):
        _rotate_if_needed(path)
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
