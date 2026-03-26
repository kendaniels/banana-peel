# 🍌 Banana Peel

Remove Gemini watermarks from PNG images and losslessly compress them.

Point Banana Peel at your Downloads folder and it watches for new Gemini images, automatically peeling the watermark and compressing them the moment they land. Install it as an OS service and never think about it again -- every image arrives clean. It also works as a one-shot CLI for processing files you already have.

## 📦 Install

```sh
pip install banana-peel
```

Or with [pipx](https://pipx.pypa.io/) for an isolated install:

```sh
pipx install banana-peel
```

Python 3.9+ required.

## 🚀 Quick Start

Clean images in your Downloads folder:

```sh
banana-peel clean ~/Downloads
```

Watch for new images and process them automatically:

```sh
banana-peel watch ~/Downloads
```

## Commands

### clean

Process files or directories on demand.

```sh
banana-peel clean photo.png                  # single file
banana-peel clean ~/Downloads                # all Gemini PNGs in a directory
banana-peel clean ~/Downloads -r             # recursive
banana-peel clean ~/Downloads --no-watermark  # compress only, skip watermark removal
banana-peel clean ~/Downloads --no-compress  # watermark removal only, skip compression
banana-peel clean ~/Downloads --zopfli       # max compression (slower)
banana-peel clean ~/Downloads -n             # dry run
```

Processed files are saved as `<name>_peeled.png`.

### watch

Monitor directories and process new Gemini PNGs as they arrive.

```sh
banana-peel watch ~/Downloads              # foreground
banana-peel watch ~/Downloads -b           # background (detached)
banana-peel watch                           # uses directories from config
```

### stop / status

Manage the background watcher.

```sh
banana-peel status    # check if the watcher is running
banana-peel stop      # stop it
```

### install / uninstall

Set up a persistent OS service so the watcher starts on login.

```sh
banana-peel install               # uses directories from config
banana-peel install ~/Downloads   # override directories
banana-peel uninstall             # remove the service
```

Uses launchd on macOS and systemd on Linux.

### init

Generate a default config file.

```sh
banana-peel init
```

## Configuration

Config lives at `~/.config/banana-peel/config.toml`. Generate one with `banana-peel init`.

```toml
[watermark]
enabled = true           # Set false to skip watermark removal (compression only)

[compression]
enabled = true           # Set false to skip compression (watermark removal only)
level = 4                # 0-6, higher = slower + smaller
strip_metadata = "safe"  # "none", "safe", "all"
use_zopfli = false       # Use Zopfli for max compression (slower)

[watch]
directories = ["~/Downloads"]  # Folders to watch (paths must be quoted)
recursive = false
debounce_seconds = 1.0
extensions = [".png"]
notify = false           # macOS notifications when an image is processed
```

All settings can be overridden with CLI flags.

## 🔬 How It Works

1. **Detection** -- Normalized cross-correlation matches the image against known watermark alpha masks (48x48 and 96x96 variants)
2. **Removal** -- Reverse alpha blending restores the original pixel values: `original = (watermarked - alpha * 255) / (1 - alpha)`
3. **Compression** -- [oxipng](https://github.com/shssoichiro/oxipng) (via pyoxipng) runs lossless optimization

The result is pixel-perfect to within +/-1 per channel due to quantization.

The reverse alpha blending method and calibrated alpha masks originate from Allen Kuo's [GeminiWatermarkTool](https://github.com/allenk/GeminiWatermarkTool), licensed under MIT. See [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) for details.

## Development

```sh
git clone https://github.com/kendaniels/banana-peel.git
cd banana-peel
pip install -e ".[dev]"
pytest
```

## License

MIT
