# Changelog

All notable changes to Banana Peel will be documented in this file.

## 0.3.0 - 2026-03-26

- Add JPG output option with configurable quality (`--jpg`, `--jpg-quality 1-100`)
- Add `--replace-png` flag to delete the PNG after JPG conversion
- Add `[jpg]` config section with `enabled`, `quality`, and `replace_png` options
- RGBA images are composited onto white background before JPG conversion

## 0.2.0 - 2026-03-26

- Add `--destination` / `-d` option to `clean` and `watch` commands to move processed files to a separate folder
- Add `destination` config option under `[watch]` section
- Destination directory is created automatically if it doesn't exist

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
