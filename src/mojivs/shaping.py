"""Text shaping — turn text into positioned glyphs (the reusable "B" layer).

:func:`shape` computes glyph positions in pixel space without touching any
rasterizer. The result (:class:`ShapedText`) is consumed by the PNG renderer
(:mod:`mojivs.render`) and the vector exporters (:mod:`mojivs.export`), so a
single layout engine drives every output format.

Supported layouts:

* Horizontal, left-to-right, with ``\\n`` producing stacked lines.
* Vertical, top-to-bottom with columns laid out right-to-left (``\\n`` starts a
  new column), using the font's vertical metrics (``vmtx`` / ``VORG``) and
  vertical punctuation forms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from . import ivs

if TYPE_CHECKING:
    from .font import IVSFont

Direction = Literal["horizontal", "vertical"]
Align = Literal["start", "center", "end"]

#: Characters that take a dedicated glyph when set vertically.
VERTICAL_FORMS = {
    "、": "︑",
    "。": "︒",
    "，": "︐",
    "．": "︒",
    "（": "︵",
    "）": "︶",
    "〔": "︹",
    "〕": "︺",
    "［": "﹇",
    "］": "﹈",
    "｛": "︷",
    "｝": "︸",
    "〈": "︿",
    "〉": "﹀",
    "《": "︽",
    "》": "︾",
    "「": "﹁",
    "」": "﹂",
    "『": "﹃",
    "』": "﹄",
    "【": "︻",
    "】": "︼",
    "…": "︙",
    "‥": "︰",
    "ー": "丨",
    "－": "丨",
    "-": "丨",
    "〜": "〜",
}


@dataclass(frozen=True)
class PlacedGlyph:
    """A single glyph positioned in pixel space.

    The mapping from a font-unit point ``(fx, fy)`` (y-up) to a device pixel is
    ``(x + fx * x_scale, y - fy * y_scale)`` — i.e. ``(x, y)`` is the glyph
    origin on the baseline and the scales flip/​size the outline.
    """

    glyph_name: str
    cluster: str
    x: float
    y: float
    x_scale: float
    y_scale: float


@dataclass(frozen=True)
class ShapedText:
    """The result of :func:`shape`: positioned glyphs plus the canvas size."""

    glyphs: tuple[PlacedGlyph, ...]
    width: int
    height: int
    direction: Direction

    def __bool__(self) -> bool:
        return bool(self.glyphs)


def _aligned_offset(extent: float, max_extent: float, align: Align) -> float:
    if align == "center":
        return (max_extent - extent) / 2.0
    if align == "end":
        return max_extent - extent
    return 0.0


def _shape_horizontal(
    font: "IVSFont",
    lines: list[list[tuple[str, str]]],
    *,
    scale: float,
    align: Align,
    line_spacing: float,
    letter_spacing: float,
    padding: float,
) -> ShapedText:
    line_box = font.line_height * scale
    line_advance = line_box * line_spacing

    line_widths = [
        sum(font.advance_width(g) * scale for _, g in line)
        + letter_spacing * max(len(line) - 1, 0)
        for line in lines
    ]
    max_width = max(line_widths, default=0.0)

    placed: list[PlacedGlyph] = []
    for i, line in enumerate(lines):
        baseline = padding + font.ascent * scale + i * line_advance
        x = padding + _aligned_offset(line_widths[i], max_width, align)
        for cluster, glyph_name in line:
            placed.append(PlacedGlyph(glyph_name, cluster, x, baseline, scale, scale))
            x += font.advance_width(glyph_name) * scale + letter_spacing

    width = int(round(max_width + 2 * padding))
    height = int(round(line_box + line_advance * (len(lines) - 1) + 2 * padding))
    return ShapedText(tuple(placed), width, height, "horizontal")


def _shape_vertical(
    font: "IVSFont",
    columns: list[list[tuple[str, str]]],
    *,
    scale: float,
    align: Align,
    line_spacing: float,
    letter_spacing: float,
    padding: float,
) -> ShapedText:
    column_width = font.units_per_em * scale * line_spacing

    column_heights = [
        sum(font.advance_height(g) * scale for _, g in col)
        + letter_spacing * max(len(col) - 1, 0)
        for col in columns
    ]
    max_height = max(column_heights, default=0.0)
    n_cols = len(columns)

    placed: list[PlacedGlyph] = []
    for j, col in enumerate(columns):
        # First column is visually rightmost.
        center_x = padding + (n_cols - 1 - j) * column_width + column_width / 2.0
        y = padding + _aligned_offset(column_heights[j], max_height, align)
        for cluster, glyph_name in col:
            advance_h = font.advance_height(glyph_name) * scale
            origin_x = center_x - (font.advance_width(glyph_name) / 2.0) * scale
            origin_y = y + font.vertical_origin(glyph_name) * scale
            placed.append(
                PlacedGlyph(glyph_name, cluster, origin_x, origin_y, scale, scale)
            )
            y += advance_h + letter_spacing

    width = int(round(n_cols * column_width + 2 * padding))
    height = int(round(max_height + 2 * padding))
    return ShapedText(tuple(placed), width, height, "vertical")


def shape(
    font: "IVSFont",
    text: str,
    *,
    size: int = 64,
    direction: Direction = "horizontal",
    align: Align = "start",
    line_spacing: float = 1.0,
    letter_spacing: float = 0.0,
    padding: float = 0.0,
    on_missing: str = "raise",
) -> ShapedText:
    """Lay out ``text`` into positioned glyphs.

    Args:
        font: The :class:`~mojivs.font.IVSFont` to shape with.
        text: The text to lay out. ``\\n`` starts a new line (horizontal) or a
            new column (vertical).
        size: Em size in pixels.
        direction: ``"horizontal"`` or ``"vertical"``.
        align: Cross-axis alignment of shorter lines/columns: ``"start"``,
            ``"center"`` or ``"end"``.
        line_spacing: Multiplier applied to the line/column advance.
        letter_spacing: Extra space between glyphs, in pixels.
        padding: Transparent padding around the text, in pixels.
        on_missing: ``"raise"`` (default) or ``"skip"`` for unsupported clusters.

    Returns:
        A :class:`ShapedText`.
    """
    scale = size / font.units_per_em
    substitute = VERTICAL_FORMS if direction == "vertical" else None

    runs = [
        font.resolve_run(segment, on_missing=on_missing, substitute=substitute)
        for segment in text.split("\n")
    ]

    if direction == "vertical":
        if not font.has_vertical_metrics:
            raise ValueError("font has no vertical metrics (vmtx); cannot set vertical")
        return _shape_vertical(
            font,
            runs,
            scale=scale,
            align=align,
            line_spacing=line_spacing,
            letter_spacing=letter_spacing,
            padding=padding,
        )
    return _shape_horizontal(
        font,
        runs,
        scale=scale,
        align=align,
        line_spacing=line_spacing,
        letter_spacing=letter_spacing,
        padding=padding,
    )
