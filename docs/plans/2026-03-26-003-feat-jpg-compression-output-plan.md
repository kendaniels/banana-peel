---
title: "feat: JPG compression output with quality settings"
type: feat
status: active
date: 2026-03-26
---

# JPG Compression Output

## Overview

Add an optional JPG output step to the processing pipeline. After watermark removal and PNG compression, convert the result to JPG at a configurable quality percentage. By default, keep the PNG alongside the JPG; optionally replace it.

## Problem Statement / Motivation

PNG files from Gemini are large. Lossless PNG compression helps, but many use cases (sharing, uploading, storage) benefit from lossy JPG compression at a fraction of the file size. Users currently need a separate tool to convert after processing.

## Proposed Solution

Add a final pipeline step that converts the processed PNG to JPG using Pillow (already a dependency). Configurable via CLI flags and config.

### Pipeline position

```
Watermark removal → PNG compression → AI rename → JPG conversion → Move to destination
```

JPG conversion runs last, after rename, so the output filename is `steak-dinner.jpg` (not `steak-dinner_peeled.jpg` then converted).

### Config

```toml
[jpg]
enabled = false          # Set true to produce JPG output
quality = 85             # 1-100, higher = better quality, larger file
replace_png = false      # Set true to delete the PNG after JPG conversion
```

**New `JpgConfig` dataclass in `config.py`:**

```python
@dataclass
class JpgConfig:
    enabled: bool = False
    quality: int = 85
    replace_png: bool = False
```

### CLI flags

Added to both `clean` and `watch`:

- `--jpg` — enable JPG output (overrides config)
- `--no-jpg` — disable JPG output (overrides config)
- `--jpg-quality N` — quality percentage 1-100 (default: 85)
- `--replace-png` — delete the PNG after JPG conversion

### Implementation

**In `processor.py` (`process_file`):**

After rename + move, if `jpg_config.enabled`:

```python
from PIL import Image

png_path = result.output_path
jpg_path = png_path.with_suffix(".jpg")

img = Image.open(png_path).convert("RGB")  # JPG has no alpha
img.save(jpg_path, "JPEG", quality=jpg_config.quality)

if jpg_config.replace_png:
    png_path.unlink()
```

**`ProcessResult` update:**

Add `jpg_path: Path | None = None` and `jpg_bytes_saved: int = 0` fields.

### Watcher considerations

- The `.jpg` output won't match `_is_target()` (requires `.png` extension and `Gemini_Generated_Image_` prefix) — no self-trigger risk
- If `watch.extensions` is extended to include `.jpg` in the future, the `_is_target` prefix check still prevents re-processing

### Dry-run behavior

```
Would process: Gemini_Generated_Image_abc.png -> steak-dinner.png + steak-dinner.jpg (quality: 85)
```

## Acceptance Criteria

- [ ] `JpgConfig` dataclass with `enabled`, `quality`, `replace_png`
- [ ] `[jpg]` section in `DEFAULT_TOML` and `load_config`
- [ ] `--jpg` / `--no-jpg` / `--jpg-quality` / `--replace-png` CLI flags on `clean` and `watch`
- [ ] JPG conversion step in `process_file()` after rename + move
- [ ] Alpha channel handled (RGBA → RGB conversion before JPG save)
- [ ] `ProcessResult` updated with JPG output info
- [ ] `replace_png` deletes the PNG when enabled
- [ ] Dry-run shows JPG output without converting
- [ ] Background mode forwards JPG flags
- [ ] Console output shows JPG file size / savings
- [ ] Tests: JPG output, quality setting, replace_png, RGBA handling
- [ ] README updated with JPG section
- [ ] CHANGELOG updated

## Technical Considerations

- **Pillow is already a dependency** — no new packages needed. `Image.save("JPEG", quality=N)` is the entire implementation.
- **RGBA → RGB** — Gemini PNGs have an alpha channel. Must convert to RGB before saving as JPG or Pillow raises an error. Use white background for compositing: `Image.new("RGB", img.size, (255, 255, 255))` then paste with alpha mask.
- **File size reporting** — Show both PNG and JPG sizes in verbose output so users can see the savings.

## Sources & References

- Pipeline: `src/banana_peel/processor.py` (process_file)
- Config patterns: `src/banana_peel/config.py` (dataclass + TOML loading)
- CLI patterns: `src/banana_peel/cli.py` (typer option declarations)
- Pillow JPEG docs: `Image.save()` with `quality` parameter
