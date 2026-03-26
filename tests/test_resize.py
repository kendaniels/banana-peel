"""Tests for image resize."""

from pathlib import Path

from PIL import Image

from banana_peel.config import CompressionConfig, ResizeConfig, WatermarkConfig
from banana_peel.processor import process_file


def _make_png(path: Path, size: tuple = (2000, 1500)) -> Path:
    """Create a test PNG at a given size."""
    img = Image.new("RGB", size, (100, 150, 200))
    img.save(path, "PNG")
    return path


def test_resize_shrinks_image(tmp_path):
    png = _make_png(tmp_path / "Gemini_Generated_Image_big.png", (2000, 1500))
    result = process_file(
        file_path=png,
        watermark_config=WatermarkConfig(enabled=False),
        compression_config=CompressionConfig(enabled=False),
        resize_config=ResizeConfig(enabled=True, max_dimension=1024),
    )
    assert result is not None
    img = Image.open(result.output_path)
    assert max(img.size) == 1024
    assert img.size == (1024, 768)  # aspect ratio preserved


def test_resize_preserves_aspect_ratio(tmp_path):
    png = _make_png(tmp_path / "Gemini_Generated_Image_tall.png", (800, 2000))
    result = process_file(
        file_path=png,
        watermark_config=WatermarkConfig(enabled=False),
        compression_config=CompressionConfig(enabled=False),
        resize_config=ResizeConfig(enabled=True, max_dimension=1000),
    )
    assert result is not None
    img = Image.open(result.output_path)
    assert img.size[1] == 1000  # height is the long side
    assert img.size[0] == 400   # width scaled proportionally


def test_resize_skips_smaller_image(tmp_path):
    png = _make_png(tmp_path / "Gemini_Generated_Image_small.png", (500, 400))
    result = process_file(
        file_path=png,
        watermark_config=WatermarkConfig(enabled=False),
        compression_config=CompressionConfig(enabled=False),
        resize_config=ResizeConfig(enabled=True, max_dimension=1024),
    )
    assert result is not None
    img = Image.open(result.output_path)
    assert img.size == (500, 400)  # unchanged


def test_resize_disabled_by_default(tmp_path):
    png = _make_png(tmp_path / "Gemini_Generated_Image_noresize.png", (2000, 1500))
    result = process_file(
        file_path=png,
        watermark_config=WatermarkConfig(enabled=False),
        compression_config=CompressionConfig(enabled=False),
    )
    assert result is not None
    img = Image.open(result.output_path)
    assert img.size == (2000, 1500)  # unchanged


def test_cli_resize(tmp_path, watermarked_png):
    from typer.testing import CliRunner
    from banana_peel.cli import app

    dst = tmp_path / "Gemini_Generated_Image_resize_test.png"
    # Make a large image
    img = Image.new("RGB", (2000, 1500), (100, 150, 200))
    img.save(dst, "PNG")

    runner = CliRunner()
    result = runner.invoke(app, ["clean", str(dst), "--resize", "800", "--verbose"])
    assert result.exit_code == 0

    peeled = list(tmp_path.glob("*_peeled.png"))
    assert len(peeled) == 1
    img = Image.open(peeled[0])
    assert max(img.size) == 800
