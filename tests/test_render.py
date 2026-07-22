"""Smoke tests for the rasterizer."""

import pytest

from mojivs import UnsupportedCharacterError

PUA = "\ue000"  # Private Use Area character with no glyph.


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


def test_render_to_box_rejects_newline(font):
    with pytest.raises(ValueError):
        font.render_to_box("a\nb", (100, 40))


def test_render_does_not_clip_overhanging_ink(font):
    # 'f' overhangs its advance width; the canvas must grow to fit its ink so
    # padding=0 does not clip it. Its inked size must match a padded render
    # within anti-aliasing tolerance (a real clip would remove several pixels).
    tight = font.render("f", size=200, padding=0).getchannel("A").getbbox()
    padded = font.render("f", size=200, padding=10).getchannel("A").getbbox()
    assert tight is not None and padded is not None
    assert abs((tight[2] - tight[0]) - (padded[2] - padded[0])) <= 1  # ink width
    assert abs((tight[3] - tight[1]) - (padded[3] - padded[1])) <= 1  # ink height


def test_default_backend_needs_no_pycairo(font, monkeypatch):
    # The default backend is now the dependency-free 'builtin' rasterizer, so a
    # plain render must succeed even when pycairo is absent.
    import importlib

    # ``from .render import render`` in the package __init__ shadows the module
    # name, so reach the real module object via importlib to patch its global.
    render_mod = importlib.import_module("mojivs.render")
    monkeypatch.setattr(render_mod, "cairo", None)
    img = font.render("辻", size=32)
    assert img.mode == "RGBA"
    assert img.getchannel("A").getbbox() is not None


def test_explicit_cairo_backend_requires_pycairo(font, monkeypatch):
    # Explicitly asking for the cairo backend must fail with a clear, actionable
    # error when pycairo is absent (not an AttributeError on ``None``).
    import importlib

    render_mod = importlib.import_module("mojivs.render")
    monkeypatch.setattr(render_mod, "cairo", None)
    with pytest.raises(RuntimeError, match="pycairo"):
        font.render("辻", size=32, backend="cairo")


def test_stroke_falls_back_to_cairo_and_needs_pycairo(font, monkeypatch):
    # Only cairo strokes, so a stroked render on the default backend routes to
    # cairo and surfaces the same clear error when pycairo is missing.
    import importlib

    render_mod = importlib.import_module("mojivs.render")
    monkeypatch.setattr(render_mod, "cairo", None)
    with pytest.raises(RuntimeError, match="pycairo"):
        font.render("辻", size=32, stroke="#f00", stroke_width=4)


def test_invalid_backend_raises(font):
    with pytest.raises(ValueError, match="backend"):
        font.render("辻", size=32, backend="nope")


def test_builtin_backend_renders_counters_as_holes(font):
    # 回 has nested counters; non-zero winding must leave them transparent rather
    # than filling them (an even-odd or winding bug would flood the interior).
    img = font.render("回", size=128, color="#000", backend="builtin")
    alpha = img.getchannel("A")
    box = alpha.getbbox()
    assert box is not None
    # Sample the glyph's centre: it sits inside the innermost counter, which must
    # be empty (transparent).
    cx = (box[0] + box[2]) // 2
    cy = (box[1] + box[3]) // 2
    assert alpha.getpixel((cx, cy)) == 0


def test_builtin_matches_optional_backends(font):
    # The builtin rasterizer should agree closely with cairo/freetype (only
    # anti-aliasing at edges may differ). Skip whichever backend is unavailable.
    builtin = font.render("辻鯛回0", size=96, color="#000", backend="builtin")
    for name in ("cairo", "freetype"):
        try:
            other = font.render("辻鯛回0", size=96, color="#000", backend=name)
        except RuntimeError:
            continue  # optional backend not installed
        assert other.size == builtin.size
        a = builtin.tobytes()
        b = other.tobytes()
        # Mean absolute per-byte difference stays tiny (edges only).
        diff = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
        assert diff < 3.0, f"builtin vs {name} mean diff {diff:.2f} too high"


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


def test_render_vertical_mixed_and_tcy(font):
    # Rotated Latin and tate-chu-yoko digits should both rasterize without error.
    rotated = font.render("縦ABC\n令和6年", size=48, direction="vertical")
    tcy = font.render("平成31年", size=48, direction="vertical", tate_chu_yoko=2)
    for img in (rotated, tcy):
        assert img.mode == "RGBA"
        assert img.getchannel("A").getbbox() is not None
