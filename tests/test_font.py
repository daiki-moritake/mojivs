"""Tests for IVSFont glyph resolution and support queries."""

import pytest

from mojivs import UnsupportedCharacterError

TSUJI = "辻"
VS17 = "\U000e0100"
VS18 = "\U000e0101"
PUA = "\uE000"  # Private Use Area: no glyph in a normal font.


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


def test_ivs_falls_back_to_base_when_selector_unknown(font):
    # 'A' + selector is not in the IVD, so it falls back to the plain glyph.
    assert font.glyph_name("A", [VS18]) == font.glyph_name("A")


def test_resolve_run_skips_missing(font):
    run = font.resolve_run(f"辻{PUA}鯛", on_missing="skip")
    clusters = [cluster for cluster, _ in run]
    assert clusters == ["辻", "鯛"]


def test_resolve_run_raises_on_missing(font):
    with pytest.raises(UnsupportedCharacterError) as exc:
        font.resolve_run(PUA, on_missing="raise")
    assert exc.value.characters == [PUA]
