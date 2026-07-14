"""Tests for the shaping layer: multiline, alignment and vertical layout."""

import pytest


def test_shape_horizontal_counts_glyphs(font):
    shaped = font.shape("辻鯛テ", size=64)
    assert shaped.direction == "horizontal"
    assert len(shaped.glyphs) == 3
    assert shaped.width > 0 and shaped.height > 0


def test_multiline_is_taller_and_keeps_all_glyphs(font):
    one = font.shape("辻鯛", size=64)
    two = font.shape("辻鯛\nテ体", size=64)
    assert len(two.glyphs) == 4
    assert two.height > one.height
    # Second line sits below the first (larger baseline y).
    assert two.glyphs[2].y > two.glyphs[0].y


def test_align_center_offsets_shorter_line(font):
    shaped = font.shape("辻鯛テ\n体", size=64, align="center")
    first_line_x = shaped.glyphs[0].x
    short_line_x = shaped.glyphs[3].x  # the lone 体 on line 2
    assert short_line_x > first_line_x


def test_vertical_layout_columns_right_to_left(font):
    shaped = font.shape("あい\nうえ", size=64, direction="vertical")
    assert shaped.direction == "vertical"
    assert len(shaped.glyphs) == 4
    # First column is visually rightmost -> larger x than the second column.
    assert shaped.glyphs[0].x > shaped.glyphs[2].x
    # Within a column, glyphs stack downward.
    assert shaped.glyphs[1].y > shaped.glyphs[0].y


def test_vertical_substitutes_punctuation(font):
    shaped = font.shape("あ。", size=64, direction="vertical")
    clusters = [g.cluster for g in shaped.glyphs]
    # The full-width period is replaced by its vertical presentation form.
    assert clusters == ["あ", "︒"]


def test_vertical_requires_vertical_metrics(font, monkeypatch):
    monkeypatch.setattr(font, "_vmtx", None)
    with pytest.raises(ValueError):
        font.shape("あ", direction="vertical")
