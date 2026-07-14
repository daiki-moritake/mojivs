"""Tests for the pure IVS resolver layer (no rendering)."""

from mojivs import ivs

# U+8FBB 辻 + selector U+E0101 -> Adobe-Japan1 CID+8267 (per the bundled IVD).
TSUJI = "辻"
VS17 = "\U000e0100"
VS18 = "\U000e0101"


def test_is_variation_selector():
    assert ivs.is_variation_selector(VS17)
    assert ivs.is_variation_selector(VS18)
    assert not ivs.is_variation_selector("A")
    assert not ivs.is_variation_selector(TSUJI)


def test_iter_clusters_groups_selectors():
    text = f"A{TSUJI}{VS18}B"
    assert list(ivs.iter_clusters(text)) == [
        ("A", []),
        (TSUJI, [VS18]),
        ("B", []),
    ]


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
