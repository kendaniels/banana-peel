---
date: 2026-03-23
topic: daemon-mode
---

# Background / Daemon Mode for banana-peel

## Problem Frame

Currently `banana-peel watch` blocks the terminal and requires the user to keep a shell open. Users want a set-and-forget experience where banana-peel runs silently in the background, starts on login, and processes images without any terminal interaction.

## Requirements

- R1. `banana-peel watch --background` forks the process, detaches from the terminal, writes a PID file to `~/.config/banana-peel/banana-peel.pid`, and exits the parent process immediately. Cross-platform (macOS + Linux).
- R2. `banana-peel stop` reads the PID file and sends SIGTERM to stop the background watcher. Cleans up the PID file.
- R3. `banana-peel status` reports whether the watcher is running (checks PID file and validates the process is alive).
- R4. `banana-peel install` registers a persistent OS-native service that starts on login and auto-restarts on crash. Uses launchd plist on macOS (`~/Library/LaunchAgents/com.banana-peel.watcher.plist`) and systemd user unit on Linux (`~/.config/systemd/user/banana-peel.service`). Starts the service immediately after installing.
- R5. `banana-peel uninstall` stops the service and removes the service definition file.
- R6. `install` reads watched directories from config.toml. If no config exists, falls back to directories passed as CLI arguments. If neither is available, errors with a helpful message.
- R7. When running as a daemon (either `--background` or via service), logs go to `~/.config/banana-peel/banana-peel.log` instead of stdout.
- R8. Optional macOS notifications when an image is processed, controlled by `notify = false` in config.toml `[watch]` section (default off).

## Success Criteria

- User can run `banana-peel install`, close the terminal, and have images processed automatically on next login
- `banana-peel status` correctly reports running/stopped state
- `banana-peel uninstall` cleanly removes all traces of the service
- Log file captures processing activity when running as daemon

## Scope Boundaries

- No GUI or menu bar app — CLI-only
- No Windows service support (just `--background` fork works on Windows via subprocess detach)
- Notifications are macOS-only for now (osascript); Linux notifications deferred
- No log rotation in v1 — log file grows unbounded (users can rotate externally)

## Key Decisions

- **Config.toml as primary source for install**: Service definitions read from config, with CLI args as fallback. This avoids duplicating directory lists in service files.
- **Install starts immediately**: Reduces friction — one command to go from zero to running.
- **Log file over syslog**: Simpler, more portable, easier for users to inspect.
- **Notifications default off**: Avoids surprising users; opt-in via config.

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Technical] Best Python approach for cross-platform daemon fork (os.fork vs subprocess.Popen with detach)
- [Affects R4][Needs research] Exact launchd plist and systemd unit file templates, including restart-on-crash and log redirection settings
- [Affects R8][Technical] Whether to use osascript directly or a Python notification library for macOS notifications

## Next Steps

→ `/ce:plan` for structured implementation planning
