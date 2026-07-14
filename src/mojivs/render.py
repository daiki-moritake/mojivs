"""Rasterizer — turns shaped glyph runs into :class:`PIL.Image.Image` objects.

This is the "A" layer: it depends on cairo/Pillow/numpy and builds on top of the
shaping layer (:mod:`mojivs.shaping`). Two entry points are provided:

* :func:`render` — natural layout (horizontal or vertical, multi-line) at a
  given em pixel size. This is what most callers want.
* :func:`render_to_box` — fit a single horizontal line into an exact
  ``(width, height)`` pixel box, compressing when too wide and justifying
  (spreading the characters) when too narrow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cairo
import numpy as np
from fontTools.pens.basePen import BasePen
from PIL import Image

from .colors import Color, RGBA, to_rgba
from .shaping import Align, Direction, PlacedGlyph, shape

if TYPE_CHECKING:
    from .font import IVSFont


class _CairoPen(BasePen):
    """Draws a glyph outline into a cairo context in device space.

    Font-unit points ``(x, y)`` (y-up) are mapped to device pixels
    ``(ox + x*sx, oy - y*sy)`` (y-down), so the caller controls position and
    scale while stroke widths stay in device pixels.
    """

    def __init__(self, glyph_set, ctx, sx, sy, ox, oy):
        super().__init__(glyph_set)
        self._ctx = ctx
        self._sx = sx
        self._sy = sy
        self._ox = ox
        self._oy = oy

    def _pt(self, pt):
        return (self._ox + pt[0] * self._sx, self._oy - pt[1] * self._sy)

    def _moveTo(self, pt):
        self._ctx.move_to(*self._pt(pt))

    def _lineTo(self, pt):
        self._ctx.line_to(*self._pt(pt))

    def _curveToOne(self, pt1, pt2, pt3):
        x1, y1 = self._pt(pt1)
        x2, y2 = self._pt(pt2)
        x3, y3 = self._pt(pt3)
        self._ctx.curve_to(x1, y1, x2, y2, x3, y3)

    def _closePath(self):
        self._ctx.close_path()


def _surface_to_image(surface: cairo.ImageSurface) -> Image.Image:
    """Convert a cairo ARGB32 surface to a straight-alpha RGBA Pillow image.

    Cairo stores ARGB32 as premultiplied BGRA; this un-premultiplies so that
    anti-aliased edges keep their true color instead of darkening.
    """
    width = surface.get_width()
    height = surface.get_height()
    stride = surface.get_stride()
    buf = (
        np.frombuffer(surface.get_data(), np.uint8)
        .reshape(height, stride // 4, 4)[:, :width, :]
        .astype(np.float32)
    )
    b, g, r, a = buf[..., 0], buf[..., 1], buf[..., 2], buf[..., 3]
    alpha = np.where(a > 0, a, 1.0)
    out = np.stack(
        [
            np.clip(r * 255.0 / alpha, 0, 255),
            np.clip(g * 255.0 / alpha, 0, 255),
            np.clip(b * 255.0 / alpha, 0, 255),
            a,
        ],
        axis=-1,
    ).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def _rasterize(
    font: "IVSFont",
    glyphs,
    width: int,
    height: int,
    *,
    fill: RGBA,
    stroke: RGBA,
    stroke_width: float,
    background: RGBA,
) -> Image.Image:
    """Rasterize placed glyphs onto a single surface and return an RGBA image."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(width, 1), max(height, 1))
    ctx = cairo.Context(surface)

    if background[3] > 0:
        ctx.set_source_rgba(*background)
        ctx.paint()

    glyph_set = font.glyph_set
    for pg in glyphs:
        pen = _CairoPen(glyph_set, ctx, pg.x_scale, pg.y_scale, pg.x, pg.y)
        glyph_set[pg.glyph_name].draw(pen)

        if stroke_width > 0 and stroke[3] > 0:
            ctx.set_line_width(stroke_width)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.set_source_rgba(*stroke)
            ctx.stroke_preserve()

        ctx.set_source_rgba(*fill)
        ctx.fill()

    return _surface_to_image(surface)


def render(
    font: "IVSFont",
    text: str,
    *,
    size: int = 64,
    direction: Direction = "horizontal",
    align: Align = "start",
    line_spacing: float = 1.0,
    letter_spacing: float = 0.0,
    padding: int = 0,
    color: Color = "#000000",
    stroke: Color = None,
    stroke_width: float = 0.0,
    background: Color = None,
    on_missing: str = "raise",
) -> Image.Image:
    """Render ``text`` to an RGBA image using the font's natural metrics.

    Args:
        font: The :class:`~mojivs.font.IVSFont` to draw with.
        text: The text to render. ``\\n`` starts a new line (horizontal) or
            column (vertical). May contain IVS variation selectors.
        size: Em size in pixels. A full-width CJK glyph is about ``size`` px.
        direction: ``"horizontal"`` or ``"vertical"``.
        align: Cross-axis alignment of shorter lines/columns.
        line_spacing: Multiplier applied to the line/column advance.
        color: Fill color (hex string or 0–255 RGB/RGBA tuple).
        stroke: Outline color. If ``None``, no outline is drawn.
        stroke_width: Outline width in pixels.
        background: Background fill. If ``None``, the background is transparent.
        letter_spacing: Extra space between characters, in pixels.
        padding: Transparent padding around the text, in pixels.
        on_missing: ``"raise"`` (default) or ``"skip"`` for unsupported clusters.

    Returns:
        A :class:`PIL.Image.Image` in ``RGBA`` mode.
    """
    pad = padding + stroke_width / 2.0
    shaped = shape(
        font,
        text,
        size=size,
        direction=direction,
        align=align,
        line_spacing=line_spacing,
        letter_spacing=letter_spacing,
        padding=pad,
        on_missing=on_missing,
    )
    return _rasterize(
        font,
        shaped.glyphs,
        shaped.width,
        shaped.height,
        fill=to_rgba(color),
        stroke=to_rgba(stroke),
        stroke_width=stroke_width,
        background=to_rgba(background),
    )


def render_to_box(
    font: "IVSFont",
    text: str,
    box: tuple[int, int],
    *,
    color: Color = "#000000",
    stroke: Color = None,
    stroke_width: float = 0.0,
    background: Color = None,
    on_missing: str = "raise",
) -> Image.Image:
    """Render a single horizontal line fitted into ``box = (width, height)`` px.

    The line height is scaled to ``height``. If the text is wider than ``width``
    it is compressed horizontally; if narrower, the characters are spread evenly
    (justified) to fill the width. The returned image is exactly ``box`` pixels.
    """
    box_w, box_h = box
    run = font.resolve_run(text, on_missing=on_missing)

    inner_h = max(box_h - stroke_width, 1.0)
    scale_y = inner_h / font.line_height

    glyph_names = [glyph_name for _, glyph_name in run]
    natural_width = sum(font.advance_width(g) * scale_y for g in glyph_names)
    inner_w = max(box_w - stroke_width, 1.0)

    scale_x = scale_y
    extra_spacing = 0.0
    if natural_width > inner_w and natural_width > 0:
        # Too wide: squash each glyph horizontally to fit.
        scale_x = scale_y * (inner_w / natural_width)
    elif glyph_names:
        # Too narrow: distribute the slack as even inter-character spacing.
        extra_spacing = (inner_w - natural_width) / len(glyph_names)

    baseline = stroke_width / 2.0 + font.ascent * scale_y
    x = stroke_width / 2.0 + extra_spacing / 2.0

    placed: list[PlacedGlyph] = []
    for cluster, glyph_name in run:
        placed.append(PlacedGlyph(glyph_name, cluster, x, baseline, scale_x, scale_y))
        x += font.advance_width(glyph_name) * scale_x + extra_spacing

    return _rasterize(
        font,
        placed,
        box_w,
        box_h,
        fill=to_rgba(color),
        stroke=to_rgba(stroke),
        stroke_width=stroke_width,
        background=to_rgba(background),
    )
