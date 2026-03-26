---
title: "feat: Gemini Watermark Remover & PNG Optimizer CLI"
type: feat
status: active
date: 2026-03-23
---

# feat: Gemini Watermark Remover & PNG Optimizer CLI

## Overview

Build `banana-peel`, a cross-platform Python CLI tool that watches folders for new PNG files (from Gemini/Nano Banana image generation), automatically removes the visible Gemini sparkle watermark via reverse alpha blending, losslessly compresses the result, and overwrites the original file.

## Problem Statement / Motivation

Gemini-generated images include a visible semi-transparent sparkle logo watermarked into the bottom-right corner. Manually removing this from every saved image is tedious. Users want a set-and-forget background process that cleans and compresses images automatically.

## Proposed Solution

A Python CLI with two modes:

1. **`banana-peel watch`** — watches one or more folders and processes new/modified PNGs automatically
2. **`banana-peel clean`** — one-shot processing of a file or directory

Processing pipeline per image:
1. Detect if Gemini watermark is present (normalized cross-correlation against known alpha mask)
2. Remove watermark via reverse alpha blending
3. Losslessly compress with pyoxipng
4. Overwrite original file

### How the Watermark Works

The visible watermark is the Gemini four-pointed star logo, alpha-composited onto the bottom-right corner:

```
watermarked_pixel = alpha * logo_pixel + (1 - alpha) * original_pixel
```

- **Two sizes**: 48x48px (images <=1024px) and 96x96px (images >1024px)
- **Margins**: 32px and 64px from bottom-right respectively
- The logo is white/light and semi-transparent, creating the "lightened area" effect

### Reversal Formula

```
original_pixel = (watermarked_pixel - alpha * logo_pixel) / (1 - alpha)
```

This is mathematically exact with at most +/-1 per channel quantization error (8-bit rounding).

The alpha mask (per-pixel transparency values of the watermark) will be calibrated from the user's sample images. An existing open-source implementation exists at [VimalMollyn/Gemini-Watermark-Remover-Python](https://github.com/VimalMollyn/Gemini-Watermark-Remover-Python) which we can reference or integrate.

## Technical Approach

### Stack

| Component | Library | Why |
|-----------|---------|-----|
| CLI framework | **Typer** | Type-hint driven, Rich integration, Click under the hood |
| Config | **TOML** via `tomllib` (stdlib 3.11+) | Simple, standard, human-readable |
| Image processing | **Pillow** + **NumPy** | Load/save images, pixel-level math for watermark reversal |
| PNG compression | **pyoxipng** | Rust-based oxipng bindings, multithreaded, best lossless compression |
| File watching | **watchdog** | Cross-platform (FSEvents/inotify/ReadDirectoryChanges), well-maintained |
| Output formatting | **Rich** (via Typer) | Styled terminal output, progress indicators |

### Project Structure

```
banana-peel/
    pyproject.toml
    src/
        banana_peel/
            __init__.py
            __main__.py           # python -m banana_peel support
            cli.py                # Typer app: watch, clean commands
            config.py             # TOML config loading + defaults
            watermark.py          # Watermark detection + removal (reverse alpha blend)
            compressor.py         # pyoxipng lossless compression wrapper
            watcher.py            # watchdog integration + debouncing
            assets/
                mask_48.png       # Pre-computed alpha mask (48x48)
                mask_96.png       # Pre-computed alpha mask (96x96)
    tests/
        conftest.py
        test_watermark.py         # Test detection + removal with sample images
        test_compressor.py
        test_watcher.py
        test_cli.py
        fixtures/
            watermarked.png       # Sample watermarked image
            clean.png             # Expected output
```

### Architecture

```
CLI (cli.py)
  |
  ├── watch command ──> Watcher (watcher.py)
  |                       |
  |                       ├── on_created/on_modified
  |                       |     |
  |                       |     ▼
  |                       └── Pipeline
  |                             |
  └── clean command ────────────┘
                                |
                          ┌─────▼──────┐
                          │ watermark.py│ detect + remove
                          └─────┬──────┘
                                |
                          ┌─────▼───────────┐
                          │ compressor.py    │ lossless compress
                          └─────┬───────────┘
                                |
                          overwrite original
```

### Implementation Phases

#### Phase 1: Core — Watermark Removal

- Analyze user's sample images to calibrate/validate alpha masks
- Implement `watermark.py`:
  - `detect_watermark(image_path) -> bool` — checks if Gemini watermark is present
  - `remove_watermark(image_path) -> Image` — reverse alpha blend
  - Auto-detect 48px vs 96px variant based on image dimensions
- Reference [Gemini-Watermark-Remover-Python](https://github.com/VimalMollyn/Gemini-Watermark-Remover-Python) for mask data and approach
- Write tests using sample images

#### Phase 2: Core — Lossless Compression

- Implement `compressor.py`:
  - `compress_png(path, level=4, strip="safe")` — wraps pyoxipng
  - Configurable compression level (0-6)
  - Option for Zopfli deflater for maximum compression
- Write tests verifying lossless output (pixel-perfect comparison)

#### Phase 3: File Watcher

- Implement `watcher.py`:
  - Subclass `FileSystemEventHandler` for PNG-only events
  - Debounce (1s default) to handle editors triggering multiple events
  - Wait for file write completion before processing
  - Skip files currently being processed (avoid re-triggering on own writes)
  - Support multiple watched directories
- Graceful shutdown on SIGINT/SIGTERM

#### Phase 4: CLI & Config

- Implement `cli.py` with Typer:
  - `banana-peel watch [DIRS...] [--config PATH]` — start watching
  - `banana-peel clean [PATH] [--recursive]` — one-shot processing
  - `banana-peel init` — generate default config file
  - Common options: `--level`, `--verbose`, `--dry-run`
- Implement `config.py`:
  - Load from `~/.config/banana-peel/config.toml` or `--config` flag
  - CLI flags override config file values
  - Default config:

```toml
[watermark]
enabled = true           # Set false to skip watermark removal (compression only)

[compression]
level = 4                # 0-6, higher = slower + smaller
strip_metadata = "safe"  # "none", "safe", "all"
use_zopfli = false       # Use Zopfli for max compression (slower)

[watch]
directories = []         # Folders to watch
recursive = false
debounce_seconds = 1.0
extensions = [".png"]
```

#### Phase 5: Polish & Distribution

- `pyproject.toml` with `[project.scripts]` entry point
- `__main__.py` for `python -m banana_peel`
- Error handling and logging
- Installable via `pip install .` or `pipx install .`

## System-Wide Impact

- **Self-triggering prevention**: The watcher must not re-process files it just wrote. Use a processing lock set (in-memory set of paths currently being processed) and/or a brief cooldown after writing.
- **File write race condition**: PNG files may not be fully written when `on_created` fires. Wait for file size to stabilize or use a debounce window.
- **Large files**: NumPy array operations for watermark removal are fast even for large images. pyoxipng compression is the bottleneck — level 4 is a good default balance.

## Acceptance Criteria

- [ ] Detects presence of Gemini watermark with high confidence
- [ ] Removes watermark via reverse alpha blending (pixel-accurate to +/-1 per channel)
- [ ] Losslessly compresses PNG (verifiable: re-decode and compare pixels)
- [ ] Overwrites original file with clean + compressed version
- [ ] Watches multiple directories for new PNG files
- [ ] Debounces rapid file events (no double-processing)
- [ ] Does not re-trigger on its own file writes
- [ ] Loads config from TOML file with CLI flag overrides
- [ ] `banana-peel clean` works for one-shot processing
- [ ] `banana-peel watch` runs as a long-lived background process
- [ ] Cross-platform: works on macOS, Linux, Windows
- [ ] Installable via pip/pipx

## Dependencies & Risks

| Risk | Mitigation |
|------|-----------|
| Alpha mask may not match all Gemini watermark variants | Calibrate from user samples; use confidence threshold to skip uncertain images |
| pyoxipng maintenance flagged as "inactive" | Underlying Rust oxipng is active; wrapper is stable and functional |
| Watchdog may miss events on some filesystems (e.g., network mounts) | Document limitation; offer `clean --recursive` as fallback |
| SynthID invisible watermark cannot be removed | Out of scope — document this clearly |

## Sources & References

### Watermark Removal

- [Gemini-Watermark-Remover-Python (GitHub)](https://github.com/VimalMollyn/Gemini-Watermark-Remover-Python) — MIT licensed reference implementation
- [GeminiWatermarkTool by Allen Kuo (GitHub)](https://github.com/allenk/GeminiWatermarkTool) — most technically detailed implementation
- [Removing Gemini AI Watermarks: Reverse Alpha Blending — Allen Kuo (Medium)](https://allenkuo.medium.com/removing-gemini-ai-watermarks-a-deep-dive-into-reverse-alpha-blending-bbbd83af2a3f)

### PNG Compression

- [pyoxipng on PyPI](https://pypi.org/project/pyoxipng/) — Rust oxipng bindings for Python
- [oxipng (GitHub)](https://github.com/shssoichiro/oxipng) — underlying Rust optimizer

### Libraries

- [Typer](https://typer.tiangolo.com/) — CLI framework
- [watchdog](https://github.com/gorakhargosh/watchdog) — filesystem monitoring
- [Pillow](https://pillow.readthedocs.io/) — image processing
- [NumPy](https://numpy.org/) — array math for pixel operations
