"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def watermarked_png():
    return FIXTURES_DIR / "watermarked.png"


@pytest.fixture
def clean_png():
    return FIXTURES_DIR / "clean.png"


@pytest.fixture
def tmp_png(watermarked_png, tmp_path):
    """A temporary copy of the watermarked image for mutation tests."""
    dst = tmp_path / "Gemini_Generated_Image_test.png"
    dst.write_bytes(watermarked_png.read_bytes())
    return dst
