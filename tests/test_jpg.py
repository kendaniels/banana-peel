"""Tests for JPG conversion."""

from pathlib import Path

from PIL import Image

from banana_peel.config import JpgConfig
from banana_peel.jpg import convert_to_jpg


def _make_rgba_png(path: Path, size: tuple = (100, 100)) -> Path:
    """Create a test RGBA PNG file."""
    img = Image.new("RGBA", size, (255, 0, 0, 128))
    img.save(path, "PNG")
    return path


def _make_rgb_png(path: Path, size: tuple = (100, 100)) -> Path:
    """Create a test RGB PNG file."""
    img = Image.new("RGB", size, (0, 128, 255))
    img.save(path, "PNG")
    return path


def test_convert_basic(tmp_path):
    png = _make_rgb_png(tmp_path / "test.png")
    config = JpgConfig(enabled=True, quality=85)
    jpg_path = convert_to_jpg(png, config)
    assert jpg_path.exists()
    assert jpg_path.suffix == ".jpg"
    assert jpg_path.name == "test.jpg"
    assert png.exists()  # PNG should still exist


def test_convert_rgba_to_jpg(tmp_path):
    png = _make_rgba_png(tmp_path / "alpha.png")
    config = JpgConfig(enabled=True, quality=85)
    jpg_path = convert_to_jpg(png, config)
    assert jpg_path.exists()
    # Verify the JPG is valid RGB
    img = Image.open(jpg_path)
    assert img.mode == "RGB"


def test_convert_quality(tmp_path):
    png = _make_rgb_png(tmp_path / "test.png", size=(200, 200))
    low = convert_to_jpg(png, JpgConfig(enabled=True, quality=10))
    low_size = low.stat().st_size

    # Re-create png (convert_to_jpg doesn't delete by default)
    _make_rgb_png(tmp_path / "test.png", size=(200, 200))
    # Remove old jpg first
    low.unlink()
    high = convert_to_jpg(png, JpgConfig(enabled=True, quality=95))
    high_size = high.stat().st_size

    assert high_size > low_size


def test_replace_png(tmp_path):
    png = _make_rgb_png(tmp_path / "test.png")
    config = JpgConfig(enabled=True, quality=85, replace_png=True)
    jpg_path = convert_to_jpg(png, config)
    assert jpg_path.exists()
    assert not png.exists()  # PNG should be deleted


def test_keep_png_by_default(tmp_path):
    png = _make_rgb_png(tmp_path / "test.png")
    config = JpgConfig(enabled=True, quality=85, replace_png=False)
    jpg_path = convert_to_jpg(png, config)
    assert jpg_path.exists()
    assert png.exists()  # PNG should still exist


def test_cli_clean_with_jpg(tmp_png):
    from typer.testing import CliRunner
    from banana_peel.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["clean", str(tmp_png), "--jpg", "--verbose"])
    assert result.exit_code == 0
    assert "Done!" in result.output
    # Check JPG was created
    peeled = tmp_png.with_name(tmp_png.stem + "_peeled.png")
    jpg = peeled.with_suffix(".jpg")
    # The peeled file was renamed, check the jpg exists
    parent = tmp_png.parent
    jpgs = list(parent.glob("*_peeled.jpg"))
    assert len(jpgs) == 1


def test_cli_clean_with_jpg_replace(tmp_png):
    from typer.testing import CliRunner
    from banana_peel.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["clean", str(tmp_png), "--jpg", "--replace-png", "--verbose"])
    assert result.exit_code == 0
    parent = tmp_png.parent
    pngs = list(parent.glob("*_peeled.png"))
    jpgs = list(parent.glob("*_peeled.jpg"))
    assert len(pngs) == 0  # PNG deleted
    assert len(jpgs) == 1  # JPG exists
