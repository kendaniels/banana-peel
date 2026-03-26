"""macOS notifications via osascript. No-op on other platforms."""

from __future__ import annotations

import platform
import subprocess


def notify(title: str, message: str, sound: str = "default") -> None:
    """Send a macOS notification. No-op on non-macOS platforms."""
    if platform.system() != "Darwin":
        return

    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')

    script = (
        f'display notification "{safe_message}"'
        f' with title "{safe_title}"'
        f' sound name "{sound}"'
    )

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # Silently fail — notifications are best-effort
