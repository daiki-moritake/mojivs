"""Render Japanese text with IVS variants to PNG files.

Run from the repository root (after `pip install -e .`):

    python examples/basic.py
"""

from pathlib import Path

from mojivs import IVSFont

FONT = Path(__file__).resolve().parent.parent / (
    "fonts/HaranoAjiFonts-master/HaranoAjiGothic-Medium.otf"
)
OUT = Path(__file__).resolve().parent

# 辻 followed by variation selectors selects different 異体字 glyph forms.
TEXT = "辻\U000e0100 辻\U000e0101 鯛\U000e0100"


def main() -> None:
    font = IVSFont(FONT)

    # 1. Natural layout at a given em size.
    font.render(TEXT, size=96, color="#1a1a1a").save(OUT / "natural.png")

    # 2. Outlined text.
    font.render(
        "異体字レンダリング",
        size=96,
        color="#ffffff",
        stroke="#e5484d",
        stroke_width=6,
        background="#1a1a1a",
    ).save(OUT / "outlined.png")

    # 3. Multi-line, centered.
    font.render(
        "異体字\nレンダリング", size=64, align="center", color="#111"
    ).save(OUT / "multiline.png")

    # 4. Vertical writing (columns run right-to-left; punctuation is substituted).
    #    orientation="mixed" (default) rotates Latin/digits 90°; tate_chu_yoko
    #    sets short digit runs upright and horizontal (縦中横).
    font.render(
        "辻\U000e0100鯛の\n「縦書き」ABC\n平成31年5月",
        size=72,
        direction="vertical",
        tate_chu_yoko=2,
        color="#111",
    ).save(OUT / "vertical.png")

    # 5. Fit into an exact pixel box (compresses or justifies to fill).
    font.render_to_box("辻鯛テ体", (400, 80), color="#000").save(OUT / "boxed.png")

    # 6. Vector output. SVG needs no extra deps; PDF needs `mojivs[pdf]`.
    (OUT / "sample.svg").write_text(font.to_svg(TEXT, size=96, color="#1a1a1a"))
    try:
        font.to_pdf(TEXT, OUT / "sample.pdf", size=96)
    except RuntimeError as exc:
        print("skipping PDF:", exc)

    # Inspect coverage without rendering.
    print("supports 辻鯛テ体:", font.supports("辻鯛テ体"))
    print("missing in '辻鯛':", font.missing("辻鯛"))


if __name__ == "__main__":
    main()
