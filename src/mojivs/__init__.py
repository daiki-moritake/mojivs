"""mojivs — IVS-aware Japanese text rendering.

Render Japanese text, including Ideographic Variation Sequences (異体字 / IVS),
to images. Variation selectors are resolved through the Adobe-Japan1 IVD and
mapped to the font's CID glyphs — something Pillow's ``ImageFont`` cannot do.

Quick start::

    from mojivs import IVSFont

    font = IVSFont("HaranoAjiGothic-Medium.otf")
    image = font.render("辻\U000e0101鯛", size=64, color="#000")
    image.save("out.png")

The package is layered:

* :mod:`mojivs.ivs` — the pure IVS→CID resolver (no rendering dependencies).
* :class:`mojivs.IVSFont` — a cached, IVS-aware view over a font.
* :func:`mojivs.render` / :func:`mojivs.render_to_box` — the rasterizers.
"""

from __future__ import annotations

from .errors import MojivsError, UnsupportedCharacterError
from .export import to_pdf, to_svg
from .font import IVSFont
from .ivs import is_variation_selector, iter_clusters
from .render import render, render_to_box
from .shaping import PlacedGlyph, ShapedText, is_upright_in_vertical, shape

__version__ = "0.3.0"

__all__ = [
    "IVSFont",
    "render",
    "render_to_box",
    "shape",
    "to_svg",
    "to_pdf",
    "ShapedText",
    "PlacedGlyph",
    "is_upright_in_vertical",
    "is_variation_selector",
    "iter_clusters",
    "MojivsError",
    "UnsupportedCharacterError",
    "__version__",
]
