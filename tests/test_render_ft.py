"""Tests for the optional FreeType rasterizer backend (``backend="freetype"``).

The FreeType and cairo backends share the shaping layer, so they place glyphs on
identically sized canvases; only the anti-aliased edge pixels differ. These tests
assert that shared-canvas invariant plus a tight tolerance on the pixel delta,
and that stroking falls back to cairo exactly.
"""

import numpy as np
import pytest

pytest.importorskip("freetype", reason="freetype-py not installed")


def _mean_abs_diff(a, b):
    return np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)).mean()


def _p99_abs_diff(a, b):
    return np.percentile(np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)), 99)


FILL_CASES = [
    pytest.param(dict(text="日本語Aa1", direction="horizontal"), id="horizontal"),
    pytest.param(
        dict(text="縦書きAbc", direction="vertical", orientation="mixed"),
        id="vertical-mixed",
    ),
    pytest.param(
        dict(text="縦書き123", direction="vertical", orientation="upright"),
        id="vertical-upright",
    ),
    pytest.param(
        dict(text="平成30年", direction="vertical", tate_chu_yoko=2),
        id="tate-chu-yoko",
    ),
    pytest.param(dict(text="一行目\n二行目", direction="horizontal"), id="multiline"),
    pytest.param(
        dict(text="背景Ab", direction="horizontal", background="#ffcc00"),
        id="background",
    ),
]


@pytest.mark.parametrize("case", FILL_CASES)
def test_freetype_matches_cairo_fill(font, case):
    cairo_img = font.render(size=48, color="#102080", backend="cairo", **case)
    ft_img = font.render(size=48, color="#102080", backend="freetype", **case)

    # Shared shaping -> identical canvas size and mode.
    assert ft_img.size == cairo_img.size
    assert ft_img.mode == cairo_img.mode == "RGBA"
    # Both backends actually drew ink.
    assert ft_img.getchannel("A").getbbox() is not None
    # Only anti-aliased edges differ; the bulk of the canvas is identical.
    assert _mean_abs_diff(cairo_img, ft_img) < 2.0
    assert _p99_abs_diff(cairo_img, ft_img) <= 32


def test_freetype_stroke_falls_back_to_cairo(font):
    # The FreeType backend only fills, so a stroked render must reproduce the
    # cairo path exactly (byte-for-byte), not just approximately.
    kw = dict(text="袋文字", size=48, color="#ffffff", stroke="#000000", stroke_width=3)
    cairo_img = font.render(backend="cairo", **kw)
    ft_img = font.render(backend="freetype", **kw)
    assert ft_img.tobytes() == cairo_img.tobytes()


def test_freetype_transparent_stroke_still_uses_freetype(font):
    # A stroke width with a fully transparent stroke color draws no outline, so
    # the FreeType backend should stay engaged (and match the cairo fill).
    kw = dict(text="透明枠", size=48, color="#000000", stroke=(0, 0, 0, 0), stroke_width=4)
    cairo_img = font.render(backend="cairo", **kw)
    ft_img = font.render(backend="freetype", **kw)
    assert ft_img.size == cairo_img.size
    assert _mean_abs_diff(cairo_img, ft_img) < 2.0


def test_render_to_box_freetype_matches_cairo(font):
    box = (300, 40)
    cairo_img = font.render_to_box("辻鯛テ体", box, color="#101010", backend="cairo")
    ft_img = font.render_to_box("辻鯛テ体", box, color="#101010", backend="freetype")
    assert ft_img.size == cairo_img.size == box
    assert ft_img.getchannel("A").getbbox() is not None
    assert _mean_abs_diff(cairo_img, ft_img) < 2.0
    assert _p99_abs_diff(cairo_img, ft_img) <= 32


def test_freetype_works_without_cairo(font, monkeypatch):
    # The whole point of the backend: rasterize with no pycairo present. Simulate
    # a cairo-free install and confirm the freetype path never touches cairo.
    import importlib

    # ``from .render import render`` in the package __init__ shadows the module
    # name, so reach the real module object via importlib to patch its global.
    render_mod = importlib.import_module("mojivs.render")
    monkeypatch.setattr(render_mod, "cairo", None)
    img = font.render("辻鯛テ", size=48, backend="freetype")
    assert img.mode == "RGBA"
    assert img.getchannel("A").getbbox() is not None


def test_render_rejects_unknown_backend(font):
    with pytest.raises(ValueError, match="backend"):
        font.render("辻", size=32, backend="gpu")


def test_render_to_box_rejects_unknown_backend(font):
    with pytest.raises(ValueError, match="backend"):
        font.render_to_box("辻", (100, 40), backend="gpu")
