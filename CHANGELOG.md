# Changelog

All notable changes to Banana Peel will be documented in this file.

## 0.1.0 - 2026-03-26

Initial release.

- Watermark detection via normalized cross-correlation against 48x48 and 96x96 alpha masks
- Watermark removal via reverse alpha blending
- Lossless PNG compression powered by oxipng (levels 0-6, Zopfli optional), with `--no-compress` flag to skip
- `clean` command for one-shot processing of files and directories
- `watch` command for real-time directory monitoring with debouncing
- Background mode (`--background`) with PID file management
- `install`/`uninstall` commands for persistent OS services (launchd on macOS, systemd on Linux)
- `stop`/`status` commands for background watcher management
- TOML configuration with CLI overrides
- macOS notifications (opt-in)
- Metadata stripping options: none, safe, all
