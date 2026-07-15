"""IVS (Ideographic Variation Sequence) resolution — the pure, dependency-light core.

This layer knows nothing about rendering. It parses the Unicode IVD
(Ideographic Variation Database) and answers a single question: given a base
character plus its trailing variation selector(s), which Adobe-Japan1 CID does
that sequence map to?

The only runtime dependency here is fontTools (for the caller-supplied cmap);
this module itself imports nothing beyond the standard library.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from importlib import resources

# Range of Unicode variation selectors used by the IVD (VS17–VS256).
# Standardized selectors (U+FE00–FE0F) are intentionally excluded because the
# Adobe-Japan1 IVD collection only uses this range.
VARIATION_SELECTOR_START = 0xE0100
VARIATION_SELECTOR_END = 0xE01EF

#: Collection name matched against column 2 of the IVD file.
ADOBE_JAPAN1 = "Adobe-Japan1"


def is_variation_selector(char: str) -> bool:
    """Return True if ``char`` is an IVS variation selector (U+E0100–U+E01EF)."""
    return VARIATION_SELECTOR_START <= ord(char) <= VARIATION_SELECTOR_END


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
