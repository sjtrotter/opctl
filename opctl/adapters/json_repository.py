import contextlib
import json
import os
import tempfile
from opctl.domain.interfaces import IPolicyRepository

try:
    import fcntl          # POSIX
    _WINDOWS = False
except ImportError:       # Windows
    import msvcrt
    _WINDOWS = True


class SessionLockError(RuntimeError):
    """The session file is locked by another opctl process."""


class JsonPolicyRepository(IPolicyRepository):
    """Concrete repository over a local JSON file.

    Writes are atomic (temp file + ``os.replace``) so a write can never corrupt the
    file or leave it half-written, and are serialized by an advisory lock on
    ``<file>.lock`` (fail-fast ``SessionLockError`` when another opctl process is
    mid-write). Reads are lock-free: an atomic rename means a reader always sees a
    complete file — the old or the new one.

    Scope note: the lock spans a single physical write, not a full
    load-modify-save, so two processes concurrently *editing* the staged session can
    still lose an update (last-writer-wins). That is acceptable for a single-operator
    tool; cross-transaction exclusion would need the lock held across load+save.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load_state(self) -> dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}  # corrupt or missing -> clean state (self-healed by from_dict)
        return {}

    def save_state(self, state: dict) -> None:
        with self._lock():
            self._atomic_write(json.dumps(state, indent=2))

    # --- locking + atomic write -----------------------------------------

    @contextlib.contextmanager
    def _lock(self):
        f = open(self.file_path + ".lock", "a+")
        try:
            self._acquire(f)
            yield
        finally:
            try:
                self._release(f)
            finally:
                f.close()

    @staticmethod
    def _acquire(f) -> None:
        try:
            if _WINDOWS:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SessionLockError(
                "session is locked by another opctl process — try again in a moment")

    @staticmethod
    def _release(f) -> None:
        try:
            if _WINDOWS:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass

    def _atomic_write(self, content: str) -> None:
        directory = os.path.dirname(self.file_path) or "."
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".session-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.file_path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
