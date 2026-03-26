# Changelog

All notable changes to Banana Peel will be documented in this file.

## 0.3.0 - 2026-03-26

- AI-powered image renaming: `--ai-rename` flag renames files based on image content (e.g., `steak-dinner.png`)
- Provider-agnostic: supports Gemini, OpenAI, and Anthropic vision APIs
- `[rename]` config section with `enabled`, `provider`, `api_key`, and `model` options
- `--provider` and `--api-key` CLI flags for both `clean` and `watch` commands
- Optional SDK dependencies: `pip install banana-peel[gemini]`, `[openai]`, `[anthropic]`, or `[ai]`
- Graceful fallback to `_peeled` naming when API is unavailable
- Retry with exponential backoff on rate limiting
- Refactored processing pipeline into shared `processor.py` module
- Add JPG output option with configurable quality (`--jpg`, `--jpg-quality 1-100`)
- Add `--replace-png` flag to delete the PNG after JPG conversion
- Add `[jpg]` config section with `enabled`, `quality`, and `replace_png` options
- RGBA images are composited onto white background before JPG conversion
- Renamed `--destination` / `-d` to `--move` / `-m`
- Add `--resize N` option to resize images to max dimension (aspect ratio preserved)
- Add `[resize]` config section with `enabled` and `max_dimension` options
- Renamed `--no-watermark` to `--skip-watermark`

## 0.2.0 - 2026-03-26

- Add `--move` / `-m` option to `clean` and `watch` commands to move processed files to a separate folder
- Add `destination` config option under `[watch]` section
- Move directory is created automatically if it doesn't exist

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
