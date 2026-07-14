"""Exception types raised by mojivs."""

from __future__ import annotations


class MojivsError(Exception):
    """Base class for all mojivs errors."""


class UnsupportedCharacterError(MojivsError):
    """Raised when the font cannot render one or more requested characters.

    Attributes:
        characters: The clusters (base + selectors) that could not be resolved
            to a glyph, in order of appearance.
    """

    def __init__(self, characters: list[str]):
        self.characters = characters
        joined = ", ".join(repr(c) for c in characters)
        super().__init__(f"font has no glyph for: {joined}")
