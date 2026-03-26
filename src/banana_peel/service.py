"""OS-native service installation for launchd (macOS) and systemd (Linux)."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from banana_peel.daemon import CONFIG_DIR, LOG_PATH

LAUNCHD_LABEL = "com.banana-peel.watcher"
LAUNCHD_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
SYSTEMD_UNIT = Path.home() / ".config" / "systemd" / "user" / "banana-peel.service"


def detect_platform() -> str:
    """Return 'macos', 'linux', or raise for unsupported."""
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Linux":
        return "linux"
    raise RuntimeError(f"Service installation not supported on {system}")


def _resolve_binary() -> str:
    """Find the absolute path to the banana-peel binary."""
    which = shutil.which("banana-peel")
    if which:
        return which
    # Fallback: use python -m
    return f"{sys.executable} -m banana_peel"


def _build_command_args(binary: str, config_path: str | None = None) -> list[str]:
    """Build the command arguments for the service."""
    if " -m " in binary:
        parts = binary.split()
        args = parts + ["watch", "--daemon-mode"]
    else:
        args = [binary, "watch", "--daemon-mode"]
    if config_path:
        args.extend(["--config", config_path])
    return args


def _generate_plist(args: list[str]) -> str:
    """Generate launchd plist XML."""
    log_path = str(LOG_PATH)
    program_args = "\n".join(f"        <string>{a}</string>" for a in args)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCHD_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
{program_args}
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>{log_path}</string>

    <key>StandardErrorPath</key>
    <string>{log_path}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>

    <key>ProcessType</key>
    <string>Background</string>

    <key>ThrottleInterval</key>
    <integer>5</integer>
</dict>
</plist>
"""


def _generate_systemd_unit(args: list[str]) -> str:
    """Generate systemd user unit file."""
    exec_start = " ".join(args)
    log_path = str(LOG_PATH)

    return f"""[Unit]
Description=Banana Peel file watcher
After=default.target

[Service]
Type=exec
ExecStart={exec_start}
Restart=on-failure
RestartSec=5s
Environment=PYTHONUNBUFFERED=1
StandardOutput=append:{log_path}
StandardError=append:{log_path}

[Install]
WantedBy=default.target
"""


def install_service(config_path: str | None = None) -> str:
    """Install and start the OS-native service. Returns status message."""
    plat = detect_platform()
    binary = _resolve_binary()
    args = _build_command_args(binary, config_path)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if plat == "macos":
        LAUNCHD_PLIST.parent.mkdir(parents=True, exist_ok=True)
        LAUNCHD_PLIST.write_text(_generate_plist(args))

        # Unload first if already loaded (ignore errors)
        subprocess.run(
            ["launchctl", "unload", str(LAUNCHD_PLIST)],
            capture_output=True,
        )
        subprocess.run(
            ["launchctl", "load", str(LAUNCHD_PLIST)],
            check=True,
            capture_output=True,
        )
        return f"Installed and started launchd service.\nPlist: {LAUNCHD_PLIST}\nLogs: {LOG_PATH}"

    else:  # linux
        SYSTEMD_UNIT.parent.mkdir(parents=True, exist_ok=True)
        SYSTEMD_UNIT.write_text(_generate_systemd_unit(args))

        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", "banana-peel.service"],
            check=True,
            capture_output=True,
        )
        return f"Installed and started systemd user service.\nUnit: {SYSTEMD_UNIT}\nLogs: {LOG_PATH}"


def uninstall_service() -> str:
    """Stop and remove the OS-native service. Returns status message."""
    plat = detect_platform()

    if plat == "macos":
        if LAUNCHD_PLIST.exists():
            subprocess.run(
                ["launchctl", "unload", str(LAUNCHD_PLIST)],
                capture_output=True,
            )
            LAUNCHD_PLIST.unlink()
            return f"Uninstalled launchd service. Removed {LAUNCHD_PLIST}"
        return "No launchd service found."

    else:  # linux
        if SYSTEMD_UNIT.exists():
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", "banana-peel.service"],
                capture_output=True,
            )
            SYSTEMD_UNIT.unlink()
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
            )
            return f"Uninstalled systemd service. Removed {SYSTEMD_UNIT}"
        return "No systemd service found."
