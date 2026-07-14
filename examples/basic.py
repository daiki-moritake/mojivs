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

    # 3. Fit into an exact pixel box (compresses or justifies to fill).
    font.render_to_box("辻鯛テ体", (400, 80), color="#000").save(OUT / "boxed.png")

    # Inspect coverage without rendering.
    print("supports 辻鯛テ体:", font.supports("辻鯛テ体"))
    print("missing in '辻鯛':", font.missing("辻鯛"))


if __name__ == "__main__":
    main()
