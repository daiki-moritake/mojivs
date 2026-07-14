"""Smoke tests for the rasterizer."""

import pytest

from mojivs import UnsupportedCharacterError

PUA = "\uE000"  # Private Use Area character with no glyph.


def test_render_returns_rgba_image(font):
    img = font.render("辻鯛テ", size=48, color="#000")
    assert img.mode == "RGBA"
    assert img.width > 0 and img.height > 0
    # Something was actually drawn (non-empty alpha channel).
    assert img.getchannel("A").getbbox() is not None


def test_render_ivs_variant_differs_from_base(font):
    # VS17 selects a visibly different 異体字 form of 辻.
    base = font.render("辻", size=48)
    variant = font.render("辻\U000e0100", size=48)
    assert base.tobytes() != variant.tobytes()


def test_render_size_scales_height(font):
    small = font.render("辻", size=32)
    large = font.render("辻", size=64)
    assert large.height > small.height


def test_render_to_box_exact_size(font):
    img = font.render_to_box("辻鯛テ体", (300, 40))
    assert img.size == (300, 40)


def test_render_raises_on_unsupported(font):
    with pytest.raises(UnsupportedCharacterError):
        font.render(PUA, size=32)


def test_render_skips_unsupported(font):
    img = font.render(f"辻{PUA}鯛", size=32, on_missing="skip")
    assert img.mode == "RGBA"


def test_stroke_widens_image(font):
    plain = font.render("辻", size=48)
    stroked = font.render("辻", size=48, stroke="#f00", stroke_width=6)
    assert stroked.width >= plain.width


def test_render_multiline_is_taller(font):
    one = font.render("辻鯛", size=48)
    two = font.render("辻鯛\nテ体", size=48)
    assert two.height > one.height


def test_render_vertical(font):
    img = font.render("あいうえ", size=48, direction="vertical")
    assert img.mode == "RGBA"
    # A single vertical column is much taller than it is wide.
    assert img.height > img.width
    assert img.getchannel("A").getbbox() is not None
