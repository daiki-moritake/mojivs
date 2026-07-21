"""Tests for IVSFont glyph resolution and support queries."""

import pytest
from fontTools.ttLib import TTFont

from mojivs import IVSFont, MojivsError, UnsupportedCharacterError

TSUJI = "辻"
VS17 = "\U000e0100"
VS18 = "\U000e0101"
FUGU = "侮"  # 侮: carries an SVS variant in the bundled font's format-14.
VS1 = "︀"  # Standardized variation selector (SVS).
PUA = ""  # Private Use Area: no glyph in a normal font.


def test_supports_plain_char(font):
    assert font.supports("辻鯛テ体")


def test_missing_reports_unsupported(font):
    missing = font.missing(f"辻{PUA}鯛")
    assert missing == [PUA]
    assert not font.supports(PUA)


def test_ivs_selects_a_different_glyph(font):
    # For 辻 the default glyph is CID+8267; VS17 selects the distinct CID+3056.
    plain = font.glyph_name(TSUJI)
    assert plain == "cid08267"
    variant = font.glyph_name(TSUJI, [VS17])
    assert variant == "cid03056"
    assert variant != plain


def test_ivs_resolved_via_font_uvs_not_only_ivd(font):
    # The format-14 subtable is the source of truth: 辻+VS17 resolves even
    # though we no longer consult the IVD first.
    assert font.glyph_name(TSUJI, [VS17]) == "cid03056"


def test_default_uvs_selector_falls_back_to_base_glyph(font):
    # 辻+VS18 is a *default* UVS record in this font (glyph name None), which
    # means "render the base's usual glyph" — i.e. the plain cmap glyph.
    assert font.glyph_name(TSUJI, [VS18]) == font.glyph_name(TSUJI)
    assert font.glyph_name(TSUJI, [VS18]) == "cid08267"


def test_svs_selects_a_different_glyph(font):
    # SVS (U+FE00–U+FE0F) is now honoured via the font's format-14 subtable:
    # 侮+VS1 maps to a distinct glyph, resolved without any Adobe-Japan1 IVD hit.
    plain = font.glyph_name(FUGU)
    variant = font.glyph_name(FUGU, [VS1])
    assert variant == "cid13382"
    assert variant != plain


def test_ivs_falls_back_to_base_when_selector_unknown(font):
    # 'A' + selector is not in the IVD, so it falls back to the plain glyph.
    assert font.glyph_name("A", [VS18]) == font.glyph_name("A")


def test_unmapped_svs_selector_is_swallowed_into_base(font):
    # A presentation selector (VS16, U+FE0F) that the font's format-14 does not
    # map attaches to the base and is swallowed: the base glyph renders and the
    # cluster is NOT reported as unsupported. This pins the clustering behavior
    # introduced by recognising SVS selectors.
    vs16 = "️"
    assert font.glyph_name("あ", [vs16]) == font.glyph_name("あ")
    assert font.missing(f"あ{vs16}") == []
    # A stray selector with no base is dropped, so it is never "missing".
    assert font.missing(vs16) == []


def test_resolve_run_skips_missing(font):
    run = font.resolve_run(f"辻{PUA}鯛", on_missing="skip")
    clusters = [cluster for cluster, _ in run]
    assert clusters == ["辻", "鯛"]


def test_resolve_run_raises_on_missing(font):
    with pytest.raises(UnsupportedCharacterError) as exc:
        font.resolve_run(PUA, on_missing="raise")
    assert exc.value.characters == [PUA]


def test_missing_unicode_cmap_raises(font_path, monkeypatch):
    tt = TTFont(str(font_path), lazy=True)
    monkeypatch.setattr(tt, "getBestCmap", lambda: None)
    with pytest.raises(MojivsError):
        IVSFont(tt)
