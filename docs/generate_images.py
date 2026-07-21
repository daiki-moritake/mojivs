"""Generate the README images under ``docs/images/``.

Run from anywhere after ``pip install -e ".[dev]"`` (needs the cairo backend):

    python docs/generate_images.py

Produces:
  hero_ivs.png       Pillow vs mojivs on the same 辻 + different selectors.
  feature_outline.png  Stroked text on a dark background.
  feature_vertical.png Vertical writing with tate-chu-yoko.
  feature_box.png      Fit into an exact pixel box.

The images are committed so the README renders on PyPI and GitHub without a build
step. Re-run this script whenever the rendering output changes.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from mojivs import IVSFont

ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = ROOT / "fonts/HaranoAjiFonts-master/HaranoAjiGothic-Medium.otf"
OUT = ROOT / "docs" / "images"

INK = "#1a1a1a"
MUTED = "#6b7280"
ACCENT = "#e5484d"
LINE = "#e5e7eb"
BG = "#ffffff"

TSUJI = "辻"
VS17 = "\U000e0100"  # one-dot shinnyō
VS18 = "\U000e0101"  # two-dot shinnyō


def _center_glyph(canvas: Image.Image, box: tuple[int, int, int, int], glyph: Image.Image) -> None:
    x0, y0, x1, y1 = box
    gx = x0 + (x1 - x0 - glyph.width) // 2
    gy = y0 + (y1 - y0 - glyph.height) // 2
    canvas.alpha_composite(glyph, (gx, gy))


def make_hero(font: IVSFont) -> None:
    """A 2x2 grid: rows Pillow/mojivs, columns +VS17/+VS18.

    Pillow renders the base glyph identically regardless of the selector; mojivs
    resolves each selector to its own Adobe-Japan1 glyph. Seeing the two mojivs
    cells differ (and the two Pillow cells match) is the whole pitch.
    """
    glyph_px = 160
    cell = 220
    margin = 40
    label_w = 120  # room for row labels on the left
    grid_left = margin + label_w
    title_band = 52
    header_band = 40

    title_font = ImageFont.truetype(str(FONT_PATH), 30)
    label_font = ImageFont.truetype(str(FONT_PATH), 26)
    small_font = ImageFont.truetype(str(FONT_PATH), 22)
    pil_glyph_font = ImageFont.truetype(str(FONT_PATH), glyph_px)

    title = "同じ「辻」＋ 異なる異体字セレクタ"
    caption = "Pillow は字形が変わらない ／ mojivs は正しい異体字になる"

    # Size the canvas so nothing (title/caption/grid) is clipped.
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    grid_right = grid_left + cell * 2
    content_right = max(
        grid_right,
        margin + measure.textlength(title, font=title_font),
        margin + measure.textlength(caption, font=small_font),
    )
    width = int(content_right + margin)
    grid_top = margin + title_band + header_band
    height = grid_top + cell * 2 + title_band

    img = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(img)

    draw.text((margin, margin), title, font=title_font, fill=INK)

    col_x = [grid_left, grid_left + cell]
    row_y = [grid_top, grid_top + cell]

    for cx, header in zip(col_x, ("＋VS17", "＋VS18")):
        draw.text(
            (cx + cell // 2, grid_top - header_band // 2),
            header,
            font=label_font,
            fill=MUTED,
            anchor="mm",
        )
    for cy, header, col in zip(row_y, ("Pillow", "mojivs"), (MUTED, ACCENT)):
        draw.text((grid_left - 24, cy + cell // 2), header, font=label_font, fill=col, anchor="rm")

    for j, sel in enumerate((VS17, VS18)):
        # Pillow row: the selector is ignored, so both columns look identical.
        draw.text(
            (col_x[j] + cell // 2, row_y[0] + cell // 2),
            TSUJI + sel,
            font=pil_glyph_font,
            fill=INK,
            anchor="mm",
        )
        # mojivs row: the IVS resolves to the correct (differing) glyph.
        glyph = font.render(TSUJI + sel, size=glyph_px, color=INK)
        _center_glyph(img, (col_x[j], row_y[1], col_x[j] + cell, row_y[1] + cell), glyph)

    draw.line((grid_left, row_y[1], grid_right, row_y[1]), fill=LINE, width=2)
    draw.line((col_x[1], grid_top, col_x[1], row_y[1] + cell), fill=LINE, width=2)

    draw.text((margin, height - title_band + 8), caption, font=small_font, fill=MUTED)
    img.convert("RGB").save(OUT / "hero_ivs.png")


def make_features(font: IVSFont) -> None:
    font.render(
        "袋文字・縁取り",
        size=88,
        color="#ffffff",
        stroke=ACCENT,
        stroke_width=6,
        background=INK,
        padding=24,
    ).convert("RGB").save(OUT / "feature_outline.png")

    font.render(
        "平成31年\n5月1日 令和",
        size=64,
        direction="vertical",
        tate_chu_yoko=2,
        color=INK,
        background=BG,
        padding=28,
    ).convert("RGB").save(OUT / "feature_vertical.png")

    font.render_to_box(
        "辻\U000e0100鯛テ体",
        (440, 96),
        color=INK,
        background=BG,
    ).convert("RGB").save(OUT / "feature_box.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    font = IVSFont(FONT_PATH)
    make_hero(font)
    make_features(font)
    for path in sorted(OUT.glob("*.png")):
        with Image.open(path) as im:
            print(f"  {path.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
