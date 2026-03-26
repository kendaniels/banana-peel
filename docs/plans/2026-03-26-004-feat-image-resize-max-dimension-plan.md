---
title: "feat: Resize images by max dimension"
type: feat
status: active
date: 2026-03-26
---

# Resize Images by Max Dimension

## Overview

Add an optional resize step that scales images down to a maximum dimension while preserving aspect ratio. Runs before compression for faster processing and smaller output.

## Proposed Solution

### Pipeline position

```
Watermark removal → Resize → PNG compression → AI rename → JPG conversion → Move
```

Resize runs early — before compression and everything else — so all downstream steps work with the smaller image.

### Config

```toml
[resize]
enabled = false
max_dimension = 1024     # Longest side in pixels (aspect ratio preserved)
```

**New `ResizeConfig` dataclass in `config.py`:**

```python
@dataclass
class ResizeConfig:
    enabled: bool = False
    max_dimension: int = 1024
```

### CLI flags

Added to both `clean` and `watch`:

- `--resize N` — resize to max dimension N pixels (enables resize)
- `--no-resize` — disable resize (overrides config)

### Implementation

**In `processor.py` (`process_file`), after watermark removal, before compression:**

```python
from PIL import Image

if resize_config.enabled:
    img = Image.open(file_path)
    w, h = img.size
    max_dim = resize_config.max_dimension
    if w > max_dim or h > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        img.save(file_path, "PNG")
```

Key details:
- `Image.thumbnail()` resizes in-place, preserving aspect ratio, only shrinking (never upscaling)
- `LANCZOS` resampling for high-quality downscaling
- Skip resize if image is already smaller than max_dimension
- Saves back to same path (in-place, same as watermark removal)

### Dry-run behavior

```
Would process: Gemini_Generated_Image_abc.png (resize to 1024px)
```

## Acceptance Criteria

- [ ] `ResizeConfig` dataclass with `enabled` and `max_dimension`
- [ ] `[resize]` section in `DEFAULT_TOML` and `load_config`
- [ ] `--resize N` and `--no-resize` CLI flags on `clean` and `watch`
- [ ] Resize step in `process_file()` after watermark removal, before compression
- [ ] Aspect ratio preserved (never distorts)
- [ ] Never upscales (skip if image already smaller)
- [ ] LANCZOS resampling for quality
- [ ] Background mode forwards resize flags
- [ ] Tests: resize, skip-if-smaller, aspect ratio preservation
- [ ] README updated
- [ ] CHANGELOG updated

## Sources & References

- Pipeline: `src/banana_peel/processor.py`
- Config patterns: `src/banana_peel/config.py`
- CLI patterns: `src/banana_peel/cli.py`
- Pillow: `Image.thumbnail()` with `LANCZOS`
