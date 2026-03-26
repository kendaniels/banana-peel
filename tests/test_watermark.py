"""Tests for watermark detection and removal."""

import numpy as np
from PIL import Image

from banana_peel.watermark import detect_watermark, has_watermark, process_image, remove_watermark


def test_detect_watermarked_image(watermarked_png):
    score = detect_watermark(watermarked_png)
    assert score >= 0.5, f"Expected high score for watermarked image, got {score}"


def test_detect_clean_image(clean_png):
    score = detect_watermark(clean_png)
    assert score < 0.15, f"Expected low score for clean image, got {score}"


def test_has_watermark_true(watermarked_png):
    assert has_watermark(watermarked_png) is True


def test_has_watermark_false(clean_png):
    assert has_watermark(clean_png) is False


def test_remove_watermark_quality(watermarked_png, clean_png):
    """Verify removal is pixel-accurate to within +/-2 per channel."""
    cleaned = remove_watermark(watermarked_png)
    expected = np.array(Image.open(clean_png))
    result = np.array(cleaned)

    diff = np.abs(result.astype(int) - expected.astype(int))
    assert diff.max() <= 2, f"Max pixel diff {diff.max()} exceeds tolerance of 2"


def test_process_image_removes_watermark(tmp_png):
    assert process_image(tmp_png) is True
    # Output should be saved as _peeled.png
    peeled = tmp_png.with_name(tmp_png.stem + "_peeled" + tmp_png.suffix)
    assert peeled.exists()
    assert has_watermark(peeled) is False


def test_process_image_skips_clean(clean_png, tmp_path):
    dst = tmp_path / "clean_copy.png"
    dst.write_bytes(clean_png.read_bytes())
    original_bytes = dst.read_bytes()

    assert process_image(dst) is False
    # File should be unchanged
    assert dst.read_bytes() == original_bytes
