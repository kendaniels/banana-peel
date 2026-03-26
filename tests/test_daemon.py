"""Tests for PID file management and daemon lifecycle."""

import os
import signal

from banana_peel.daemon import PidFile


def test_acquire_and_release(tmp_path):
    pid_path = tmp_path / "test.pid"
    pf = PidFile(pid_path)
    pf.acquire()

    assert pid_path.exists()
    assert int(pid_path.read_text().strip()) == os.getpid()

    pf.release()
    assert not pid_path.exists()


def test_check_running_returns_none_when_no_file(tmp_path):
    pid_path = tmp_path / "nonexistent.pid"
    assert PidFile.check_running(pid_path) is None


def test_check_running_detects_stale_pid(tmp_path):
    pid_path = tmp_path / "stale.pid"
    pid_path.write_text("999999\n")  # Very unlikely to be a real PID
    # No flock held, so it should be detected as stale
    assert PidFile.check_running(pid_path) is None
    assert not pid_path.exists()  # Should have been cleaned up


def test_check_running_detects_live_process(tmp_path):
    pid_path = tmp_path / "live.pid"
    pf = PidFile(pid_path)
    pf.acquire()

    # From another "perspective", check if running
    result = PidFile.check_running(pid_path)
    assert result == os.getpid()

    pf.release()


def test_double_acquire_fails(tmp_path):
    pid_path = tmp_path / "double.pid"
    pf1 = PidFile(pid_path)
    pf1.acquire()

    pf2 = PidFile(pid_path)
    try:
        pf2.acquire()
        assert False, "Should have raised SystemExit"
    except SystemExit:
        pass

    pf1.release()


def test_is_alive_current_process():
    assert PidFile.is_alive(os.getpid()) is True


def test_is_alive_dead_process():
    assert PidFile.is_alive(999999) is False


def test_read_pid(tmp_path):
    pid_path = tmp_path / "read.pid"
    pid_path.write_text("12345\n")
    assert PidFile.read_pid(pid_path) == 12345


def test_read_pid_missing(tmp_path):
    assert PidFile.read_pid(tmp_path / "missing.pid") is None


def test_read_pid_invalid(tmp_path):
    pid_path = tmp_path / "bad.pid"
    pid_path.write_text("not-a-number\n")
    assert PidFile.read_pid(pid_path) is None
