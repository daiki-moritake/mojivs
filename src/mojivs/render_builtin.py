"""Built-in rasterizer backend — pure Python + Pillow, no numpy/cairo/freetype.

This is the default backend. It exists so a bare ``pip install mojivs`` (which
pulls only ``fonttools`` and ``pillow``) can render filled text with no system
libraries and no C extensions beyond Pillow itself. mojivs still owns IVS
resolution and shaping; this module only rasterizes the already-placed glyphs.

How it works
------------
Each placed glyph's outline (a cached pen recording in font units) is replayed
through :class:`_FlatteningPen`, which applies the glyph's device-space affine
and flattens every Bézier into line segments — yielding closed polygonal
contours in device pixels. Those contours are filled with a **non-zero winding**
scanline routine at ``_SSAA``× resolution and box-downsampled by Pillow, which
turns per-sample coverage into an anti-aliased 8-bit alpha mask. The mask tints
the fill color and is composited over the canvas with Pillow's C ``alpha_composite``.

Non-zero winding (not even-odd) is used so counters render as holes *and*
deliberately overlapping strokes — common in CJK fonts built from overlapping
components — stay solid.

Scope: fill + background for every orientation. Stroking is not implemented
here; :func:`mojivs.render.render` routes stroked text to the cairo backend.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import replayRecording
from PIL import Image

from .colors import RGBA

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .font import IVSFont
    from .shaping import PlacedGlyph

# Supersampling factor per axis. Coverage is computed on an _SSAA×_SSAA grid and
# box-averaged down, so each output pixel gets up to _SSAA² coverage levels. 4 is
# a good speed/quality trade-off (16 levels); higher smooths edges at more cost.
_SSAA = 4

# Bézier flatness tolerance, in device pixels *before* supersampling. Curves are
# subdivided until they deviate less than this from a straight chord; the value
# is kept below one supersample step (1/_SSAA px) so faceting stays sub-pixel.
_FLATNESS = 0.2 / _SSAA
_MAX_DEPTH = 12  # recursion cap on cubic subdivision (guards pathological curves)

# Pillow 9.1 moved the resampling filters onto ``Image.Resampling``; fall back to
# the module-level constant so Pillow 9.0 keeps working. BOX is an area-average
# downsample, which turns supersampled coverage into anti-aliased alpha.
_resampling: Any = getattr(Image, "Resampling", Image)
_BOX = _resampling.BOX

_Point = tuple[float, float]


def _mid(a: _Point, b: _Point) -> _Point:
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)


def _cubic_flat_enough(p0: _Point, p1: _Point, p2: _Point, p3: _Point, tol: float) -> bool:
    """Classic flatness test: max control-point deviation from the p0→p3 chord."""
    ux = 3.0 * p1[0] - 2.0 * p0[0] - p3[0]
    uy = 3.0 * p1[1] - 2.0 * p0[1] - p3[1]
    vx = 3.0 * p2[0] - p0[0] - 2.0 * p3[0]
    vy = 3.0 * p2[1] - p0[1] - 2.0 * p3[1]
    return max(ux * ux, vx * vx) + max(uy * uy, vy * vy) <= 16.0 * tol * tol


def _flatten_cubic(
    p0: _Point,
    p1: _Point,
    p2: _Point,
    p3: _Point,
    out: list[_Point],
    depth: int = 0,
) -> None:
    """Append the flattened cubic p0..p3 to ``out`` (excludes p0, includes p3)."""
    if depth >= _MAX_DEPTH or _cubic_flat_enough(p0, p1, p2, p3, _FLATNESS):
        out.append(p3)
        return
    p01 = _mid(p0, p1)
    p12 = _mid(p1, p2)
    p23 = _mid(p2, p3)
    p012 = _mid(p01, p12)
    p123 = _mid(p12, p23)
    mid = _mid(p012, p123)
    _flatten_cubic(p0, p01, p012, mid, out, depth + 1)
    _flatten_cubic(mid, p123, p23, p3, out, depth + 1)


class _FlatteningPen(BasePen):
    """Replays a glyph recording into device-space polygonal contours.

    ``BasePen`` normalizes quadratic segments into cubics for us, so only
    :meth:`_curveToOne` needs to flatten. Every point is mapped to device pixels
    by the placed glyph's affine before it is stored, so the resulting contours
    are ready to rasterize.
    """

    def __init__(self, glyph_set, transform):
        super().__init__(glyph_set)
        self._t = transform
        self.contours: list[list[_Point]] = []
        # Reassigned by each _moveTo; the initial empty list is a harmless sink
        # for the (malformed) case of a segment arriving before any moveTo.
        self._cur: list[_Point] = []
        self._pt: _Point = (0.0, 0.0)

    def _moveTo(self, pt):
        p = self._t.transformPoint(pt)
        self._cur = [p]
        self.contours.append(self._cur)
        self._pt = p

    def _lineTo(self, pt):
        p = self._t.transformPoint(pt)
        self._cur.append(p)
        self._pt = p

    def _curveToOne(self, pt1, pt2, pt3):
        p1 = self._t.transformPoint(pt1)
        p2 = self._t.transformPoint(pt2)
        p3 = self._t.transformPoint(pt3)
        _flatten_cubic(self._pt, p1, p2, p3, self._cur)
        self._pt = p3


def _glyph_contours(font: IVSFont, pg: PlacedGlyph) -> list[list[_Point]]:
    pen = _FlatteningPen(font.glyph_set, pg.transform)
    replayRecording(font.glyph_outline(pg.glyph_name), pen)
    return pen.contours


def _fill_mask(contours: list[list[_Point]]) -> tuple[Image.Image, int, int] | None:
    """Non-zero fill ``contours`` into an anti-aliased ``L`` mask.

    Returns ``(mask, ox, oy)`` where ``(ox, oy)`` is the mask's top-left in
    device pixels, or ``None`` if the contours enclose no area.
    """
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for contour in contours:
        for x, y in contour:
            if x < minx:
                minx = x
            if x > maxx:
                maxx = x
            if y < miny:
                miny = y
            if y > maxy:
                maxy = y
    if minx > maxx:
        return None

    # One pixel of margin so anti-aliased edges are never clipped by the tile.
    ox = math.floor(minx) - 1
    oy = math.floor(miny) - 1
    w = math.ceil(maxx) + 1 - ox
    h = math.ceil(maxy) + 1 - oy
    if w <= 0 or h <= 0:
        return None

    ss = _SSAA
    width_ss = w * ss
    height_ss = h * ss

    # Bucket each edge's scanline crossings by supersampled row. Edges carry a
    # winding direction (+1 downward, -1 upward) so the fill can honour non-zero.
    rows: list[list[tuple[float, int]]] = [[] for _ in range(height_ss)]
    for contour in contours:
        n = len(contour)
        if n < 2:
            continue
        for i in range(n):
            ax, ay = contour[i]
            bx, by = contour[(i + 1) % n]  # closing edge wraps to the start
            # Transform into supersampled tile space.
            ay = (ay - oy) * ss
            by = (by - oy) * ss
            if ay == by:
                continue  # horizontal edges contribute no crossings
            ax = (ax - ox) * ss
            bx = (bx - ox) * ss
            if ay < by:
                y_top, y_bot, x_top, wind = ay, by, ax, 1
                dxdy = (bx - ax) / (by - ay)
            else:
                y_top, y_bot, x_top, wind = by, ay, bx, -1
                dxdy = (ax - bx) / (ay - by)

            y_start = max(0, math.ceil(y_top - 0.5))
            y_end = min(height_ss, math.ceil(y_bot - 0.5))
            for yy in range(y_start, y_end):
                sample_y = yy + 0.5
                rows[yy].append((x_top + (sample_y - y_top) * dxdy, wind))

    coverage = bytearray(width_ss * height_ss)
    for yy, crossings in enumerate(rows):
        if not crossings:
            continue
        crossings.sort()
        wind = 0
        base = yy * width_ss
        for k in range(len(crossings) - 1):
            wind += crossings[k][1]
            if wind == 0:
                continue
            a = crossings[k][0]
            b = crossings[k + 1][0]
            xa = max(0, math.ceil(a - 0.5))
            xb = min(width_ss, math.ceil(b - 0.5))
            if xb > xa:
                coverage[base + xa : base + xb] = b"\xff" * (xb - xa)

    mask_ss = Image.frombytes("L", (width_ss, height_ss), bytes(coverage))
    mask = mask_ss.resize((w, h), _BOX)
    return mask, ox, oy


def _composite(
    canvas: Image.Image,
    mask: Image.Image,
    ox: int,
    oy: int,
    fill_rgb: tuple[int, int, int],
    fill_alpha: float,
    width: int,
    height: int,
) -> None:
    """Composite ``fill_rgb`` (masked by ``mask``) over ``canvas`` at ``(ox, oy)``."""
    w, h = mask.size
    if fill_alpha < 1.0:
        mask = mask.point(lambda v: int(v * fill_alpha + 0.5))

    # Clip the tile to the canvas so glyphs overhanging the edges don't error.
    dx0, dy0 = max(ox, 0), max(oy, 0)
    dx1, dy1 = min(ox + w, width), min(oy + h, height)
    if dx0 >= dx1 or dy0 >= dy1:
        return
    if (dx0, dy0, dx1, dy1) != (ox, oy, ox + w, oy + h):
        mask = mask.crop((dx0 - ox, dy0 - oy, dx1 - ox, dy1 - oy))

    tile = Image.new("RGBA", (dx1 - dx0, dy1 - dy0), fill_rgb + (0,))
    tile.putalpha(mask)
    region = canvas.crop((dx0, dy0, dx1, dy1))
    canvas.paste(Image.alpha_composite(region, tile), (dx0, dy0))


def _rgba255(color: RGBA) -> tuple[int, int, int, int]:
    r, g, b, a = color
    return (round(r * 255), round(g * 255), round(b * 255), round(a * 255))


def rasterize_builtin(
    font: IVSFont,
    glyphs: Iterable[PlacedGlyph],
    width: int,
    height: int,
    *,
    fill: RGBA,
    background: RGBA,
) -> Image.Image:
    """Rasterize placed glyphs to a straight-alpha RGBA image, pure-Python.

    Mirrors :func:`mojivs.render._rasterize` (minus stroking) so the cairo,
    freetype and builtin backends all return equivalent images.

    Args:
        font: The :class:`~mojivs.font.IVSFont` the glyphs were shaped with.
        glyphs: Placed glyphs to draw (each carrying its device-space affine).
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        fill: Fill color as an ``(r, g, b, a)`` float tuple in ``0..1``.
        background: Background color as an ``(r, g, b, a)`` float tuple.
    """
    width = max(width, 1)
    height = max(height, 1)
    canvas = Image.new("RGBA", (width, height), _rgba255(background))

    fr, fg, fb, fa = fill
    fill_rgb = (round(fr * 255), round(fg * 255), round(fb * 255))

    for pg in glyphs:
        result = _fill_mask(_glyph_contours(font, pg))
        if result is None:
            continue
        mask, ox, oy = result
        _composite(canvas, mask, ox, oy, fill_rgb, fa, width, height)

    return canvas
