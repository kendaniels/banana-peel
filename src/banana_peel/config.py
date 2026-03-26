"""Configuration loading from TOML files with defaults."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "banana-peel" / "config.toml"

DEFAULT_TOML = """\
[watermark]
enabled = true           # Set false to skip watermark removal (compression only)

[compression]
enabled = true           # Set false to skip compression (watermark removal only)
level = 4                # 0-6, higher = slower + smaller
strip_metadata = "safe"  # "none", "safe", "all"
use_zopfli = false       # Use Zopfli for max compression (slower)

[watch]
directories = ["~/Downloads"]  # Folders to watch (paths must be quoted)
destination = ""               # Move processed files here (empty = keep in place)
recursive = false
debounce_seconds = 1.0
extensions = [".png"]
notify = false           # macOS notifications when an image is processed

[rename]
enabled = false              # Set true to rename files based on image content
provider = "gemini"          # "gemini", "openai", or "anthropic"
api_key = ""                 # API key (falls back to env var if empty)
model = ""                   # Model override (empty = provider default)

[resize]
enabled = false          # Set true to resize images
max_dimension = 1024     # Longest side in pixels (aspect ratio preserved)

[jpg]
enabled = false          # Set true to produce JPG output
quality = 85             # 1-100, higher = better quality, larger file
replace_png = false      # Set true to delete the PNG after JPG conversion
"""


@dataclass
class WatermarkConfig:
    enabled: bool = True


@dataclass
class CompressionConfig:
    enabled: bool = True
    level: int = 4
    strip_metadata: str = "safe"
    use_zopfli: bool = False
    zopfli_iterations: int = 15


@dataclass
class WatchConfig:
    directories: list[str] = field(default_factory=list)
    destination: str = ""
    recursive: bool = False
    debounce_seconds: float = 1.0
    extensions: list[str] = field(default_factory=lambda: [".png"])
    notify: bool = False


@dataclass
class RenameConfig:
    enabled: bool = False
    provider: str = "gemini"
    api_key: str = ""
    model: str = ""


@dataclass
class ResizeConfig:
    enabled: bool = False
    max_dimension: int = 1024


@dataclass
class JpgConfig:
    enabled: bool = False
    quality: int = 85
    replace_png: bool = False


@dataclass
class Config:
    watermark: WatermarkConfig = field(default_factory=WatermarkConfig)
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    watch: WatchConfig = field(default_factory=WatchConfig)
    rename: RenameConfig = field(default_factory=RenameConfig)
    resize: ResizeConfig = field(default_factory=ResizeConfig)
    jpg: JpgConfig = field(default_factory=JpgConfig)


def load_config(path: str | Path | None = None) -> Config:
    """Load config from a TOML file, falling back to defaults."""
    config = Config()

    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return config

    if tomllib is None:
        return config

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    if "watermark" in data:
        wm = data["watermark"]
        if "enabled" in wm:
            config.watermark.enabled = wm["enabled"]

    if "compression" in data:
        comp = data["compression"]
        for key in ("enabled", "level", "strip_metadata", "use_zopfli", "zopfli_iterations"):
            if key in comp:
                setattr(config.compression, key, comp[key])

    if "watch" in data:
        watch = data["watch"]
        for key in ("directories", "destination", "recursive", "debounce_seconds", "extensions", "notify"):
            if key in watch:
                setattr(config.watch, key, watch[key])

    if "rename" in data:
        rename = data["rename"]
        for key in ("enabled", "provider", "api_key", "model"):
            if key in rename:
                setattr(config.rename, key, rename[key])

    if "resize" in data:
        resize = data["resize"]
        for key in ("enabled", "max_dimension"):
            if key in resize:
                setattr(config.resize, key, resize[key])

    if "jpg" in data:
        jpg = data["jpg"]
        for key in ("enabled", "quality", "replace_png"):
            if key in jpg:
                setattr(config.jpg, key, jpg[key])

    return config


def write_default_config(path: str | Path | None = None) -> Path:
    """Write default config file. Returns the path written to."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_TOML)
    return config_path
