"""Color parsing shared by the rasterizer and the vector exporters."""

from __future__ import annotations

from typing import Sequence, Union

Color = Union[str, Sequence[int], None]
RGBA = tuple[float, float, float, float]

TRANSPARENT: RGBA = (0.0, 0.0, 0.0, 0.0)


def to_rgba(color: Color, default: RGBA = TRANSPARENT) -> RGBA:
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


def to_hex(color: Color, default: Color = None) -> tuple[str, float]:
    """Return ``("#rrggbb", alpha)`` for a color, for use in SVG/PDF output."""
    r, g, b, a = to_rgba(color if color is not None else default)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}", a
