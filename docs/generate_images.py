"""Generate the README images under ``docs/images/``.

Run from anywhere after ``pip install -e ".[dev]"`` (needs the cairo backend):

    python docs/generate_images.py

Produces:
  hero_ivs.png       辻+VS17 across Pillow BASIC / Pillow+libraqm / mojivs.
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
GREEN = "#2e7d32"
LINE = "#e5e7eb"
BG = "#ffffff"

TSUJI = "辻"
VS17 = "\U000e0100"  # one-dot shinnyō — differs from the font's default glyph
VS18 = "\U000e0101"  # two-dot shinnyō — same as the default glyph for this font


def _center_glyph(canvas: Image.Image, box: tuple[int, int, int, int], glyph: Image.Image) -> None:
    x0, y0, x1, y1 = box
    gx = x0 + (x1 - x0 - glyph.width) // 2
    gy = y0 + (y1 - y0 - glyph.height) // 2
    canvas.alpha_composite(glyph, (gx, gy))


def make_hero(font: IVSFont) -> None:
    """Three columns rendering the same request: 辻 + VS17 (one-dot shinnyō).

    * Pillow BASIC layout ignores the selector and shows the default glyph.
    * Pillow with libraqm (HarfBuzz) shapes the selector via the font's UVS
      cmap and gets the right glyph — but needs libraqm installed.
    * mojivs resolves the IVS through the Adobe-Japan1 IVD with fonttools only:
      correct glyph, no HarfBuzz and no dependence on the font's UVS cmap.

    The honest point is not "Pillow can't" but "mojivs needs no HarfBuzz".
    """
    from PIL import features

    if not features.check("raqm"):
        raise RuntimeError(
            "generating the hero needs Pillow built with libraqm (raqm) so the "
            "'Pillow + libraqm' column is real; install libraqm and retry."
        )

    glyph_px = 150
    cell = 250
    margin = 40
    title_font = ImageFont.truetype(str(FONT_PATH), 30)
    name_font = ImageFont.truetype(str(FONT_PATH), 27)
    engine_font = ImageFont.truetype(str(FONT_PATH), 21)
    status_font = ImageFont.truetype(str(FONT_PATH), 21)
    small_font = ImageFont.truetype(str(FONT_PATH), 21)

    title = "「辻」＋ VS17（一点しんにょう）を指定して描画"
    caption = "同じ入力でも結果が違う。mojivs は fonttools だけで IVS を解決（HarfBuzz も UVS cmap も不要）"

    width = margin * 2 + cell * 3
    title_y = margin
    name_y = margin + 56
    engine_y = name_y + 32
    glyph_top = engine_y + 40
    status_y = glyph_top + glyph_px + 40
    caption_y = status_y + 44
    height = caption_y + 40

    # Ensure the caption is not clipped (it is the widest line).
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    width = max(width, int(margin * 2 + measure.textlength(caption, font=small_font)))

    img = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(img)
    draw.text((margin, title_y), title, font=title_font, fill=INK)

    font_basic = ImageFont.truetype(str(FONT_PATH), glyph_px, layout_engine=ImageFont.Layout.BASIC)
    font_raqm = ImageFont.truetype(str(FONT_PATH), glyph_px, layout_engine=ImageFont.Layout.RAQM)

    columns = [
        ("Pillow", "BASIC レイアウト", "セレクタを無視", ACCENT, "pil_basic"),
        ("Pillow", "＋ libraqm", "正しい（HarfBuzz 必須）", GREEN, "pil_raqm"),
        ("mojivs", "libraqm 不要", "正しい（IVD で解決）", GREEN, "mojivs"),
    ]

    for i, (name, engine, status, status_color, how) in enumerate(columns):
        cx = margin + cell * i + cell // 2
        gy = glyph_top + glyph_px // 2
        draw.text((cx, name_y), name, font=name_font, fill=INK, anchor="mm")
        draw.text((cx, engine_y), engine, font=engine_font, fill=MUTED, anchor="mm")
        if how == "pil_basic":
            # BASIC ignores the selector, so this is the default glyph (two-dot).
            draw.text((cx, gy), TSUJI, font=font_basic, fill=INK, anchor="mm")
        elif how == "pil_raqm":
            draw.text((cx, gy), TSUJI + VS17, font=font_raqm, fill=INK, anchor="mm")
        else:
            glyph = font.render(TSUJI + VS17, size=glyph_px, color=INK)
            box = (margin + cell * i, glyph_top, margin + cell * (i + 1), glyph_top + glyph_px)
            _center_glyph(img, box, glyph)
        draw.text((cx, status_y), status, font=status_font, fill=status_color, anchor="mm")

    for i in (1, 2):
        x = margin + cell * i
        draw.line((x, name_y - 24, x, status_y + 20), fill=LINE, width=2)

    draw.text((margin, caption_y), caption, font=small_font, fill=MUTED)
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
