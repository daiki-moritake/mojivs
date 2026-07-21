"""Variation-sequence clustering and the Adobe-Japan1 IVD fallback.

This layer knows nothing about rendering. It splits text into base-character
clusters (a base plus any trailing variation selectors) and provides the legacy
Adobe-Japan1 lookup: given a base character plus its variation selector(s),
which Adobe-Japan1 CID does that sequence map to?

Two selector families are recognised when clustering:

* **IVS** (Ideographic Variation Sequence) selectors U+E0100–U+E01EF (VS17–256),
  used by the Unicode IVD.
* **SVS** (Standardized Variation Sequence) selectors U+FE00–U+FE0F (VS1–16),
  used by StandardizedVariants and emoji presentation sequences.

The authoritative resolution is now the font's own cmap format-14 subtable (see
:mod:`mojivs.font`); :func:`cid_glyph_name` here is only the Adobe-Japan1
fallback for CID-keyed fonts that ship no format-14 table. The Adobe-Japan1 IVD
only uses the IVS range, so SVS lookups naturally miss it and defer to the font.

The only runtime dependency here is fontTools (for the caller-supplied cmap);
this module itself imports nothing beyond the standard library.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from importlib import resources

# IVS variation selectors used by the Unicode IVD (VS17–VS256).
VARIATION_SELECTOR_START = 0xE0100
VARIATION_SELECTOR_END = 0xE01EF

# Standardized variation selectors (VS1–VS16): StandardizedVariants and emoji
# presentation sequences. The IVD does not use these, but a font's cmap
# format-14 subtable can, so they are recognised when clustering.
SVS_SELECTOR_START = 0xFE00
SVS_SELECTOR_END = 0xFE0F

#: Collection name matched against column 2 of the IVD file.
ADOBE_JAPAN1 = "Adobe-Japan1"


def is_variation_selector(char: str) -> bool:
    """Return True if ``char`` is a variation selector.

    Covers both IVS selectors (U+E0100–U+E01EF, VS17–256) and SVS selectors
    (U+FE00–U+FE0F, VS1–16). Either family attaches to the preceding base
    character when clustering.
    """
    cp = ord(char)
    return (
        VARIATION_SELECTOR_START <= cp <= VARIATION_SELECTOR_END
        or SVS_SELECTOR_START <= cp <= SVS_SELECTOR_END
    )


def iter_clusters(text: str) -> Iterator[tuple[str, list[str]]]:
    """Split ``text`` into (base character, [variation selectors]) clusters.

    A cluster is a base character followed by zero or more variation selectors.
    Stray selectors with no preceding base character are skipped.

    >>> list(iter_clusters("A辻\U000e0101"))
    [('A', []), ('辻', ['\U000e0101'])]
    """
    i = 0
    n = len(text)
    while i < n:
        base = text[i]
        if is_variation_selector(base):
            # Selector without a base character: skip it.
            i += 1
            continue
        selectors: list[str] = []
        j = i + 1
        while j < n and is_variation_selector(text[j]):
            selectors.append(text[j])
            j += 1
        yield base, selectors
        i = j


def _sequence_key(base: str, selectors: list[str]) -> str:
    """Build the IVD lookup key, e.g. ``"3402 E0101"`` (uppercase hex, space-joined)."""
    parts = [format(ord(base), "X")]
    parts.extend(format(ord(s), "X") for s in selectors)
    return " ".join(parts)


@functools.lru_cache(maxsize=1)
def _adobe_japan1_index() -> dict[str, str]:
    """Parse the packaged IVD file into ``{"<base> <selector>": "<cid>"}``.

    Parsed once and cached for the process lifetime. ``<cid>`` is the numeric
    CID as a string (``"CID+"`` prefix stripped), e.g. ``"13698"``.
    """
    index: dict[str, str] = {}
    data = resources.files("mojivs.data").joinpath("ivd.txt")
    with data.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(";")
            if len(parts) < 3:
                continue
            sequence = parts[0].strip()
            collection = parts[1].strip()
            if collection != ADOBE_JAPAN1:
                continue
            cid = parts[2].strip().replace("CID+", "")
            index[sequence] = cid
    return index


def cid_glyph_name(base: str, selectors: list[str]) -> str | None:
    """Resolve an IVS to an Adobe-Japan1 glyph name (e.g. ``"cid13698"``).

    Returns ``None`` when there are no selectors or the sequence is not present
    in the Adobe-Japan1 IVD collection. The returned name is *not* checked
    against any particular font — that is the font layer's responsibility.
    """
    if not selectors:
        return None
    cid = _adobe_japan1_index().get(_sequence_key(base, selectors))
    if cid is None:
        return None
    return "cid" + cid.zfill(5)
