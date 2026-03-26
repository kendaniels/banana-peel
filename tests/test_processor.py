"""Tests for the shared processor pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from banana_peel.config import CompressionConfig, RenameConfig, WatermarkConfig
from banana_peel.processor import process_file


def test_process_file_basic(tmp_png):
    """Process a file with default config (rename disabled)."""
    result = process_file(
        file_path=tmp_png,
        watermark_config=WatermarkConfig(),
        compression_config=CompressionConfig(),
    )
    assert result is not None
    assert result.output_path.name.endswith("_peeled.png")
    assert result.output_path.exists()
    assert result.ai_renamed is False


def test_process_file_dry_run(tmp_png):
    """Dry run returns None without modifying files."""
    original_bytes = tmp_png.read_bytes()
    result = process_file(
        file_path=tmp_png,
        watermark_config=WatermarkConfig(),
        compression_config=CompressionConfig(),
        dry_run=True,
    )
    assert result is None
    assert tmp_png.read_bytes() == original_bytes


def test_process_file_with_destination(tmp_png, tmp_path):
    """Processed file is moved to destination."""
    dest = tmp_path / "output"
    result = process_file(
        file_path=tmp_png,
        watermark_config=WatermarkConfig(),
        compression_config=CompressionConfig(),
        destination=dest,
    )
    assert result is not None
    assert result.output_path.parent == dest
    assert result.output_path.exists()
    assert not tmp_png.with_name(tmp_png.stem + "_peeled.png").exists()


def test_process_file_no_watermark(tmp_png):
    """Skipping watermark removal still compresses and renames."""
    result = process_file(
        file_path=tmp_png,
        watermark_config=WatermarkConfig(enabled=False),
        compression_config=CompressionConfig(),
    )
    assert result is not None
    assert result.watermark_removed is False
    assert result.output_path.name.endswith("_peeled.png")


def test_process_file_no_compress(tmp_png):
    """Skipping compression still renames."""
    result = process_file(
        file_path=tmp_png,
        watermark_config=WatermarkConfig(),
        compression_config=CompressionConfig(enabled=False),
    )
    assert result is not None
    assert result.bytes_saved == 0
    assert result.output_path.name.endswith("_peeled.png")


def test_process_file_ai_rename_fallback(tmp_png):
    """AI rename falls back to _peeled when renamer fails."""
    rename_config = RenameConfig(enabled=True, provider="gemini", api_key="fake")

    with patch("banana_peel.processor.process_file.__module__", "banana_peel.processor"):
        result = process_file(
            file_path=tmp_png,
            watermark_config=WatermarkConfig(),
            compression_config=CompressionConfig(),
            rename_config=rename_config,
        )
    assert result is not None
    # Should fall back to _peeled since no real API
    assert result.output_path.name.endswith("_peeled.png") or result.ai_renamed is False
