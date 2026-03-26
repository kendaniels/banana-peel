"""PNG to JPG conversion."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from banana_peel.config import JpgConfig


def convert_to_jpg(
    png_path: Path,
    config: JpgConfig,
) -> Path:
    """Convert a PNG file to JPG.

    Handles RGBA → RGB conversion with white background.
    Optionally deletes the source PNG.

    Returns the path to the created JPG file.
    """
    img = Image.open(png_path)

    # JPG doesn't support alpha — composite onto white background
    if img.mode in ("RGBA", "LA", "PA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    jpg_path = png_path.with_suffix(".jpg")
    img.save(jpg_path, "JPEG", quality=config.quality)

    if config.replace_png:
        png_path.unlink()

    return jpg_path
