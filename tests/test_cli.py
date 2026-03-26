"""Tests for the CLI interface."""

from typer.testing import CliRunner

from banana_peel.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "banana-peel" in result.output


def test_clean_file(tmp_png):
    result = runner.invoke(app, ["clean", str(tmp_png), "--verbose"])
    assert result.exit_code == 0
    assert "Done!" in result.output


def test_clean_dry_run(tmp_png):
    original_bytes = tmp_png.read_bytes()
    result = runner.invoke(app, ["clean", str(tmp_png), "--dry-run"])
    assert result.exit_code == 0
    assert "Would" in result.output
    # File should be unchanged
    assert tmp_png.read_bytes() == original_bytes


def test_clean_no_files(tmp_path):
    result = runner.invoke(app, ["clean", str(tmp_path / "nonexistent.png")])
    assert result.exit_code == 1


def test_init(tmp_path):
    config_path = tmp_path / "config.toml"
    result = runner.invoke(app, ["init", "--path", str(config_path)])
    assert result.exit_code == 0
    assert config_path.exists()
    content = config_path.read_text()
    assert "[compression]" in content
    assert "notify" in content


def test_status_not_running():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Not running" in result.output


def test_clean_with_destination(tmp_png, tmp_path):
    dest = tmp_path / "output"
    result = runner.invoke(app, ["clean", str(tmp_png), "--destination", str(dest), "--verbose"])
    assert result.exit_code == 0
    assert "Done!" in result.output
    # File should be in destination, not original location
    assert not tmp_png.with_name(tmp_png.stem + "_peeled.png").exists()
    assert (dest / (tmp_png.stem + "_peeled.png")).exists()


def test_stop_not_running():
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 1
    assert "No running watcher" in result.output
