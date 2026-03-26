"""Folder watcher for automatic PNG processing."""

from __future__ import annotations

import logging
import os
import shutil
import signal
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from banana_peel.compressor import compress_png
from banana_peel.config import CompressionConfig, WatchConfig, WatermarkConfig
from banana_peel.notify import notify as send_notification
from banana_peel.watermark import has_watermark, remove_watermark

logger = logging.getLogger("banana_peel")


class PngHandler(FileSystemEventHandler):
    """Handles PNG file creation/modification events."""

    def __init__(
        self,
        watermark_config: WatermarkConfig,
        compression_config: CompressionConfig,
        watch_config: WatchConfig,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__()
        self._watermark_config = watermark_config
        self._compression_config = compression_config
        self._extensions = set(watch_config.extensions)
        self._debounce = watch_config.debounce_seconds
        self._destination = (
            Path(watch_config.destination).expanduser().resolve()
            if watch_config.destination
            else None
        )
        self._dry_run = dry_run
        self._verbose = verbose
        self._notify = watch_config.notify

        self._lock = threading.Lock()

        # Self-trigger prevention: track what we're actively processing
        self._processing: set[str] = set()

        # After we write a file, record its mtime. If a later event fires
        # and the mtime hasn't changed, we know it's a self-triggered event.
        self._our_mtime: dict[str, float] = {}

        # Debounce tracking
        self._timers: dict[str, threading.Timer] = {}

    def _is_target(self, path: str) -> bool:
        name = Path(path).name
        return (
            name.startswith("Gemini_Generated_Image_")
            and not name.endswith("_peeled.png")
            and any(name.lower().endswith(ext) for ext in self._extensions)
        )

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_target(event.src_path):
            self._schedule(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_target(event.src_path):
            self._schedule(event.src_path)

    def _schedule(self, path: str) -> None:
        """Schedule processing with debounce."""
        with self._lock:
            # Skip if we're currently processing this file
            if path in self._processing:
                return

            # Cancel any pending timer for this path (debounce reset)
            if path in self._timers:
                self._timers[path].cancel()

            timer = threading.Timer(self._debounce, self._process, args=[path])
            timer.daemon = True
            self._timers[path] = timer
            timer.start()

    def _process(self, path: str) -> None:
        """Process a single PNG file."""
        with self._lock:
            self._processing.add(path)
            self._timers.pop(path, None)

        try:
            file_path = Path(path)
            if not file_path.exists() or not file_path.is_file():
                return

            # Self-trigger guard: if the file's mtime matches what we last
            # wrote, this event was caused by our own save — skip it.
            current_mtime = os.path.getmtime(path)
            with self._lock:
                if path in self._our_mtime and self._our_mtime[path] == current_mtime:
                    return

            # Final name after processing
            peeled_path = file_path.with_name(
                file_path.stem + "_peeled" + file_path.suffix
            )

            # Skip if already processed (peeled file exists)
            if peeled_path.exists():
                return

            if self._dry_run:
                logger.info("[dry-run] Would process: %s -> %s", path, peeled_path)
                return

            watermark_removed = False
            if self._watermark_config.enabled and has_watermark(file_path):
                cleaned = remove_watermark(file_path)
                cleaned.save(file_path, "PNG")
                watermark_removed = True

            saved = 0
            if self._compression_config.enabled:
                saved = compress_png(
                    file_path,
                    level=self._compression_config.level,
                    strip=self._compression_config.strip_metadata,
                    use_zopfli=self._compression_config.use_zopfli,
                    zopfli_iterations=self._compression_config.zopfli_iterations,
                )

            # Rename to _peeled as final step
            file_path.rename(peeled_path)

            # Move to destination folder if configured
            final_path = peeled_path
            if self._destination:
                self._destination.mkdir(parents=True, exist_ok=True)
                dest_path = self._destination / peeled_path.name
                shutil.move(str(peeled_path), str(dest_path))
                final_path = dest_path
                logger.info("Moved: %s -> %s", peeled_path.name, final_path)

            if watermark_removed and self._compression_config.enabled:
                action = "Cleaned + compressed"
            elif watermark_removed:
                action = "Cleaned"
            else:
                action = "Compressed"
            logger.info("%s: %s -> %s (saved %d bytes)", action, file_path.name, final_path.name, saved)

            # Send notification if enabled
            if self._notify and not self._dry_run:
                send_notification("Banana Peel", f"{action}: {final_path.name}")

            # Record the mtime of the final file so we don't re-process it
            with self._lock:
                final_str = str(final_path)
                self._our_mtime[final_str] = os.path.getmtime(final_str)

        except Exception:
            logger.exception("Error processing %s", path)
        finally:
            with self._lock:
                self._processing.discard(path)


def watch(
    directories: list[str | Path],
    watermark_config: WatermarkConfig | None = None,
    compression_config: CompressionConfig | None = None,
    watch_config: WatchConfig | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Watch directories for PNG files and process them.

    Blocks until SIGINT/SIGTERM.
    """
    watermark_config = watermark_config or WatermarkConfig()
    compression_config = compression_config or CompressionConfig()
    watch_config = watch_config or WatchConfig()

    handler = PngHandler(
        watermark_config=watermark_config,
        compression_config=compression_config,
        watch_config=watch_config,
        dry_run=dry_run,
        verbose=verbose,
    )

    observer = Observer()
    for directory in directories:
        dir_path = Path(directory).expanduser().resolve()
        if not dir_path.is_dir():
            logger.warning("Skipping non-existent directory: %s", dir_path)
            continue
        observer.schedule(handler, str(dir_path), recursive=watch_config.recursive)
        logger.info("Watching: %s", dir_path)

    stop_event = threading.Event()

    def _shutdown(signum, frame):
        logger.info("Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    observer.start()
    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    finally:
        observer.stop()
        observer.join()
