---
title: "feat: Background/Daemon Mode for banana-peel"
type: feat
status: active
date: 2026-03-23
origin: docs/brainstorms/2026-03-23-daemon-mode-requirements.md
---

# feat: Background/Daemon Mode for banana-peel

## Overview

Add two layers of background execution to banana-peel: (1) a quick `--background` flag that forks and detaches, and (2) `install`/`uninstall` commands that register OS-native services (launchd on macOS, systemd on Linux). Also adds `stop` and `status` commands, file-based logging for daemon mode, and optional macOS notifications.

## Problem Statement / Motivation

Currently `banana-peel watch` blocks the terminal. Users want a set-and-forget experience where images are processed automatically without keeping a shell open. (see origin: docs/brainstorms/2026-03-23-daemon-mode-requirements.md)

## Proposed Solution

### New CLI Commands

| Command | Purpose |
|---------|---------|
| `banana-peel watch --background` | Fork, detach, write PID file, exit parent |
| `banana-peel stop` | Send SIGTERM via PID file, clean up |
| `banana-peel status` | Report running/stopped state |
| `banana-peel install [DIRS...]` | Register OS-native service + start immediately |
| `banana-peel uninstall` | Stop service + remove service definition |

### New Internal Flag

`banana-peel watch --daemon-mode` — runs the watcher in foreground but logs to file instead of stdout. Used by both `--background` (subprocess target) and service definitions (launchd/systemd invocation target). Not user-facing.

## Technical Approach

### Daemonization (`--background`)

Use `subprocess.Popen(start_new_session=True)` to launch a detached child process. This is cross-platform (macOS + Linux), thread-safe (unlike `os.fork`), and the pattern used by PyMongo.

```python
proc = subprocess.Popen(
    [sys.executable, "-m", "banana_peel", "watch", "--daemon-mode", ...],
    start_new_session=True,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    close_fds=True,
)
pid_file.write_text(str(proc.pid))
```

### PID File Management (`src/banana_peel/daemon.py`)

Use `flock`-based locking as the source of truth for whether a process is alive (not just PID existence + signal 0). This eliminates PID-reuse race conditions.

- **PID file location**: `~/.config/banana-peel/banana-peel.pid`
- **Lock**: `fcntl.flock(fd, LOCK_EX | LOCK_NB)` — held for process lifetime
- **Stale detection**: If lock can be acquired, PID file is stale → clean up
- **Cleanup**: `atexit` + `SIGTERM` handler

### Service Installation (`src/banana_peel/service.py`)

#### macOS (launchd)

Write plist to `~/Library/LaunchAgents/com.banana-peel.watcher.plist`:

- `ProgramArguments`: resolved path to `banana-peel` binary + `watch --daemon-mode`
- `RunAtLoad`: true (start on login)
- `KeepAlive > SuccessfulExit = false` (restart on crash only, not on clean stop)
- `ThrottleInterval`: 5 seconds
- `StandardOutPath` / `StandardErrorPath`: `~/.config/banana-peel/banana-peel.log`
- `PYTHONUNBUFFERED=1`
- `ProcessType`: Background

Load with `launchctl load`, unload with `launchctl unload`.

#### Linux (systemd)

Write unit to `~/.config/systemd/user/banana-peel.service`:

- `Type=exec`
- `ExecStart`: resolved path to `banana-peel` binary + `watch --daemon-mode`
- `Restart=on-failure`, `RestartSec=5s`
- `StandardOutput=append:~/.config/banana-peel/banana-peel.log`
- `PYTHONUNBUFFERED=1`
- `WantedBy=default.target`

Enable with `systemctl --user enable --now`, disable with `systemctl --user disable --now`.

#### Binary path resolution

At install time, resolve the banana-peel binary path using `shutil.which("banana-peel")`, falling back to `sys.executable + " -m banana_peel"`.

#### Directory source for service

Read `watch.directories` from config.toml. Fall back to CLI arguments. Error if neither available. (see origin)

### Daemon Logging (`--daemon-mode`)

When `--daemon-mode` is active, replace `RichHandler` with `logging.FileHandler` writing to `~/.config/banana-peel/banana-peel.log`. Log format: `%(asctime)s %(levelname)s %(message)s`.

### macOS Notifications

Use `subprocess.run(["osascript", "-e", script])` — zero extra dependencies. Properly escape title/message for AppleScript. No-op on non-macOS. Controlled by `notify = false` (default off) in config.toml `[watch]` section. (see origin)

### Config Changes

Add to `[watch]` section in config.toml and `WatchConfig` dataclass:

```toml
[watch]
notify = false    # macOS notifications when an image is processed
```

## Implementation Phases

### Phase 1: PID File + daemon.py

- New file: `src/banana_peel/daemon.py`
  - `PidFile` class with `acquire()`, `release()`, `check_running()`, `read_pid()`, `is_alive()`
  - flock-based locking
- Tests for PID lifecycle

### Phase 2: --background, stop, status commands

- Add `--background` flag to `watch` command
- Add `--daemon-mode` internal flag to `watch` command (switches logging to file)
- New `stop` command in `cli.py`
- New `status` command in `cli.py`
- Tests for CLI commands

### Phase 3: install/uninstall + service.py

- New file: `src/banana_peel/service.py`
  - `detect_platform() -> "macos" | "linux"`
  - `install_service(directories, config)` — writes plist or unit file, loads/enables
  - `uninstall_service()` — stops and removes
  - Template strings for plist XML and systemd unit INI
- New `install` and `uninstall` commands in `cli.py`
- Tests for template generation

### Phase 4: Notifications + config update

- Add `notify` field to `WatchConfig`
- Add `notify()` function (osascript wrapper) — `src/banana_peel/notify.py`
- Call from `PngHandler._process()` after successful processing
- Update `config.py` to load `notify` field

## Acceptance Criteria

- [ ] `banana-peel watch --background` forks, writes PID file, exits parent (R1)
- [ ] `banana-peel stop` kills the background process via PID (R2)
- [ ] `banana-peel status` reports running/stopped correctly (R3)
- [ ] `banana-peel install` creates launchd plist (macOS) or systemd unit (Linux) and starts service (R4)
- [ ] `banana-peel uninstall` stops and removes service definition (R5)
- [ ] `install` reads directories from config.toml, falls back to CLI args (R6)
- [ ] Daemon mode logs to `~/.config/banana-peel/banana-peel.log` (R7)
- [ ] Optional macOS notifications via `notify = true` in config (R8)
- [ ] PID file uses flock for reliable stale detection
- [ ] Service auto-restarts on crash (KeepAlive/Restart=on-failure)
- [ ] Service starts on login (RunAtLoad/WantedBy=default.target)

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/banana_peel/daemon.py` | **Create** — PidFile class with flock |
| `src/banana_peel/service.py` | **Create** — install/uninstall for launchd + systemd |
| `src/banana_peel/notify.py` | **Create** — macOS notification via osascript |
| `src/banana_peel/cli.py` | **Modify** — add --background, --daemon-mode, stop, status, install, uninstall |
| `src/banana_peel/config.py` | **Modify** — add notify field to WatchConfig |
| `src/banana_peel/watcher.py` | **Modify** — call notify after processing |
| `tests/test_daemon.py` | **Create** |
| `tests/test_service.py` | **Create** |
| `tests/test_cli.py` | **Modify** — tests for new commands |

## Dependencies & Risks

| Risk | Mitigation |
|------|-----------|
| `fcntl.flock` not available on Windows | PID file falls back to signal-0 check on Windows; documented limitation |
| launchd plist path varies by install method | Resolve binary path at install time via `shutil.which` |
| macOS notification permission for background processes | Document in README; OS limitation |
| systemd user services stop on logout | Document `loginctl enable-linger` for headless use |

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-23-daemon-mode-requirements.md](docs/brainstorms/2026-03-23-daemon-mode-requirements.md) — Key decisions: config.toml as primary source for install, install starts immediately, log file over syslog, notifications default off

### Internal References

- CLI: `src/banana_peel/cli.py`
- Config: `src/banana_peel/config.py`
- Watcher: `src/banana_peel/watcher.py`

### External References

- [PyMongo daemon.py — subprocess.Popen pattern](https://github.com/mongodb/mongo-python-driver/blob/master/pymongo/daemon.py)
- [Apple launchd documentation](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [systemd.service man page](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
- [Nobody does pidfiles right — flock-based approach](https://yakking.branchable.com/posts/procrun-2-pidfiles/)
