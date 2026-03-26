"""Tests for lossless PNG compression."""

import numpy as np
from PIL import Image

from banana_peel.compressor import compress_png


def test_compress_reduces_size(tmp_png):
    original_size = tmp_png.stat().st_size
    saved = compress_png(tmp_png, level=2)
    assert saved > 0, "Expected compression to reduce file size"
    assert tmp_png.stat().st_size < original_size


def test_compress_is_lossless(tmp_png):
    """Verify compression doesn't alter pixel data (RGB channels)."""
    original_pixels = np.array(Image.open(tmp_png).convert("RGB"))
    compress_png(tmp_png, level=4)
    compressed_pixels = np.array(Image.open(tmp_png).convert("RGB"))

    np.testing.assert_array_equal(original_pixels, compressed_pixels)


def test_compress_to_output_path(tmp_png, tmp_path):
    output = tmp_path / "compressed.png"
    saved = compress_png(tmp_png, output=output, level=2)
    assert output.exists()
    assert saved > 0
