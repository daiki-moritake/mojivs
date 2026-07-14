"""Rasterizer — turns resolved glyph runs into :class:`PIL.Image.Image` objects.

This is the "A" layer: it depends on cairo/Pillow/numpy and builds on top of the
dependency-light resolver. Two entry points are provided:

* :func:`render` — natural horizontal layout using the font's own advance
  widths, at a given em pixel size. This is what most callers want.
* :func:`render_to_box` — fit the text into an exact ``(width, height)`` pixel
  box, compressing when the text is too wide and justifying (spreading the
  characters) when it is too narrow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, Union

import cairo
import numpy as np
from fontTools.pens.basePen import BasePen
from PIL import Image

if TYPE_CHECKING:
    from .font import IVSFont

Color = Union[str, Sequence[int], None]
RGBA = tuple[float, float, float, float]

_TRANSPARENT: RGBA = (0.0, 0.0, 0.0, 0.0)


def _to_rgba(color: Color, default: RGBA = _TRANSPARENT) -> RGBA:
    """Normalize a color to ``(r, g, b, a)`` floats in the range 0.0–1.0.

    Accepts ``None`` (returns ``default``), a ``"#rgb"`` / ``"#rrggbb"`` /
    ``"#rrggbbaa"`` hex string, or an ``(r, g, b)`` / ``(r, g, b, a)`` sequence
    of 0–255 integers.
    """
    if color is None:
        return default

    if isinstance(color, str):
        h = color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            raise ValueError(f"invalid hex color: {color!r}")
        values = [int(h[i : i + 2], 16) for i in range(0, len(h), 2)]
    else:
        values = list(color)

    if len(values) == 3:
        values.append(255)
    if len(values) != 4:
        raise ValueError(f"color must have 3 or 4 components, got {color!r}")
    r, g, b, a = values
    return (r / 255.0, g / 255.0, b / 255.0, a / 255.0)


class _CairoPen(BasePen):
    """A pen that draws a glyph outline into a cairo context in device space.

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


def _draw_run(
    font: "IVSFont",
    glyph_names: list[str],
    *,
    width: int,
    height: int,
    scale_x: float,
    scale_y: float,
    baseline: float,
    positions_px: list[float],
    fill: RGBA,
    stroke: RGBA,
    stroke_width: float,
    background: RGBA,
) -> Image.Image:
    """Rasterize a run of glyphs onto a single surface and return an RGBA image."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(width, 1), max(height, 1))
    ctx = cairo.Context(surface)

    if background[3] > 0:
        ctx.set_source_rgba(*background)
        ctx.paint()

    glyph_set = font.glyph_set
    for glyph_name, x in zip(glyph_names, positions_px):
        pen = _CairoPen(glyph_set, ctx, scale_x, scale_y, x, baseline)
        glyph_set[glyph_name].draw(pen)

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
    color: Color = "#000000",
    stroke: Color = None,
    stroke_width: float = 0.0,
    background: Color = None,
    letter_spacing: float = 0.0,
    padding: int = 0,
    on_missing: str = "raise",
) -> Image.Image:
    """Render ``text`` to an RGBA image using the font's natural metrics.

    Args:
        font: The :class:`~mojivs.font.IVSFont` to draw with.
        text: The text to render (may contain IVS variation selectors).
        size: Em size in pixels. A full-width CJK glyph is about ``size`` px wide.
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
    run = font.resolve_run(text, on_missing=on_missing)
    scale = size / font.units_per_em

    glyph_names = [glyph_name for _, glyph_name in run]
    advances_px = [font.advance_width(g) * scale for g in glyph_names]

    pad = padding + (stroke_width / 2.0)
    positions_px: list[float] = []
    x = pad
    for adv in advances_px:
        positions_px.append(x)
        x += adv + letter_spacing
    content_width = x - letter_spacing - pad if advances_px else 0.0

    width = int(round(content_width + 2 * pad))
    height = int(round(font.line_height * scale + 2 * pad))
    baseline = pad + font.ascent * scale

    return _draw_run(
        font,
        glyph_names,
        width=width,
        height=height,
        scale_x=scale,
        scale_y=scale,
        baseline=baseline,
        positions_px=positions_px,
        fill=_to_rgba(color),
        stroke=_to_rgba(stroke),
        stroke_width=stroke_width,
        background=_to_rgba(background),
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
    """Render ``text`` fitted into an exact ``box = (width, height)`` in pixels.

    The line height is scaled to ``height``. If the text is wider than ``width``
    it is compressed horizontally; if narrower, the characters are spread evenly
    (justified) to fill the width. The returned image is exactly ``box`` pixels.
    """
    box_w, box_h = box
    run = font.resolve_run(text, on_missing=on_missing)

    inner_h = max(box_h - stroke_width, 1.0)
    scale_y = inner_h / font.line_height

    glyph_names = [glyph_name for _, glyph_name in run]
    natural_advances = [font.advance_width(g) * scale_y for g in glyph_names]
    natural_width = sum(natural_advances)

    inner_w = max(box_w - stroke_width, 1.0)

    scale_x = scale_y
    extra_spacing = 0.0
    if natural_width > inner_w and natural_width > 0:
        # Too wide: squash each glyph horizontally to fit.
        scale_x = scale_y * (inner_w / natural_width)
    elif glyph_names:
        # Too narrow: distribute the slack as even inter-character spacing.
        extra_spacing = (inner_w - natural_width) / len(glyph_names)

    pad_x = stroke_width / 2.0
    baseline = stroke_width / 2.0 + font.ascent * scale_y

    positions_px: list[float] = []
    advances_px = [font.advance_width(g) * scale_x for g in glyph_names]
    x = pad_x + extra_spacing / 2.0
    for adv in advances_px:
        positions_px.append(x)
        x += adv + extra_spacing

    return _draw_run(
        font,
        glyph_names,
        width=box_w,
        height=box_h,
        scale_x=scale_x,
        scale_y=scale_y,
        baseline=baseline,
        positions_px=positions_px,
        fill=_to_rgba(color),
        stroke=_to_rgba(stroke),
        stroke_width=stroke_width,
        background=_to_rgba(background),
    )
