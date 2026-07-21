"""Tests for the pure IVS resolver layer (no rendering)."""

from mojivs import ivs

# U+8FBB 辻 + selector U+E0101 -> Adobe-Japan1 CID+8267 (per the bundled IVD).
TSUJI = "辻"
VS17 = "\U000e0100"
VS18 = "\U000e0101"
VS1 = "︀"  # Standardized variation selector (SVS), VS1.
VS16 = "️"  # SVS, VS16 (emoji presentation selector).


def test_is_variation_selector():
    assert ivs.is_variation_selector(VS17)
    assert ivs.is_variation_selector(VS18)
    assert not ivs.is_variation_selector("A")
    assert not ivs.is_variation_selector(TSUJI)


def test_is_variation_selector_accepts_svs():
    # SVS selectors (U+FE00–U+FE0F) also cluster onto the preceding base.
    assert ivs.is_variation_selector(VS1)
    assert ivs.is_variation_selector(VS16)


def test_iter_clusters_groups_selectors():
    text = f"A{TSUJI}{VS18}B"
    assert list(ivs.iter_clusters(text)) == [
        ("A", []),
        (TSUJI, [VS18]),
        ("B", []),
    ]


def test_iter_clusters_groups_svs_selector():
    fugu = "侮"  # 侮
    assert list(ivs.iter_clusters(f"{fugu}{VS1}")) == [(fugu, [VS1])]


def test_iter_clusters_groups_emoji_presentation_selector():
    # VS16 (U+FE0F) attaches to the preceding base rather than forming its own
    # cluster, so it is never treated as a standalone (unsupported) character.
    sun = "☀"
    assert list(ivs.iter_clusters(f"{sun}{VS16}")) == [(sun, [VS16])]


def test_iter_clusters_skips_stray_svs_selector():
    # A leading SVS selector with no base character is dropped, same as IVS.
    assert list(ivs.iter_clusters(f"{VS16}A")) == [("A", [])]


def test_iter_clusters_skips_stray_selector():
    # A leading selector with no base character is dropped.
    assert list(ivs.iter_clusters(f"{VS18}A")) == [("A", [])]


def test_cid_glyph_name_resolves_known_sequence():
    assert ivs.cid_glyph_name(TSUJI, [VS17]) == "cid03056"
    assert ivs.cid_glyph_name(TSUJI, [VS18]) == "cid08267"


def test_cid_glyph_name_without_selector_is_none():
    assert ivs.cid_glyph_name(TSUJI, []) is None


def test_cid_glyph_name_unknown_sequence_is_none():
    # 'A' + a variation selector is not an Adobe-Japan1 sequence.
    assert ivs.cid_glyph_name("A", [VS18]) is None


def test_cid_glyph_name_ignores_svs():
    # The Adobe-Japan1 IVD only uses IVS selectors, so an SVS sequence misses
    # here and is left for the font's format-14 subtable to resolve.
    assert ivs.cid_glyph_name("侮", [VS1]) is None
