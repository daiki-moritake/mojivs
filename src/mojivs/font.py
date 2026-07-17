"""The :class:`IVSFont` — a font wrapper that resolves IVS-aware glyph names.

An :class:`IVSFont` loads a font once and caches the expensive lookups (the
Unicode cmap, the glyph name set, the horizontal metrics). All of the per-render
work in the original implementation — rebuilding the cmap and re-parsing the IVD
on every call — is done here exactly once.
"""

from __future__ import annotations

import io
import os
from typing import Any, Union

from fontTools.pens.boundsPen import ControlBoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, replayRecording
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
        self._source = font
        self._font_number = font_number
        if isinstance(font, TTFont):
            self._ttfont = font
        else:
            self._ttfont = TTFont(os.fspath(font), fontNumber=font_number, lazy=True)

        # Lazily populated by the optional FreeType backend (see render_ft): the
        # raw font bytes and a cached freetype.Face. Kept here so their lifetime
        # matches the font and they are built at most once.
        self._font_bytes: bytes | None = None
        self._ft_face: Any = None

        # fontTools table objects are dynamically typed; annotate the ones we
        # poke attributes/indices on as Any so the type checker stays quiet.
        self._glyph_set = self._ttfont.getGlyphSet()
        self._glyph_names = frozenset(self._ttfont.getGlyphNames())
        cmap = self._ttfont.getBestCmap()  # codepoint -> glyph name
        if cmap is None:
            raise MojivsError(
                "font has no usable Unicode cmap subtable; mojivs cannot map "
                "characters to glyphs for this font"
            )
        self._cmap: dict[int, str] = cmap
        self._hmtx: Any = self._ttfont["hmtx"]
        self._vmtx: Any = self._ttfont["vmtx"] if "vmtx" in self._ttfont else None
        self._vorg: Any = self._ttfont["VORG"] if "VORG" in self._ttfont else None

        head: Any = self._ttfont["head"]
        hhea: Any = self._ttfont["hhea"]
        self.units_per_em: int = head.unitsPerEm
        self.ascent: int = hhea.ascent
        self.descent: int = hhea.descent

        # Cap height is used to vertically center tate-chu-yoko digits; fall back
        # to a typical proportion of the em when the font does not declare it.
        os2 = self._ttfont["OS/2"] if "OS/2" in self._ttfont else None
        cap = getattr(os2, "sCapHeight", 0) if os2 is not None else 0
        self.cap_height: int = cap if cap > 0 else round(self.units_per_em * 0.7)

        # Interpreting a glyph's charstring/glyf program is the single most
        # expensive step in a render, so each glyph's outline is decoded once
        # and cached here (as a replayable pen recording), then reused for both
        # bounds computation and rasterization instead of being re-interpreted.
        self._outline_cache: dict[str, list] = {}
        self._cbounds_cache: dict[str, tuple[float, float, float, float] | None] = {}

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

    def font_data(self) -> bytes:
        """Raw bytes of the underlying font file (cached).

        Used by the optional FreeType backend, which needs the font file itself.
        Read from the source path when available, otherwise serialized from the
        in-memory :class:`~fontTools.ttLib.TTFont`.
        """
        if self._font_bytes is None:
            if isinstance(self._source, TTFont):
                buffer = io.BytesIO()
                self._source.save(buffer)
                self._font_bytes = buffer.getvalue()
            else:
                with open(os.fspath(self._source), "rb") as handle:
                    self._font_bytes = handle.read()
        return self._font_bytes

    def glyph_outline(self, glyph_name: str) -> list:
        """Return ``glyph_name``'s outline as a replayable pen recording (cached).

        The font's charstring/glyf program is interpreted once per glyph (with
        any components decomposed) and the pen calls are recorded. Callers
        replay the recording — via :func:`fontTools.pens.recordingPen.replayRecording`
        — instead of re-running the interpreter, which is what dominates render
        time. Repeated glyphs (common in real text) reuse the cached recording.
        """
        outline = self._outline_cache.get(glyph_name)
        if outline is None:
            pen = DecomposingRecordingPen(self._glyph_set)
            self._glyph_set[glyph_name].draw(pen)
            outline = pen.value
            self._outline_cache[glyph_name] = outline
        return outline

    def glyph_control_bounds(self, glyph_name: str) -> tuple[float, float, float, float] | None:
        """Control-point bounds ``(x0, y0, x1, y1)`` of ``glyph_name`` in font units.

        A cheap superset of the true outline bounds (exactly what the layout
        engine needs to avoid clipping), computed from the cached outline so the
        glyph is never interpreted a second time. Returns ``None`` for an empty
        glyph (e.g. a space).
        """
        if glyph_name in self._cbounds_cache:
            return self._cbounds_cache[glyph_name]
        pen = ControlBoundsPen(self._glyph_set)
        replayRecording(self.glyph_outline(glyph_name), pen)
        bounds = pen.bounds
        self._cbounds_cache[glyph_name] = bounds
        return bounds

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
            return self._vorg.VOriginRecords.get(glyph_name, self._vorg.defaultVertOriginY)
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
            name_table: Any = self._ttfont["name"]
            name = name_table.getDebugName(4) or "?"
        except Exception:  # pragma: no cover - defensive
            name = "?"
        return f"IVSFont({name!r}, upm={self.units_per_em})"
