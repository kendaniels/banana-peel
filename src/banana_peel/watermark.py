"""Gemini watermark detection and removal via reverse alpha blending.

The reverse alpha blending method and calibrated alpha masks used here
originate from GeminiWatermarkTool by Allen Kuo (AllenK / Kwyshell):
https://github.com/allenk/GeminiWatermarkTool
Licensed under the MIT License. See THIRD_PARTY_NOTICES for full text.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

_ASSETS_DIR = Path(__file__).parent / "assets"

# Watermark config by image size
_CONFIGS = {
    "large": {"mask": "mask_96.png", "size": 96, "margin": 64, "min_dim": 1025},
    "small": {"mask": "mask_48.png", "size": 48, "margin": 32, "min_dim": 0},
}

# Detection threshold — minimum correlation score to consider watermark present
_DETECTION_THRESHOLD = 0.15

# Alpha thresholds for reversal
_ALPHA_MIN = 0.002  # Ignore insignificant alpha values
_ALPHA_MAX = 0.99   # Prevent division by near-zero


def _load_mask(name: str) -> np.ndarray:
    """Load an alpha mask and return the alpha channel as float array [0, 1]."""
    mask_path = _ASSETS_DIR / name
    mask_img = Image.open(mask_path).convert("RGBA")
    return np.array(mask_img)[:, :, 3].astype(np.float64) / 255.0


def _get_config(width: int, height: int) -> dict:
    """Pick watermark config based on image dimensions."""
    if width > 1024 and height > 1024:
        return _CONFIGS["large"]
    return _CONFIGS["small"]


def _extract_region(
    pixels: np.ndarray, width: int, height: int, size: int, margin: int
) -> tuple[int, int, int, int]:
    """Return (y1, y2, x1, x2) for the watermark region."""
    y1 = height - margin - size
    x1 = width - margin - size
    return y1, y1 + size, x1, x1 + size


def detect_watermark(image_path: str | Path) -> float:
    """Detect Gemini watermark. Returns confidence score (0.0 to 1.0).

    A score above _DETECTION_THRESHOLD indicates the watermark is likely present.
    """
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    config = _get_config(width, height)

    alpha_mask = _load_mask(config["mask"])
    size = config["size"]
    margin = config["margin"]

    if width < size + margin or height < size + margin:
        return 0.0

    pixels = np.array(img).astype(np.float64)
    y1, y2, x1, x2 = _extract_region(pixels, width, height, size, margin)
    region = pixels[y1:y2, x1:x2, :3]

    # Normalized cross-correlation between the region brightness pattern
    # and the expected watermark alpha pattern.
    # The watermark adds brightness proportional to alpha * (255 - original).
    # For detection, we check if the bright areas match the mask shape.

    # Compute per-pixel brightness deviation from region mean
    region_gray = np.mean(region, axis=2)
    region_mean = np.mean(region_gray)
    region_dev = region_gray - region_mean

    # Mask deviation from its mean
    mask_mean = np.mean(alpha_mask)
    mask_dev = alpha_mask - mask_mean

    # NCC
    numerator = np.sum(region_dev * mask_dev)
    denominator = np.sqrt(np.sum(region_dev**2) * np.sum(mask_dev**2))

    if denominator < 1e-10:
        return 0.0

    ncc = numerator / denominator
    return float(max(0.0, ncc))


def has_watermark(image_path: str | Path) -> bool:
    """Check if image has a Gemini watermark above the detection threshold."""
    return detect_watermark(image_path) >= _DETECTION_THRESHOLD


def remove_watermark(image_path: str | Path) -> Image.Image:
    """Remove the Gemini watermark and return the cleaned image.

    Uses reverse alpha blending:
        original = (watermarked - alpha * 255) / (1 - alpha)
    """
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    config = _get_config(width, height)

    alpha_mask = _load_mask(config["mask"])
    size = config["size"]
    margin = config["margin"]

    pixels = np.array(img).astype(np.float64)
    y1, y2, x1, x2 = _extract_region(pixels, width, height, size, margin)

    for c in range(3):  # R, G, B channels
        region = pixels[y1:y2, x1:x2, c]
        # Only process pixels where alpha mask is significant
        mask = (alpha_mask >= _ALPHA_MIN) & (alpha_mask <= _ALPHA_MAX)
        alpha = alpha_mask[mask]
        # Reverse: original = (watermarked - alpha * 255) / (1 - alpha)
        region[mask] = (region[mask] - alpha * 255.0) / (1.0 - alpha)

    # Clamp to valid range and convert back
    pixels = np.clip(pixels, 0, 255).astype(np.uint8)
    return Image.fromarray(pixels)


def process_image(image_path: str | Path) -> bool:
    """Detect and remove watermark if present. Returns True if watermark was removed.

    Saves cleaned result back to the original file, then renames to <name>_peeled.png.
    """
    image_path = Path(image_path)
    if not has_watermark(image_path):
        return False

    cleaned = remove_watermark(image_path)
    cleaned.save(image_path, "PNG")
    peeled_path = image_path.with_name(image_path.stem + "_peeled" + image_path.suffix)
    image_path.rename(peeled_path)
    return True
