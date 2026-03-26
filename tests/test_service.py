"""Tests for service template generation."""

from banana_peel.service import _generate_plist, _generate_systemd_unit, _build_command_args


def test_generate_plist_contains_key_fields():
    plist = _generate_plist(["/usr/bin/banana-peel", "watch", "--daemon-mode"])
    assert "com.banana-peel.watcher" in plist
    assert "<string>/usr/bin/banana-peel</string>" in plist
    assert "<string>watch</string>" in plist
    assert "<string>--daemon-mode</string>" in plist
    assert "RunAtLoad" in plist
    assert "KeepAlive" in plist
    assert "SuccessfulExit" in plist
    assert "PYTHONUNBUFFERED" in plist
    assert "ThrottleInterval" in plist


def test_generate_systemd_unit_contains_key_fields():
    unit = _generate_systemd_unit(["/usr/bin/banana-peel", "watch", "--daemon-mode"])
    assert "ExecStart=/usr/bin/banana-peel watch --daemon-mode" in unit
    assert "Restart=on-failure" in unit
    assert "RestartSec=5s" in unit
    assert "PYTHONUNBUFFERED=1" in unit
    assert "WantedBy=default.target" in unit
    assert "Type=exec" in unit


def test_build_command_args_binary():
    args = _build_command_args("/usr/bin/banana-peel")
    assert args == ["/usr/bin/banana-peel", "watch", "--daemon-mode"]


def test_build_command_args_with_config():
    args = _build_command_args("/usr/bin/banana-peel", "/home/user/config.toml")
    assert args == ["/usr/bin/banana-peel", "watch", "--daemon-mode", "--config", "/home/user/config.toml"]


def test_build_command_args_python_module():
    args = _build_command_args("/usr/bin/python3 -m banana_peel")
    assert args == ["/usr/bin/python3", "-m", "banana_peel", "watch", "--daemon-mode"]
