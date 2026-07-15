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
from .errors import MojivsError, UnsupportedCharacterError

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
        if self._cmap is None:
            raise MojivsError(
                "font has no usable Unicode cmap subtable; mojivs cannot map "
                "characters to glyphs for this font"
            )
        self._hmtx = self._ttfont["hmtx"]
        self._vmtx = self._ttfont["vmtx"] if "vmtx" in self._ttfont else None
        self._vorg = self._ttfont["VORG"] if "VORG" in self._ttfont else None

        head = self._ttfont["head"]
        hhea = self._ttfont["hhea"]
        self.units_per_em: int = head.unitsPerEm
        self.ascent: int = hhea.ascent
        self.descent: int = hhea.descent

        # Cap height is used to vertically center tate-chu-yoko digits; fall back
        # to a typical proportion of the em when the font does not declare it.
        os2 = self._ttfont["OS/2"] if "OS/2" in self._ttfont else None
        cap = getattr(os2, "sCapHeight", 0) if os2 is not None else 0
        self.cap_height: int = cap if cap > 0 else round(self.units_per_em * 0.7)

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

    @property
    def has_vertical_metrics(self) -> bool:
        """Whether the font carries vertical metrics (a ``vmtx`` table)."""
        return self._vmtx is not None

    def advance_height(self, glyph_name: str) -> int:
        """Vertical advance height of ``glyph_name``, in font units.

        Falls back to the line height when the font has no ``vmtx`` table.
        """
        if self._vmtx is None:
            return self.line_height
        return self._vmtx[glyph_name][0]

    def vertical_origin(self, glyph_name: str) -> int:
        """Y of the glyph's vertical origin above the baseline, in font units.

        Uses the ``VORG`` table when present, otherwise the ascent.
        """
        if self._vorg is not None:
            return self._vorg.VOriginRecords.get(
                glyph_name, self._vorg.defaultVertOriginY
            )
        return self.ascent

    def resolve_run(
        self,
        text: str,
        *,
        on_missing: str = "raise",
        substitute: dict[str, str] | None = None,
    ) -> list[tuple[str, str]]:
        """Turn ``text`` into an ordered list of ``(cluster, glyph_name)`` pairs.

        Args:
            text: The text to resolve.
            on_missing: ``"raise"`` (default) to raise
                :class:`~mojivs.errors.UnsupportedCharacterError` for unknown
                clusters, or ``"skip"`` to drop them silently.
            substitute: Optional mapping applied to base characters before
                lookup (e.g. vertical punctuation forms). If a substituted
                character has no glyph, the original is tried.

        Returns:
            The resolvable clusters paired with their glyph names.
        """
        if on_missing not in ("raise", "skip"):
            raise ValueError("on_missing must be 'raise' or 'skip'")

        run: list[tuple[str, str]] = []
        missing: list[str] = []
        for base, selectors in ivs.iter_clusters(text):
            candidates = [base]
            if substitute and base in substitute:
                candidates.insert(0, substitute[base])

            for candidate in candidates:
                glyph_name = self.glyph_name(candidate, selectors)
                if glyph_name is not None:
                    run.append((candidate + "".join(selectors), glyph_name))
                    break
            else:
                missing.append(base + "".join(selectors))

        if missing and on_missing == "raise":
            raise UnsupportedCharacterError(missing)
        return run

    # -- convenience: delegate to shaping / rendering / export --------------

    def shape(self, text: str, **kwargs):
        """Lay out ``text`` into positioned glyphs.

        Thin convenience wrapper around :func:`mojivs.shaping.shape`.
        """
        from .shaping import shape as _shape

        return _shape(self, text, **kwargs)

    def render(self, text: str, **kwargs):
        """Render ``text`` to a :class:`PIL.Image.Image`.

        Thin convenience wrapper around :func:`mojivs.render.render`.
        """
        from .render import render as _render

        return _render(self, text, **kwargs)

    def to_svg(self, text: str, **kwargs) -> str:
        """Render ``text`` to an SVG document string.

        Thin convenience wrapper around :func:`mojivs.export.to_svg`.
        """
        from .export import to_svg as _to_svg

        return _to_svg(self, text, **kwargs)

    def to_pdf(self, text: str, path, **kwargs) -> None:
        """Render ``text`` to a single-page PDF at ``path``.

        Requires the optional ``reportlab`` dependency
        (``pip install mojivs[pdf]``). Thin wrapper around
        :func:`mojivs.export.to_pdf`.
        """
        from .export import to_pdf as _to_pdf

        return _to_pdf(self, text, path, **kwargs)

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
