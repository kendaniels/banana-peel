"""Shared file processing pipeline."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from banana_peel.compressor import compress_png
from banana_peel.config import CompressionConfig, RenameConfig, ResizeConfig, WatermarkConfig
from banana_peel.watermark import has_watermark, remove_watermark

logger = logging.getLogger("banana_peel")


@dataclass
class ProcessResult:
    """Result of processing a single file."""

    output_path: Path
    watermark_removed: bool = False
    bytes_saved: int = 0
    ai_renamed: bool = False


def process_file(
    file_path: Path,
    watermark_config: WatermarkConfig,
    compression_config: CompressionConfig,
    rename_config: RenameConfig | None = None,
    resize_config: ResizeConfig | None = None,
    destination: Path | None = None,
    dry_run: bool = False,
) -> ProcessResult | None:
    """Run the full pipeline: watermark removal -> resize -> compression -> rename -> move.

    Returns ProcessResult on success, or None if dry_run.
    """
    rename_config = rename_config or RenameConfig()
    resize_config = resize_config or ResizeConfig()

    # --- Watermark removal ---
    watermark_removed = False
    if watermark_config.enabled and has_watermark(file_path):
        if dry_run:
            return None
        cleaned = remove_watermark(file_path)
        cleaned.save(file_path, "PNG")
        watermark_removed = True

    if dry_run:
        return None

    # --- Resize ---
    if resize_config.enabled:
        from PIL import Image

        img = Image.open(file_path)
        w, h = img.size
        max_dim = resize_config.max_dimension
        if w > max_dim or h > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            img.save(file_path, "PNG")

    # --- Compression ---
    bytes_saved = 0
    if compression_config.enabled:
        bytes_saved = compress_png(
            file_path,
            level=compression_config.level,
            strip=compression_config.strip_metadata,
            use_zopfli=compression_config.use_zopfli,
            zopfli_iterations=compression_config.zopfli_iterations,
        )

    # --- Rename ---
    ai_renamed = False
    new_name = file_path.stem + "_peeled" + file_path.suffix

    if rename_config.enabled:
        # Try AI rename (import here to avoid circular deps and optional dep issues)
        try:
            from banana_peel.renamer import RetryingRenamer, get_renamer, slugify

            renamer = get_renamer(rename_config)
            if renamer is not None:
                renamer = RetryingRenamer(renamer)
                description = renamer.describe(file_path)
                if description:
                    slug = slugify(description)
                    # Check for collision in the target directory
                    target_dir = destination if destination else file_path.parent
                    candidate = target_dir / (slug + file_path.suffix)
                    if candidate.exists():
                        from datetime import datetime

                        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                        slug = f"{slug}-{ts}"
                    new_name = slug + file_path.suffix
                    ai_renamed = True
        except Exception:
            logger.warning("AI rename failed for %s, falling back to _peeled", file_path.name)

    renamed_path = file_path.with_name(new_name)
    file_path.rename(renamed_path)

    # --- Move to destination ---
    final_path = renamed_path
    if destination:
        destination.mkdir(parents=True, exist_ok=True)
        dest_path = destination / renamed_path.name
        shutil.move(str(renamed_path), str(dest_path))
        final_path = dest_path

    return ProcessResult(
        output_path=final_path,
        watermark_removed=watermark_removed,
        bytes_saved=bytes_saved,
        ai_renamed=ai_renamed,
    )
