"""Windows OS file lock for the long-running scheduler only."""

import errno
import msvcrt
from contextlib import contextmanager
from pathlib import Path

from app.db.database import DATA_DIR


LOCK_PATH = DATA_DIR / "scheduler.lock"


@contextmanager
def scheduler_instance_lock(path: Path = LOCK_PATH):
    """Yield False if held elsewhere; a dead process releases the OS lock automatically.

    Keep the file after release so a second process cannot race a file deletion.
    Its contents never include a PID, configuration value, or secret.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno != errno.EACCES:
                raise
            yield False
            return
        try:
            yield True
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()
