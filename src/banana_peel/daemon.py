"""PID file management with flock-based locking for reliable daemon lifecycle."""

from __future__ import annotations

import atexit
import errno
import fcntl
import os
import signal
import subprocess
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "banana-peel"
PID_PATH = CONFIG_DIR / "banana-peel.pid"
LOG_PATH = CONFIG_DIR / "banana-peel.log"


class PidFile:
    """Manage a PID file with flock-based locking.

    The flock is the source of truth for whether a process is alive,
    not the PID value. This eliminates PID-reuse race conditions.
    """

    def __init__(self, path: Path = PID_PATH):
        self.path = path
        self._fd: int | None = None

    def acquire(self) -> None:
        """Write PID file and hold an exclusive lock for the process lifetime."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o644)

        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._fd)
            self._fd = None
            raise SystemExit(
                f"Another instance is already running (lock held on {self.path})"
            )

        os.ftruncate(self._fd, 0)
        os.lseek(self._fd, 0, os.SEEK_SET)
        os.write(self._fd, f"{os.getpid()}\n".encode())
        os.fsync(self._fd)

        atexit.register(self.release)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def release(self) -> None:
        """Remove PID file and release lock."""
        if self._fd is not None:
            try:
                self.path.unlink(missing_ok=True)
            finally:
                os.close(self._fd)
                self._fd = None

    def _signal_handler(self, signum, frame):
        self.release()
        sys.exit(128 + signum)

    @staticmethod
    def read_pid(path: Path = PID_PATH) -> int | None:
        """Read PID from file, returning None if missing or invalid."""
        try:
            text = path.read_text().strip()
            return int(text) if text else None
        except (FileNotFoundError, ValueError):
            return None

    @staticmethod
    def is_alive(pid: int) -> bool:
        """Check if a process is running via signal 0."""
        try:
            os.kill(pid, 0)
            return True
        except OSError as e:
            if e.errno == errno.ESRCH:
                return False
            if e.errno == errno.EPERM:
                return True
            raise

    @classmethod
    def check_running(cls, path: Path = PID_PATH) -> int | None:
        """Return PID if another instance is running, None otherwise.

        Uses flock as the primary check, signal 0 as fallback.
        """
        if not path.exists():
            return None

        try:
            fd = os.open(str(path), os.O_RDONLY)
        except FileNotFoundError:
            return None

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Lock acquired → stale PID file
            path.unlink(missing_ok=True)
            return None
        except OSError:
            # Lock held → process is alive
            return cls.read_pid(path)
        finally:
            os.close(fd)

    @staticmethod
    def stop(path: Path = PID_PATH) -> bool:
        """Send SIGTERM to the running instance. Returns True if stopped."""
        pid = PidFile.check_running(path)
        if pid is None:
            return False

        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError:
            return False


def start_background(extra_args: list[str] | None = None) -> int:
    """Launch banana-peel watcher as a detached background process.

    Returns the PID of the child process.
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "banana_peel", "watch", "--daemon-mode"]
    if extra_args:
        cmd.extend(extra_args)

    log_file = open(LOG_PATH, "a")
    proc = subprocess.Popen(
        cmd,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=log_file,
        close_fds=True,
    )
    log_file.close()

    # Write PID file for the child (the child will also acquire its own flock)
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(f"{proc.pid}\n")

    return proc.pid
