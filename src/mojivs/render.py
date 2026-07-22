"""Rasterizer — turns shaped glyph runs into :class:`PIL.Image.Image` objects.

This is the "A" layer: it builds on the shaping layer (:mod:`mojivs.shaping`)
and rasterizes with Pillow/numpy plus one of two optional backends. Two entry
points are provided:

* :func:`render` — natural layout (horizontal or vertical, multi-line) at a
  given em pixel size. This is what most callers want.
* :func:`render_to_box` — fit a single horizontal line into an exact
  ``(width, height)`` pixel box, compressing when too wide and justifying
  (spreading the characters) when too narrow.

The default ``backend="builtin"`` is a pure-Python + Pillow rasterizer that
needs no numpy, cairo or freetype (see :mod:`mojivs.render_builtin`), so a bare
``pip install mojivs`` can render filled text. ``backend="cairo"`` and
``backend="freetype"`` are optional accelerators; cairo also handles all stroked
text, and any backend automatically routes to cairo when a stroke is requested.
Optional backends are imported lazily so a bare install needs none of them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from fontTools.misc.transform import Transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import replayRecording
from PIL import Image

from .colors import RGBA, Color, to_rgba
from .render_builtin import rasterize_builtin
from .render_ft import rasterize_ft
from .shaping import Align, Direction, Orientation, PlacedGlyph, shape_for_output

if TYPE_CHECKING:
    from .font import IVSFont

    # pycairo ships no type stubs; treat it as an opaque module and tolerate the
    # ImportError fallback (the freetype backend does not need it).
    cairo: Any
else:
    try:
        import cairo
    except ImportError:  # pragma: no cover - exercised only without pycairo
        cairo = None

# Rasterizer backend selector. ``"builtin"`` (default) is the dependency-free
# pure-Python path (see render_builtin); ``"cairo"`` and ``"freetype"`` are
# optional accelerators. Only cairo can stroke, so builtin/freetype fall back to
# cairo whenever a stroke is requested.
Backend = Literal["builtin", "cairo", "freetype"]
_BACKENDS = ("builtin", "cairo", "freetype")


def _require_cairo() -> None:
    if cairo is None:
        raise RuntimeError(
            "the 'cairo' backend requires pycairo; install it with "
            "'pip install mojivs[cairo]', or use backend='freetype' "
            "(pip install mojivs[freetype])"
        )


def _stroke_active(stroke: RGBA, stroke_width: float) -> bool:
    """Whether a visible outline would be drawn for these stroke settings."""
    return stroke_width > 0 and stroke[3] > 0


class _CairoPen(BasePen):
    """Draws a glyph outline into a cairo context in device space.

    Font-unit points (y-up) are mapped to device pixels (y-down) by the placed
    glyph's affine ``transform``, so position, scale and rotation are all handled
    while stroke widths stay in device pixels.
    """

    def __init__(self, glyph_set, ctx, transform):
        super().__init__(glyph_set)
        self._ctx = ctx
        self._t = transform

    def _moveTo(self, pt):
        self._ctx.move_to(*self._t.transformPoint(pt))

    def _lineTo(self, pt):
        self._ctx.line_to(*self._t.transformPoint(pt))

    def _curveToOne(self, pt1, pt2, pt3):
        x1, y1 = self._t.transformPoint(pt1)
        x2, y2 = self._t.transformPoint(pt2)
        x3, y3 = self._t.transformPoint(pt3)
        self._ctx.curve_to(x1, y1, x2, y2, x3, y3)

    def _closePath(self):
        self._ctx.close_path()


def _surface_to_image(surface: Any) -> Image.Image:
    """Convert a cairo ARGB32 surface to a straight-alpha RGBA Pillow image.

    Cairo stores ARGB32 as premultiplied BGRA in native byte order. Pillow's
    ``"BGRa"`` raw decoder both reorders the channels into RGBA and
    un-premultiplies them, so anti-aliased edges keep their true color instead of
    darkening — and it needs no numpy. ``stride`` is passed so any per-row
    padding cairo added is skipped.
    """
    width = surface.get_width()
    height = surface.get_height()
    stride = surface.get_stride()
    data = bytes(surface.get_data())
    return Image.frombuffer("RGBA", (width, height), data, "raw", "BGRa", stride, 1)


def _rasterize(
    font: IVSFont,
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
    _require_cairo()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(width, 1), max(height, 1))
    ctx = cairo.Context(surface)

    if background[3] > 0:
        ctx.set_source_rgba(*background)
        ctx.paint()

    glyph_set = font.glyph_set
    for pg in glyphs:
        pen = _CairoPen(glyph_set, ctx, pg.transform)
        replayRecording(font.glyph_outline(pg.glyph_name), pen)

        if stroke_width > 0 and stroke[3] > 0:
            ctx.set_line_width(stroke_width)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.set_source_rgba(*stroke)
            ctx.stroke_preserve()

        ctx.set_source_rgba(*fill)
        ctx.fill()

    return _surface_to_image(surface)


def _rasterize_dispatch(
    font: IVSFont,
    glyphs,
    width: int,
    height: int,
    *,
    backend: Backend,
    fill: RGBA,
    stroke: RGBA,
    stroke_width: float,
    background: RGBA,
) -> Image.Image:
    """Route placed glyphs to the selected backend, returning an RGBA image.

    Only cairo can stroke, so a requested stroke always uses the cairo path
    regardless of ``backend``; unstroked fills use the chosen backend directly.
    """
    if not _stroke_active(stroke, stroke_width):
        if backend == "builtin":
            return rasterize_builtin(font, glyphs, width, height, fill=fill, background=background)
        if backend == "freetype":
            return rasterize_ft(font, glyphs, width, height, fill=fill, background=background)

    return _rasterize(
        font,
        glyphs,
        width,
        height,
        fill=fill,
        stroke=stroke,
        stroke_width=stroke_width,
        background=background,
    )


def render(
    font: IVSFont,
    text: str,
    *,
    size: int = 64,
    direction: Direction = "horizontal",
    align: Align = "start",
    line_spacing: float = 1.0,
    letter_spacing: float = 0.0,
    padding: int = 0,
    orientation: Orientation = "mixed",
    tate_chu_yoko: int = 0,
    color: Color = "#000000",
    stroke: Color = None,
    stroke_width: float = 0.0,
    background: Color = None,
    on_missing: str = "raise",
    backend: Backend = "builtin",
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
        orientation: Vertical only. ``"mixed"`` rotates Latin/digits 90°;
            ``"upright"`` keeps every glyph upright.
        tate_chu_yoko: Vertical only. Set short ASCII digit runs upright and
            horizontal (縦中横); ``0`` disables it.
        color: Fill color (hex string or 0–255 RGB/RGBA tuple).
        stroke: Outline color. If ``None``, no outline is drawn.
        stroke_width: Outline width in pixels.
        background: Background fill. If ``None``, the background is transparent.
        letter_spacing: Extra space between characters, in pixels.
        padding: Transparent padding around the text, in pixels.
        on_missing: ``"raise"`` (default) or ``"skip"`` for unsupported clusters.
        backend: Rasterizer to use. ``"builtin"`` (default) is the dependency-free
            pure-Python path. ``"cairo"`` (requires ``mojivs[cairo]``) and
            ``"freetype"`` (requires ``mojivs[freetype]``) are optional
            accelerators. Only cairo strokes, so ``"builtin"`` and ``"freetype"``
            fall back to cairo automatically whenever a stroke is requested.

    Returns:
        A :class:`PIL.Image.Image` in ``RGBA`` mode.
    """
    if backend not in _BACKENDS:
        raise ValueError(f"backend must be one of {_BACKENDS}, got {backend!r}")

    shaped = shape_for_output(
        font,
        text,
        stroke_width=stroke_width,
        padding=padding,
        size=size,
        direction=direction,
        align=align,
        line_spacing=line_spacing,
        letter_spacing=letter_spacing,
        orientation=orientation,
        tate_chu_yoko=tate_chu_yoko,
        on_missing=on_missing,
    )

    fill = to_rgba(color)
    stroke_rgba = to_rgba(stroke)
    background_rgba = to_rgba(background)

    return _rasterize_dispatch(
        font,
        shaped.glyphs,
        shaped.width,
        shaped.height,
        backend=backend,
        fill=fill,
        stroke=stroke_rgba,
        stroke_width=stroke_width,
        background=background_rgba,
    )


def render_to_box(
    font: IVSFont,
    text: str,
    box: tuple[int, int],
    *,
    color: Color = "#000000",
    stroke: Color = None,
    stroke_width: float = 0.0,
    background: Color = None,
    on_missing: str = "raise",
    backend: Backend = "builtin",
) -> Image.Image:
    """Render a single horizontal line fitted into ``box = (width, height)`` px.

    The line height is scaled to ``height``. If the text is wider than ``width``
    it is compressed horizontally; if narrower, the characters are spread evenly
    (justified) to fill the width. The returned image is exactly ``box`` pixels.

    This is a horizontal single-line helper only. For vertical writing or
    multiple lines, use :func:`render` (which sizes the canvas to the content).

    ``backend`` selects the rasterizer as in :func:`render`: ``"builtin"``
    (default), ``"cairo"`` or ``"freetype"`` (both fall back to cairo when a
    stroke is drawn).
    """
    if backend not in _BACKENDS:
        raise ValueError(f"backend must be one of {_BACKENDS}, got {backend!r}")
    if "\n" in text:
        raise ValueError(
            "render_to_box renders a single line; newlines are not supported. "
            "Use render() for multi-line or vertical text."
        )
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
        transform = Transform(scale_x, 0, 0, -scale_y, x, baseline)
        placed.append(PlacedGlyph(glyph_name, cluster, transform))
        x += font.advance_width(glyph_name) * scale_x + extra_spacing

    fill = to_rgba(color)
    stroke_rgba = to_rgba(stroke)
    background_rgba = to_rgba(background)

    return _rasterize_dispatch(
        font,
        placed,
        box_w,
        box_h,
        backend=backend,
        fill=fill,
        stroke=stroke_rgba,
        stroke_width=stroke_width,
        background=background_rgba,
    )
