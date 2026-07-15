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

from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import ControlBoundsPen

from . import ivs

if TYPE_CHECKING:
    from .font import IVSFont

Direction = Literal["horizontal", "vertical"]
Align = Literal["start", "center", "end"]
Orientation = Literal["mixed", "upright"]

# Unicode ranges kept upright in vertical text (roughly Unicode UAX #50 "U").
# Everything outside these ranges (Latin, digits, Greek, Cyrillic, half-width
# forms, …) is rotated 90° clockwise when ``orientation="mixed"``.
_UPRIGHT_RANGES = (
    (0x3000, 0x303F),  # CJK Symbols and Punctuation
    (0x3040, 0x30FF),  # Hiragana + Katakana
    (0x3105, 0x312F),  # Bopomofo
    (0x3190, 0x319F),  # Kanbun
    (0x31F0, 0x31FF),  # Katakana Phonetic Extensions
    (0x3300, 0x9FFF),  # CJK Compatibility, Ext A, Unified Ideographs
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0xFE10, 0xFE1F),  # Vertical Forms
    (0xFE30, 0xFE4F),  # CJK Compatibility Forms
    (0xFF00, 0xFF60),  # Fullwidth Forms (fullwidth ASCII)
    (0xFFE0, 0xFFE6),  # Fullwidth signs
    (0x1B000, 0x1B16F),  # Kana Supplement / Extended
    (0x20000, 0x3FFFF),  # CJK Extension B and beyond
)


def is_upright_in_vertical(char: str) -> bool:
    """Whether ``char`` stays upright (vs. rotated) in vertical text."""
    cp = ord(char)
    return any(lo <= cp <= hi for lo, hi in _UPRIGHT_RANGES)

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

    ``transform`` is an affine mapping font-unit points ``(fx, fy)`` (y-up) to
    device pixels (y-down); apply it with ``transform.transformPoint((fx, fy))``.
    For upright glyphs it is a scale-and-flip; rotated glyphs (Latin in vertical
    text) carry a 90° rotation as well.
    """

    glyph_name: str
    cluster: str
    transform: Transform

    @property
    def x(self) -> float:
        """Device x of the glyph origin (the transform's x translation)."""
        return self.transform[4]

    @property
    def y(self) -> float:
        """Device y of the glyph origin (the transform's y translation)."""
        return self.transform[5]


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
) -> tuple[list[PlacedGlyph], float, float]:
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
        baseline = font.ascent * scale + i * line_advance
        x = _aligned_offset(line_widths[i], max_width, align)
        for cluster, glyph_name in line:
            transform = Transform(scale, 0, 0, -scale, x, baseline)
            placed.append(PlacedGlyph(glyph_name, cluster, transform))
            x += font.advance_width(glyph_name) * scale + letter_spacing

    advance_width = max_width
    advance_height = line_box + line_advance * (len(lines) - 1)
    return placed, advance_width, advance_height


@dataclass(frozen=True)
class _VCell:
    """One vertical layout slot: an upright glyph, a rotated glyph, or a
    tate-chu-yoko run of digits set upright and horizontal in a single cell."""

    mode: Literal["upright", "rotate", "tcy"]
    items: list[tuple[str, str]]
    advance: float  # advance down the column, in pixels


def _is_ascii_digit(cluster: str) -> bool:
    return len(cluster) == 1 and cluster in "0123456789"


def _vertical_cells(
    font: "IVSFont",
    column: list[tuple[str, str]],
    *,
    scale: float,
    orientation: Orientation,
    tate_chu_yoko: int,
) -> list[_VCell]:
    em_px = font.units_per_em * scale
    cells: list[_VCell] = []
    i, n = 0, len(column)
    while i < n:
        cluster, glyph_name = column[i]

        # Tate-chu-yoko: consecutive digits are chunked into groups of at most
        # `tate_chu_yoko`, each set upright and horizontal inside one em cell.
        if tate_chu_yoko and _is_ascii_digit(cluster):
            j = i
            while j < n and _is_ascii_digit(column[j][0]) and (j - i) < tate_chu_yoko:
                j += 1
            cells.append(_VCell("tcy", column[i:j], em_px))
            i = j
            continue

        if orientation == "mixed" and not is_upright_in_vertical(cluster[0]):
            advance = font.advance_width(glyph_name) * scale
            cells.append(_VCell("rotate", [column[i]], advance))
        else:
            advance = font.advance_height(glyph_name) * scale
            cells.append(_VCell("upright", [column[i]], advance))
        i += 1
    return cells


def _place_cell(
    placed: list[PlacedGlyph],
    font: "IVSFont",
    cell: _VCell,
    *,
    center_x: float,
    top_y: float,
    scale: float,
    v_center: float,
) -> None:
    if cell.mode == "upright":
        cluster, glyph_name = cell.items[0]
        origin_x = center_x - (font.advance_width(glyph_name) / 2.0) * scale
        origin_y = top_y + font.vertical_origin(glyph_name) * scale
        placed.append(
            PlacedGlyph(glyph_name, cluster, Transform(scale, 0, 0, -scale, origin_x, origin_y))
        )
    elif cell.mode == "rotate":
        cluster, glyph_name = cell.items[0]
        # 90° clockwise: font +x advances down, font +y points right.
        transform = Transform(0, scale, scale, 0, center_x - v_center * scale, top_y)
        placed.append(PlacedGlyph(glyph_name, cluster, transform))
    else:  # tate-chu-yoko: upright digits laid horizontally, squeezed to one em
        advances = [font.advance_width(g) for _, g in cell.items]
        natural = sum(advances) * scale
        squeeze = min(1.0, font.units_per_em * scale / natural) if natural else 1.0
        sx = scale * squeeze
        x = center_x - sum(advances) * sx / 2.0
        # Center the digits' cap box vertically within the em cell.
        baseline = top_y + cell.advance / 2.0 + (font.cap_height / 2.0) * scale
        for cluster, glyph_name in cell.items:
            placed.append(
                PlacedGlyph(glyph_name, cluster, Transform(sx, 0, 0, -scale, x, baseline))
            )
            x += font.advance_width(glyph_name) * sx


def _shape_vertical(
    font: "IVSFont",
    columns: list[list[tuple[str, str]]],
    *,
    scale: float,
    align: Align,
    line_spacing: float,
    letter_spacing: float,
    orientation: Orientation,
    tate_chu_yoko: int,
) -> tuple[list[PlacedGlyph], float, float]:
    column_width = font.units_per_em * scale * line_spacing
    v_center = (font.ascent + font.descent) / 2.0

    columns_cells = [
        _vertical_cells(
            font, col, scale=scale, orientation=orientation, tate_chu_yoko=tate_chu_yoko
        )
        for col in columns
    ]
    column_heights = [
        sum(c.advance for c in cells) + letter_spacing * max(len(cells) - 1, 0)
        for cells in columns_cells
    ]
    max_height = max(column_heights, default=0.0)
    n_cols = len(columns_cells)

    placed: list[PlacedGlyph] = []
    for j, cells in enumerate(columns_cells):
        # First column is visually rightmost.
        center_x = (n_cols - 1 - j) * column_width + column_width / 2.0
        y = _aligned_offset(column_heights[j], max_height, align)
        for cell in cells:
            _place_cell(
                placed, font, cell, center_x=center_x, top_y=y, scale=scale, v_center=v_center
            )
            y += cell.advance + letter_spacing

    return placed, n_cols * column_width, max_height


def _shift(transform: Transform, dx: float, dy: float) -> Transform:
    """Translate a device-space affine by ``(dx, dy)`` in the output plane."""
    return Transform(transform[0], transform[1], transform[2], transform[3],
                     transform[4] + dx, transform[5] + dy)


def _ink_bounds(font: "IVSFont", placed: list[PlacedGlyph]):
    """Device-space bounding box of all glyph ink, or ``None`` if there is none.

    Uses control-point bounds (a cheap superset of the true outline bounds),
    which is exactly what is needed to guarantee nothing is clipped.
    """
    glyph_set = font.glyph_set
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for pg in placed:
        pen = ControlBoundsPen(glyph_set)
        glyph_set[pg.glyph_name].draw(pen)
        if pen.bounds is None:
            continue
        x0, y0, x1, y1 = pen.bounds
        for corner in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            dx, dy = pg.transform.transformPoint(corner)
            min_x, max_x = min(min_x, dx), max(max_x, dx)
            min_y, max_y = min(min_y, dy), max(max_y, dy)
    if min_x == float("inf"):
        return None
    return min_x, min_y, max_x, max_y


def _finalize(
    font: "IVSFont",
    placed: list[PlacedGlyph],
    advance_width: float,
    advance_height: float,
    *,
    padding: float,
    direction: Direction,
) -> ShapedText:
    """Size the canvas to cover both the advance box and any ink overhang,
    then shift the glyphs so the content sits at ``padding`` from the edges."""
    x0, y0 = 0.0, 0.0
    x1, y1 = advance_width, advance_height
    ink = _ink_bounds(font, placed)
    if ink is not None:
        x0, y0 = min(x0, ink[0]), min(y0, ink[1])
        x1, y1 = max(x1, ink[2]), max(y1, ink[3])

    shift_x, shift_y = padding - x0, padding - y0
    shifted = tuple(
        PlacedGlyph(pg.glyph_name, pg.cluster, _shift(pg.transform, shift_x, shift_y))
        for pg in placed
    )
    width = int(round(x1 - x0 + 2 * padding))
    height = int(round(y1 - y0 + 2 * padding))
    return ShapedText(shifted, width, height, direction)


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
    orientation: Orientation = "mixed",
    tate_chu_yoko: int = 0,
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
        orientation: Vertical only. ``"mixed"`` (default) rotates non-CJK
            characters (Latin, digits, …) 90° clockwise; ``"upright"`` keeps
            every glyph upright.
        tate_chu_yoko: Vertical only. When > 0, maximal runs of ASCII digits of
            at most this length are set upright and horizontal in a single cell
            (縦中横). ``0`` disables it.
        on_missing: ``"raise"`` (default) or ``"skip"`` for unsupported clusters.

    Returns:
        A :class:`ShapedText`.
    """
    if direction not in ("horizontal", "vertical"):
        raise ValueError("direction must be 'horizontal' or 'vertical'")
    if align not in ("start", "center", "end"):
        raise ValueError("align must be 'start', 'center' or 'end'")
    if orientation not in ("mixed", "upright"):
        raise ValueError("orientation must be 'mixed' or 'upright'")
    if tate_chu_yoko < 0:
        raise ValueError("tate_chu_yoko must be >= 0")

    scale = size / font.units_per_em
    substitute = VERTICAL_FORMS if direction == "vertical" else None

    runs = [
        font.resolve_run(segment, on_missing=on_missing, substitute=substitute)
        for segment in text.split("\n")
    ]

    if direction == "vertical":
        if not font.has_vertical_metrics:
            raise ValueError("font has no vertical metrics (vmtx); cannot set vertical")
        placed, adv_w, adv_h = _shape_vertical(
            font,
            runs,
            scale=scale,
            align=align,
            line_spacing=line_spacing,
            letter_spacing=letter_spacing,
            orientation=orientation,
            tate_chu_yoko=tate_chu_yoko,
        )
    else:
        placed, adv_w, adv_h = _shape_horizontal(
            font,
            runs,
            scale=scale,
            align=align,
            line_spacing=line_spacing,
            letter_spacing=letter_spacing,
        )

    return _finalize(
        font, placed, adv_w, adv_h, padding=padding, direction=direction
    )


def shape_for_output(
    font: "IVSFont", text: str, *, stroke_width: float = 0.0, padding: float = 0.0, **layout
) -> ShapedText:
    """Shape ``text`` for a renderer, widening the padding to fit the stroke.

    Shared preamble for :func:`mojivs.render.render`,
    :func:`mojivs.export.to_svg` and :func:`mojivs.export.to_pdf` so the
    stroke-padding rule lives in one place.
    """
    return shape(font, text, padding=padding + stroke_width / 2.0, **layout)
