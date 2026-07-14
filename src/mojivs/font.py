"""The :class:`IVSFont` — a font wrapper that resolves IVS-aware glyph names.

An :class:`IVSFont` loads a font once and caches the expensive lookups (the
Unicode cmap, the glyph name set, the horizontal metrics). All of the per-render
work in the original implementation — rebuilding the cmap and re-parsing the IVD
on every call — is done here exactly once.
"""

from __future__ import annotations

import os
from typing import Union

from fontTools.ttLib import TTFont

from . import ivs
from .errors import UnsupportedCharacterError

FontSource = Union[str, "os.PathLike[str]", TTFont]


class IVSFont:
    """An IVS-aware view over a single font.

    Args:
        font: A path to an OpenType/TrueType font, or an already-loaded
            :class:`fontTools.ttLib.TTFont`.
        font_number: Index of the face to use inside a font collection
            (``.ttc``/``.otc``). Ignored when ``font`` is a ``TTFont``.

    Example:
        >>> font = IVSFont("HaranoAjiGothic-Medium.otf")
        >>> font.supports("辻")
        True
    """

    def __init__(self, font: FontSource, *, font_number: int = 0):
        if isinstance(font, TTFont):
            self._ttfont = font
        else:
            self._ttfont = TTFont(os.fspath(font), fontNumber=font_number, lazy=True)

        self._glyph_set = self._ttfont.getGlyphSet()
        self._glyph_names = frozenset(self._ttfont.getGlyphNames())
        self._cmap = self._ttfont.getBestCmap()  # codepoint -> glyph name
        self._hmtx = self._ttfont["hmtx"]

        head = self._ttfont["head"]
        hhea = self._ttfont["hhea"]
        self.units_per_em: int = head.unitsPerEm
        self.ascent: int = hhea.ascent
        self.descent: int = hhea.descent

    # -- glyph resolution ---------------------------------------------------

    def glyph_name(self, base: str, selectors: list[str] | None = None) -> str | None:
        """Return the glyph name for a base character and its selectors.

        Resolution order:

        1. If selectors are present and the IVS maps to an Adobe-Japan1 CID that
           exists in this font, use that CID glyph.
        2. Otherwise fall back to the plain Unicode cmap mapping for the base.
        3. Return ``None`` if neither yields a glyph in this font.
        """
        selectors = selectors or []
        cid = ivs.cid_glyph_name(base, selectors)
        if cid is not None and cid in self._glyph_names:
            return cid
        return self._cmap.get(ord(base))

    def missing(self, text: str) -> list[str]:
        """Return the clusters in ``text`` this font cannot render, in order."""
        return [
            base + "".join(selectors)
            for base, selectors in ivs.iter_clusters(text)
            if self.glyph_name(base, selectors) is None
        ]

    def supports(self, text: str) -> bool:
        """Return True if every cluster in ``text`` can be rendered by this font."""
        return not self.missing(text)

    # -- metrics accessors used by the renderer -----------------------------

    @property
    def glyph_set(self):
        """The fontTools glyph set (maps glyph name -> drawable glyph)."""
        return self._glyph_set

    @property
    def line_height(self) -> int:
        """Distance from ascent to descent, in font units."""
        return self.ascent - self.descent

    def advance_width(self, glyph_name: str) -> int:
        """Horizontal advance width of ``glyph_name``, in font units."""
        return self._hmtx[glyph_name][0]

    def resolve_run(
        self, text: str, *, on_missing: str = "raise"
    ) -> list[tuple[str, str]]:
        """Turn ``text`` into an ordered list of ``(cluster, glyph_name)`` pairs.

        Args:
            text: The text to resolve.
            on_missing: ``"raise"`` (default) to raise
                :class:`~mojivs.errors.UnsupportedCharacterError` for unknown
                clusters, or ``"skip"`` to drop them silently.

        Returns:
            The resolvable clusters paired with their glyph names.
        """
        if on_missing not in ("raise", "skip"):
            raise ValueError("on_missing must be 'raise' or 'skip'")

        run: list[tuple[str, str]] = []
        missing: list[str] = []
        for base, selectors in ivs.iter_clusters(text):
            glyph_name = self.glyph_name(base, selectors)
            cluster = base + "".join(selectors)
            if glyph_name is None:
                missing.append(cluster)
            else:
                run.append((cluster, glyph_name))

        if missing and on_missing == "raise":
            raise UnsupportedCharacterError(missing)
        return run

    # -- convenience: delegate to the renderer ------------------------------

    def render(self, text: str, **kwargs):
        """Render ``text`` to a :class:`PIL.Image.Image`.

        Thin convenience wrapper around :func:`mojivs.render.render`.
        """
        from .render import render as _render

        return _render(self, text, **kwargs)

    def render_to_box(self, text: str, box, **kwargs):
        """Render ``text`` fitted into a ``(width, height)`` pixel box.

        Thin convenience wrapper around :func:`mojivs.render.render_to_box`.
        """
        from .render import render_to_box as _render_to_box

        return _render_to_box(self, text, box, **kwargs)

    def __repr__(self) -> str:
        try:
            name = self._ttfont["name"].getDebugName(4) or "?"
        except Exception:  # pragma: no cover - defensive
            name = "?"
        return f"IVSFont({name!r}, upm={self.units_per_em})"
