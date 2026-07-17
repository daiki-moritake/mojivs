"""Optional FreeType rasterizer backend — faster, and free of the cairo dependency.

Selected with ``render(..., backend="freetype")``. mojivs still owns IVS
resolution and shaping; FreeType only rasterizes the already-placed glyphs,
interpreting each outline and anti-aliasing it in C. This is roughly 2.5x faster
than the cairo backend on the "load once, render many" path and needs no system
cairo library (``freetype-py`` ships self-contained wheels).

Coordinate systems
------------------
mojivs' per-glyph affine maps font units (y-up) to device pixels (y-down)::

    dx = a*px + c*py + e
    dy = b*px + d*py + f

FreeType works in a y-up device space, so it is fed the 2x2 matrix
``M = (xx=a, xy=c, yx=-b, yy=-d)`` — the same linear map with the y axis flipped
— and the resulting y-up bitmap is placed into the y-down canvas at
``(floor(e) + bitmap_left, floor(f) - bitmap_top)``. The face is sized so one
font unit equals one unit (``set_pixel_sizes(0, units_per_em)``); all scale then
lives in ``M``, so a single face serves every render size.

Scope: native fill and background across every orientation (horizontal,
vertical, rotated, tate-chu-yoko). Stroked text is handled by the cairo backend
(see :func:`mojivs.render.render`), which falls back automatically.
"""

from __future__ import annotations

import ctypes
import io
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

from .colors import RGBA

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .shaping import PlacedGlyph

    # freetype-py ships no type stubs and builds its FT_* constants dynamically,
    # so give the type checker an opaque view instead of the real partial module.
    freetype: Any
else:
    try:
        import freetype
    except ImportError:  # pragma: no cover - exercised only without freetype-py
        freetype = None

# Unhinted outlines match cairo's outline fill; RENDER produces an 8-bit
# anti-aliased coverage bitmap.
_LOAD_FLAGS = None


def _load_flags() -> int:
    global _LOAD_FLAGS
    if _LOAD_FLAGS is None:
        _LOAD_FLAGS = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING
    return _LOAD_FLAGS


def _require_freetype() -> None:
    if freetype is None:
        raise RuntimeError(
            "the 'freetype' backend requires freetype-py; install it with "
            "'pip install mojivs[freetype]'"
        )


def _face(font):
    """Return a cached, em-normalized ``freetype.Face`` for ``font``."""
    if font._ft_face is None:
        _require_freetype()
        face = freetype.Face(io.BytesIO(font.font_data()))
        # One font unit -> one unit; per-glyph scale lives in the matrix.
        face.set_pixel_sizes(0, font.units_per_em)
        font._ft_face = face
    return font._ft_face


def _fixed16(value: float) -> int:
    """Convert to FreeType 16.16 fixed point."""
    return int(round(value * 65536))


def _bitmap_coverage(bitmap) -> np.ndarray:
    """Zero-copy ``(rows, pitch)`` uint8 view of a FreeType bitmap buffer.

    Avoids freetype-py's ``bitmap.buffer`` property, which materializes a Python
    list element by element (the dominant per-glyph cost). The view references
    FreeType's internal glyph-slot buffer, so it is consumed immediately, before
    the next ``load_glyph`` overwrites it.
    """
    rows, pitch = bitmap.rows, bitmap.pitch
    count = rows * abs(pitch)
    pointer = ctypes.cast(bitmap._FT_Bitmap.buffer, ctypes.POINTER(ctypes.c_ubyte))
    return np.ctypeslib.as_array(pointer, shape=(count,)).reshape(rows, pitch)


def rasterize_ft(
    font,
    glyphs: Iterable[PlacedGlyph],
    width: int,
    height: int,
    *,
    fill: RGBA,
    background: RGBA,
) -> Image.Image:
    """Rasterize placed glyphs with FreeType into a straight-alpha RGBA image.

    Mirrors :func:`mojivs.render._rasterize` (minus stroking) so both entry
    points can share it.

    Args:
        font: The :class:`~mojivs.font.IVSFont` the glyphs were shaped with.
        glyphs: Placed glyphs to draw (each carrying its device-space affine).
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        fill: Fill color as an ``(r, g, b, a)`` float tuple in ``0..1``.
        background: Background color as an ``(r, g, b, a)`` float tuple.
    """
    _require_freetype()
    face = _face(font)
    ttfont = font._ttfont
    flags = _load_flags()

    width = max(width, 1)
    height = max(height, 1)

    # Single fill color, so glyph coverage accumulates in one alpha plane and the
    # color is applied once at the end.
    coverage = np.zeros((height, width), np.float32)

    for pg in glyphs:
        gid = ttfont.getGlyphID(pg.glyph_name)
        a, b, c, d, e, f = pg.transform

        matrix = freetype.Matrix(_fixed16(a), _fixed16(c), _fixed16(-b), _fixed16(-d))
        # Fractional pen offset as a sub-pixel translate (26.6, y-up) so
        # anti-aliasing lands where the cairo backend places it.
        floor_e = np.floor(e)
        floor_f = np.floor(f)
        delta = freetype.Vector(int(round((e - floor_e) * 64)), int(round(-(f - floor_f) * 64)))
        face.set_transform(matrix, delta)
        face.load_glyph(gid, flags)

        slot = face.glyph
        bitmap = slot.bitmap
        w, rows = bitmap.width, bitmap.rows
        if w == 0 or rows == 0:
            continue
        cov = _bitmap_coverage(bitmap)[:, :w].astype(np.float32) / 255.0

        left = int(floor_e) + slot.bitmap_left
        top = int(floor_f) - slot.bitmap_top

        x0, y0 = max(left, 0), max(top, 0)
        x1, y1 = min(left + w, width), min(top + rows, height)
        if x0 >= x1 or y0 >= y1:
            continue
        src = cov[y0 - top : y1 - top, x0 - left : x1 - left]
        dst = coverage[y0:y1, x0:x1]
        # Alpha "over": out = src + dst * (1 - src).
        coverage[y0:y1, x0:x1] = src + dst * (1.0 - src)

    return _compose(coverage, fill, background, width, height)


def _compose(
    coverage: np.ndarray,
    fill: RGBA,
    background: RGBA,
    width: int,
    height: int,
) -> Image.Image:
    """Composite fill (masked by ``coverage``) over ``background`` -> RGBA image."""
    fr, fg, fb, fa_max = fill
    br, bg, bb, ba = background

    # Work in premultiplied float, then un-premultiply to straight uint8.
    bg_pm = np.array([br * ba, bg * ba, bb * ba, ba], np.float32)
    canvas = np.empty((height, width, 4), np.float32)
    canvas[:] = bg_pm

    fa = coverage * fa_max  # per-pixel fill alpha
    fill_pm = np.stack([fr * fa, fg * fa, fb * fa, fa], axis=-1)
    canvas = fill_pm + canvas * (1.0 - fa)[..., None]

    out = np.zeros((height, width, 4), np.uint8)
    alpha = canvas[..., 3]
    out[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    nonzero = alpha > 0
    if nonzero.any():
        inv = np.zeros_like(alpha)
        inv[nonzero] = 255.0 / alpha[nonzero]
        for ch in range(3):
            out[..., ch] = np.clip(canvas[..., ch] * inv, 0, 255).astype(np.uint8)
    return Image.fromarray(out)
