"""Vector exporters — render shaped text to SVG and (optionally) PDF.

Both build on the same shaping layer as the raster renderer, so the layout is
identical across formats. SVG has no dependencies beyond fontTools; PDF requires
the optional ``reportlab`` package (``pip install mojivs[pdf]``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.sax.saxutils import quoteattr

from fontTools.pens.basePen import BasePen
from fontTools.pens.svgPathPen import SVGPathPen

from .colors import Color, to_hex
from .shaping import Align, Direction, ShapedText, shape

if TYPE_CHECKING:
    from .font import IVSFont


def _num(value: float) -> str:
    """Format a coordinate compactly (no trailing zeros)."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _paint_attrs(color: Color, stroke: Color, stroke_width: float) -> str:
    fill_hex, fill_a = to_hex(color)
    attrs = [f'fill="{fill_hex}"' if fill_a > 0 else 'fill="none"']
    if fill_a not in (0.0, 1.0):
        attrs.append(f'fill-opacity="{_num(fill_a)}"')
    if stroke is not None and stroke_width > 0:
        stroke_hex, stroke_a = to_hex(stroke)
        attrs.append(f'stroke="{stroke_hex}"')
        attrs.append(f'stroke-width="{_num(stroke_width)}"')
        attrs.append('stroke-linejoin="round"')
        if stroke_a not in (1.0,):
            attrs.append(f'stroke-opacity="{_num(stroke_a)}"')
    return " ".join(attrs)


def _svg_from_shaped(
    font: "IVSFont",
    shaped: ShapedText,
    *,
    color: Color,
    stroke: Color,
    stroke_width: float,
    background: Color,
) -> str:
    glyph_set = font.glyph_set
    paint = _paint_attrs(color, stroke, stroke_width)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{shaped.width}" '
        f'height="{shaped.height}" viewBox="0 0 {shaped.width} {shaped.height}">'
    ]

    bg_hex, bg_a = to_hex(background)
    if bg_a > 0:
        parts.append(
            f'<rect width="{shaped.width}" height="{shaped.height}" '
            f'fill="{bg_hex}" fill-opacity="{_num(bg_a)}"/>'
        )

    for pg in shaped.glyphs:
        pen = SVGPathPen(glyph_set)
        glyph_set[pg.glyph_name].draw(pen)
        d = pen.getCommands()
        if not d:
            continue
        transform = (
            f"translate({_num(pg.x)},{_num(pg.y)}) "
            f"scale({_num(pg.x_scale)},{_num(-pg.y_scale)})"
        )
        title = quoteattr(pg.cluster)
        parts.append(
            f'<path transform="{transform}" {paint} d="{d}"><title>{title[1:-1]}'
            f"</title></path>"
        )

    parts.append("</svg>")
    return "\n".join(parts)


def to_svg(
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
) -> str:
    """Render ``text`` to an SVG document string (scalable, no rasterization).

    Accepts the same layout and style options as :func:`mojivs.render.render`.
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
    return _svg_from_shaped(
        font,
        shaped,
        color=color,
        stroke=stroke,
        stroke_width=stroke_width,
        background=background,
    )


class _ReportlabPen(BasePen):
    """Draws a glyph outline into a reportlab path in PDF (y-up) coordinates."""

    def __init__(self, glyph_set, path, sx, sy, ox, oy):
        super().__init__(glyph_set)
        self._path = path
        self._sx = sx
        self._sy = sy
        self._ox = ox
        self._oy = oy

    def _pt(self, pt):
        return (self._ox + pt[0] * self._sx, self._oy + pt[1] * self._sy)

    def _moveTo(self, pt):
        self._path.moveTo(*self._pt(pt))

    def _lineTo(self, pt):
        self._path.lineTo(*self._pt(pt))

    def _curveToOne(self, pt1, pt2, pt3):
        x1, y1 = self._pt(pt1)
        x2, y2 = self._pt(pt2)
        x3, y3 = self._pt(pt3)
        self._path.curveTo(x1, y1, x2, y2, x3, y3)

    def _closePath(self):
        self._path.close()


def to_pdf(
    font: "IVSFont",
    text: str,
    path,
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
) -> None:
    """Render ``text`` to a single-page PDF written to ``path``.

    The page size matches the shaped pixel size. Requires the optional
    ``reportlab`` dependency (``pip install mojivs[pdf]``).
    """
    try:
        from reportlab.lib.colors import Color as RLColor
        from reportlab.pdfgen import canvas as pdfcanvas
    except ImportError as exc:  # pragma: no cover - exercised without reportlab
        raise RuntimeError(
            "to_pdf requires reportlab; install it with 'pip install mojivs[pdf]'"
        ) from exc

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

    fill_hex, fill_a = to_hex(color)
    fr, fg, fb = (int(fill_hex[i : i + 2], 16) / 255.0 for i in (1, 3, 5))

    c = pdfcanvas.Canvas(str(path), pagesize=(shaped.width, shaped.height))

    bg_hex, bg_a = to_hex(background)
    if bg_a > 0:
        br, bg_, bb = (int(bg_hex[i : i + 2], 16) / 255.0 for i in (1, 3, 5))
        c.setFillColor(RLColor(br, bg_, bb, alpha=bg_a))
        c.rect(0, 0, shaped.width, shaped.height, fill=1, stroke=0)

    do_stroke = stroke is not None and stroke_width > 0
    if do_stroke:
        stroke_hex, stroke_a = to_hex(stroke)
        sr, sg, sb = (int(stroke_hex[i : i + 2], 16) / 255.0 for i in (1, 3, 5))
        c.setStrokeColor(RLColor(sr, sg, sb, alpha=stroke_a))
        c.setLineWidth(stroke_width)
        c.setLineJoin(1)  # round

    c.setFillColor(RLColor(fr, fg, fb, alpha=fill_a))

    glyph_set = font.glyph_set
    for pg in shaped.glyphs:
        # Convert top-down device y to PDF's bottom-up page coordinates.
        p = c.beginPath()
        pen = _ReportlabPen(
            glyph_set, p, pg.x_scale, pg.y_scale, pg.x, shaped.height - pg.y
        )
        glyph_set[pg.glyph_name].draw(pen)
        c.drawPath(p, fill=1 if fill_a > 0 else 0, stroke=1 if do_stroke else 0)

    c.showPage()
    c.save()
