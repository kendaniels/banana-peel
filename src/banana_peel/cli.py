"""Banana Peel CLI — Remove Gemini watermarks and compress PNGs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

from banana_peel import __version__
from banana_peel.compressor import compress_png
from banana_peel.config import Config, load_config, write_default_config
from banana_peel.daemon import LOG_PATH, PID_PATH, PidFile, start_background
from banana_peel.watermark import has_watermark, remove_watermark
from banana_peel.watcher import watch as watch_dirs

app = typer.Typer(
    name="banana-peel",
    help="Remove Gemini watermarks and losslessly compress PNG files.",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(verbose: bool, daemon_mode: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("banana_peel")
    logger.setLevel(level)

    if daemon_mode:
        # Log to file when running as daemon
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(LOG_PATH))
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    else:
        handler = RichHandler(console=console, show_path=False, markup=True)

    handler.setLevel(level)
    logger.addHandler(handler)
    logging.getLogger("PIL").setLevel(logging.WARNING)


def _load_merged_config(config_path: Optional[Path]) -> Config:
    return load_config(config_path)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"banana-peel {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Banana Peel — Remove Gemini watermarks and losslessly compress PNGs."""


@app.command()
def clean(
    paths: List[Path] = typer.Argument(..., help="Files or directories to process."),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Process directories recursively."),
    level: Optional[int] = typer.Option(None, "--level", "-l", min=0, max=6, help="Compression level (0-6)."),
    strip: Optional[str] = typer.Option(None, "--strip", "-s", help="Metadata stripping: none, safe, all."),
    no_watermark: bool = typer.Option(False, "--no-watermark", help="Skip watermark removal (compress only)."),
    no_compress: bool = typer.Option(False, "--no-compress", help="Skip compression (watermark removal only)."),
    zopfli: bool = typer.Option(False, "--zopfli", help="Use Zopfli for max compression (slower)."),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done without doing it."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output."),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path."),
) -> None:
    """Remove watermarks and compress PNG files."""
    _setup_logging(verbose)
    logger = logging.getLogger("banana_peel")
    cfg = _load_merged_config(config)

    comp_level = level if level is not None else cfg.compression.level
    comp_strip = strip if strip is not None else cfg.compression.strip_metadata
    use_zopfli = zopfli or cfg.compression.use_zopfli
    do_watermark = not no_watermark and cfg.watermark.enabled
    do_compress = not no_compress and cfg.compression.enabled

    # Collect all Gemini-generated PNG files
    png_files: list[Path] = []
    for p in paths:
        p = p.expanduser().resolve()
        if p.is_file() and p.suffix.lower() == ".png" and p.name.startswith("Gemini_Generated_Image_") and not p.stem.endswith("_peeled"):
            png_files.append(p)
        elif p.is_dir():
            glob_pattern = "**/*.png" if recursive else "*.png"
            png_files.extend(
                f for f in p.glob(glob_pattern)
                if f.name.startswith("Gemini_Generated_Image_")
                and not f.stem.endswith("_peeled")
            )
        else:
            logger.warning("Skipping: %s", p)

    if not png_files:
        console.print("[yellow]No PNG files found.[/yellow]")
        raise typer.Exit(1)

    total_saved = 0
    watermarks_removed = 0

    for png in png_files:
        peeled_path = png.with_name(png.stem + "_peeled" + png.suffix)
        watermark_removed = False

        if do_watermark and has_watermark(png):
            if dry_run:
                console.print(f"[dim]Would remove watermark:[/dim] {png.name}")
            else:
                cleaned = remove_watermark(png)
                cleaned.save(png, "PNG")
                watermark_removed = True
                watermarks_removed += 1

        if dry_run:
            action = "compress + rename" if do_compress else "rename"
            if watermark_removed:
                action = "remove watermark + " + action
            console.print(f"[dim]Would {action}:[/dim] {png.name} -> {peeled_path.name}")
        else:
            saved = 0
            if do_compress:
                saved = compress_png(
                    png, level=comp_level, strip=comp_strip,
                    use_zopfli=use_zopfli,
                )
                total_saved += saved

            # Rename to _peeled as final step
            png.rename(peeled_path)

            if watermark_removed and do_compress:
                status_msg = "Cleaned + compressed"
            elif watermark_removed:
                status_msg = "Cleaned"
            else:
                status_msg = "Compressed"
            if verbose:
                detail = f" [dim](saved {saved:,} bytes)[/dim]" if do_compress else ""
                console.print(f"[green]{status_msg}:[/green] {png.name} -> {peeled_path.name}{detail}")

    if not dry_run:
        console.print(
            f"\n[bold green]🍌 Done![/bold green] "
            f"Processed {len(png_files)} file(s), "
            f"removed {watermarks_removed} watermark(s), "
            f"saved {total_saved:,} bytes total."
        )


@app.command()
def watch(
    directories: Optional[List[Path]] = typer.Argument(None, help="Directories to watch."),
    level: Optional[int] = typer.Option(None, "--level", "-l", min=0, max=6, help="Compression level (0-6)."),
    no_watermark: bool = typer.Option(False, "--no-watermark", help="Skip watermark removal."),
    no_compress: bool = typer.Option(False, "--no-compress", help="Skip compression."),
    background: bool = typer.Option(False, "--background", "-b", help="Run in background and detach."),
    daemon_mode: bool = typer.Option(False, "--daemon-mode", hidden=True, help="Internal: run in foreground with file logging."),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output."),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path."),
) -> None:
    """Watch directories for new PNGs and process them automatically."""
    cfg = _load_merged_config(config)

    # Merge CLI dirs with config dirs
    watch_dirs_list: list[str] = []
    if directories:
        watch_dirs_list = [str(d.expanduser().resolve()) for d in directories]
    elif cfg.watch.directories:
        watch_dirs_list = cfg.watch.directories
    else:
        console.print("[red]No directories specified.[/red] Pass directories as arguments or set them in config.")
        raise typer.Exit(1)

    if level is not None:
        cfg.compression.level = level
    if no_watermark:
        cfg.watermark.enabled = False
    if no_compress:
        cfg.compression.enabled = False

    # Background mode: fork and exit parent
    if background:
        extra_args = []
        for d in watch_dirs_list:
            extra_args.append(d)
        if config:
            extra_args.extend(["--config", str(config)])
        if verbose:
            extra_args.append("--verbose")
        if no_watermark:
            extra_args.append("--no-watermark")
        if no_compress:
            extra_args.append("--no-compress")
        if level is not None:
            extra_args.extend(["--level", str(level)])

        pid = start_background(extra_args)
        console.print(f"[green]🍌 Started background watcher[/green] (PID {pid})")
        console.print(f"[dim]Logs: {LOG_PATH}[/dim]")
        console.print(f"[dim]Stop with: banana-peel stop[/dim]")
        return

    # Daemon mode: file logging + PID file lock
    if daemon_mode:
        _setup_logging(verbose, daemon_mode=True)
        pid_file = PidFile()
        pid_file.acquire()
    else:
        _setup_logging(verbose)
        console.print(f"[bold]🍌 Banana Peel[/bold] watching {len(watch_dirs_list)} directory(ies)...")
        console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    watch_dirs(
        directories=watch_dirs_list,
        watermark_config=cfg.watermark,
        compression_config=cfg.compression,
        watch_config=cfg.watch,
        dry_run=dry_run,
        verbose=verbose,
    )


@app.command()
def stop() -> None:
    """Stop the background watcher."""
    pid = PidFile.check_running()
    if pid is None:
        console.print("[yellow]No running watcher found.[/yellow]")
        raise typer.Exit(1)

    if PidFile.stop():
        console.print(f"[green]Stopped watcher[/green] (PID {pid})")
    else:
        console.print(f"[red]Failed to stop watcher[/red] (PID {pid})")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Check if the background watcher is running."""
    pid = PidFile.check_running()
    if pid is not None:
        console.print(f"[green]Running[/green] (PID {pid})")
        console.print(f"[dim]Logs: {LOG_PATH}[/dim]")
    else:
        console.print("[yellow]Not running[/yellow]")


@app.command()
def install(
    directories: Optional[List[Path]] = typer.Argument(None, help="Directories to watch (fallback if not in config)."),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path."),
) -> None:
    """Install as a persistent OS service (launchd on macOS, systemd on Linux)."""
    from banana_peel.service import install_service

    cfg = _load_merged_config(config)

    # Validate we have directories from config or args
    has_dirs = bool(cfg.watch.directories) or bool(directories)
    if not has_dirs:
        console.print(
            "[red]No directories specified.[/red]\n"
            "Set [bold]watch.directories[/bold] in config.toml or pass directories as arguments.\n"
            "Run [bold]banana-peel init[/bold] to create a config file first."
        )
        raise typer.Exit(1)

    config_path = str(config) if config else None
    result = install_service(config_path)
    console.print(f"[green]{result}[/green]")


@app.command()
def uninstall() -> None:
    """Remove the OS service."""
    from banana_peel.service import uninstall_service

    result = uninstall_service()
    console.print(result)


@app.command()
def init(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Config file path."),
) -> None:
    """Generate a default config file."""
    config_path = write_default_config(path)
    console.print(f"[green]Config written to:[/green] {config_path}")
