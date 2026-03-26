"""Lossless PNG compression using pyoxipng."""

from __future__ import annotations

from pathlib import Path

import oxipng


def compress_png(
    path: str | Path,
    output: str | Path | None = None,
    level: int = 4,
    strip: str = "safe",
    use_zopfli: bool = False,
    zopfli_iterations: int = 15,
) -> int:
    """Losslessly compress a PNG file.

    Args:
        path: Input PNG file path.
        output: Output path. If None, overwrites the input file.
        level: Compression level 0-6. Higher = slower + smaller.
        strip: Metadata stripping: "none", "safe", or "all".
        use_zopfli: Use Zopfli deflater for maximum compression (slower).
        zopfli_iterations: Zopfli iteration count (only if use_zopfli=True).

    Returns:
        Bytes saved (positive = file got smaller).
    """
    path = Path(path)
    original_size = path.stat().st_size

    strip_chunks = {
        "none": oxipng.StripChunks.none(),
        "safe": oxipng.StripChunks.safe(),
        "all": oxipng.StripChunks.all(),
    }.get(strip, oxipng.StripChunks.safe())

    deflater = (
        oxipng.Deflaters.zopfli(zopfli_iterations)
        if use_zopfli
        else None
    )

    kwargs = {
        "level": level,
        "strip": strip_chunks,
        "bit_depth_reduction": True,
        "color_type_reduction": True,
        "palette_reduction": True,
    }
    if deflater is not None:
        kwargs["deflate"] = deflater

    out_path = str(output) if output else None
    oxipng.optimize(str(path), out_path, **kwargs)

    result_path = Path(output) if output else path
    new_size = result_path.stat().st_size
    return original_size - new_size
