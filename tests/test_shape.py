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


def test_is_upright_in_vertical():
    from mojivs.shaping import is_upright_in_vertical

    assert is_upright_in_vertical("あ")
    assert is_upright_in_vertical("辻")
    assert is_upright_in_vertical("、")
    assert not is_upright_in_vertical("A")
    assert not is_upright_in_vertical("1")


def _is_rotated(pg):
    # Upright glyphs are a pure scale (xx != 0); rotated glyphs swap axes (xx == 0).
    return pg.transform[0] == 0 and pg.transform[1] != 0


def test_vertical_mixed_rotates_latin_only(font):
    shaped = font.shape("Aあ", size=64, direction="vertical")  # mixed by default
    assert _is_rotated(shaped.glyphs[0])  # A rotated
    assert not _is_rotated(shaped.glyphs[1])  # あ upright


def test_vertical_upright_orientation_keeps_latin_upright(font):
    shaped = font.shape("Aあ", size=64, direction="vertical", orientation="upright")
    assert not _is_rotated(shaped.glyphs[0])
    assert not _is_rotated(shaped.glyphs[1])


def test_tate_chu_yoko_groups_digits_into_one_cell(font):
    # Without TCY the two digits are separate (rotated) cells stacked vertically.
    plain = font.shape("25", size=64, direction="vertical")
    assert plain.glyphs[0].y != plain.glyphs[1].y

    # With TCY they share one cell: same baseline (y), side by side (different x).
    tcy = font.shape("25", size=64, direction="vertical", tate_chu_yoko=2)
    assert len(tcy.glyphs) == 2
    assert tcy.glyphs[0].y == tcy.glyphs[1].y
    assert tcy.glyphs[0].x != tcy.glyphs[1].x
    assert not _is_rotated(tcy.glyphs[0])  # upright
    assert tcy.height < plain.height


def test_tate_chu_yoko_chunks_long_runs(font):
    # A 4-digit run with limit 2 is chunked into two upright cells ("20", "24").
    shaped = font.shape("2024", size=64, direction="vertical", tate_chu_yoko=2)
    assert len(shaped.glyphs) == 4
    assert not any(_is_rotated(g) for g in shaped.glyphs)
    baselines = {round(g.y, 3) for g in shaped.glyphs}
    assert len(baselines) == 2  # two cells, two baselines
