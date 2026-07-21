"""Command-line interface for mojivs (the ``mojivs`` command).

Render IVS-aware Japanese text to an image or SVG, or inspect a font's coverage,
without writing any Python::

    mojivs render "辻\\U000e0100鯛" --font Gothic.otf -o out.png --escape
    mojivs supports "辻鯛テ体" --font Gothic.otf
    mojivs missing  "辻鯛𠮷"   --font Gothic.otf
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import __version__
from .errors import MojivsError
from .font import IVSFont

# Interpret only the escapes useful for typing variation selectors on a shell,
# without the Latin-1 mangling that ``str.encode().decode("unicode_escape")``
# would inflict on the surrounding Japanese text.
_ESCAPE_RE = re.compile(r"\\U[0-9A-Fa-f]{8}|\\u[0-9A-Fa-f]{4}|\\n|\\t")
_ESCAPE_MAP = {"\\n": "\n", "\\t": "\t"}


def _unescape(text: str) -> str:
    """Turn ``\\U000e0100`` / ``\\uXXXX`` / ``\\n`` escapes into real characters."""

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in _ESCAPE_MAP:
            return _ESCAPE_MAP[token]
        return chr(int(token[2:], 16))

    return _ESCAPE_RE.sub(repl, text)


def _add_layout_style_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--size", type=int, default=64, help="Em size in pixels (default: 64).")
    parser.add_argument(
        "--direction",
        choices=("horizontal", "vertical"),
        default="horizontal",
        help="Writing direction (default: horizontal).",
    )
    parser.add_argument(
        "--align",
        choices=("start", "center", "end"),
        default="start",
        help="Alignment across lines (default: start).",
    )
    parser.add_argument(
        "--orientation",
        choices=("mixed", "upright"),
        default="mixed",
        help="Vertical text: rotate Latin/digits (mixed) or keep upright.",
    )
    parser.add_argument(
        "--tate-chu-yoko",
        type=int,
        default=0,
        metavar="N",
        help="Vertical text: set runs of up to N digits upright and horizontal.",
    )
    parser.add_argument("--line-spacing", type=float, default=1.0, help="Line spacing multiplier.")
    parser.add_argument("--letter-spacing", type=float, default=0.0, help="Extra letter spacing.")
    parser.add_argument("--padding", type=int, default=0, help="Padding in pixels.")
    parser.add_argument("--color", default="#000000", help="Fill color (default: #000000).")
    parser.add_argument("--stroke", default=None, help="Stroke (outline) color. Default: none.")
    parser.add_argument("--stroke-width", type=float, default=0.0, help="Stroke width in pixels.")
    parser.add_argument(
        "--background", default=None, help="Background color. Default: transparent."
    )


def _layout_style_kwargs(args: argparse.Namespace) -> dict:
    return {
        "size": args.size,
        "direction": args.direction,
        "align": args.align,
        "orientation": args.orientation,
        "tate_chu_yoko": args.tate_chu_yoko,
        "line_spacing": args.line_spacing,
        "letter_spacing": args.letter_spacing,
        "padding": args.padding,
        "color": args.color,
        "stroke": args.stroke,
        "stroke_width": args.stroke_width,
        "background": args.background,
        "on_missing": args.on_missing,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mojivs",
        description="IVS-aware Japanese text rendering (異体字 → image/SVG).",
    )
    parser.add_argument("--version", action="version", version=f"mojivs {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_text_and_font(p: argparse.ArgumentParser) -> None:
        p.add_argument("text", help="Text to process. Use --escape to type \\U... selectors.")
        p.add_argument(
            "--font", required=True, type=Path, help="Path to an OpenType/TrueType font."
        )
        p.add_argument(
            "--escape",
            action="store_true",
            help="Interpret \\U000e0100 / \\uXXXX / \\n escapes in TEXT.",
        )

    render = sub.add_parser("render", help="Render text to a PNG or SVG file.")
    add_text_and_font(render)
    render.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path. Format inferred from extension (.png/.svg); default out.png.",
    )
    render.add_argument(
        "--format",
        choices=("png", "svg"),
        default=None,
        help="Output format when it cannot be inferred from --output.",
    )
    render.add_argument(
        "--backend",
        choices=("cairo", "freetype"),
        default="cairo",
        help="Rasterizer backend for PNG (default: cairo).",
    )
    render.add_argument(
        "--on-missing",
        choices=("raise", "skip"),
        default="raise",
        help="Unsupported clusters: raise an error (default) or skip them.",
    )
    _add_layout_style_args(render)

    for name, help_text in (
        ("supports", "Print 'true'/'false' for whether the font covers TEXT."),
        ("missing", "Print the clusters the font cannot render, one per line."),
    ):
        p = sub.add_parser(name, help=help_text)
        add_text_and_font(p)

    return parser


def _resolve_format(args: argparse.Namespace) -> str:
    if args.output is not None:
        suffix = args.output.suffix.lower()
        if suffix == ".svg":
            return "svg"
        if suffix == ".png":
            return "png"
    return args.format or "png"


def _run_render(args: argparse.Namespace) -> int:
    font = IVSFont(args.font)
    text = _unescape(args.text) if args.escape else args.text
    fmt = _resolve_format(args)
    output = args.output or Path(f"out.{fmt}")

    kwargs = _layout_style_kwargs(args)
    if fmt == "svg":
        output.write_text(font.to_svg(text, **kwargs), encoding="utf-8")
    else:
        font.render(text, backend=args.backend, **kwargs).save(output)
    print(f"wrote {output}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "render":
            return _run_render(args)

        font = IVSFont(args.font)
        text = _unescape(args.text) if getattr(args, "escape", False) else args.text
        if args.command == "supports":
            print("true" if font.supports(text) else "false")
            return 0
        if args.command == "missing":
            for cluster in font.missing(text):
                print(cluster)
            return 0
    except (MojivsError, OSError, RuntimeError) as exc:
        print(f"mojivs: error: {exc}", file=sys.stderr)
        return 1
    return 0  # pragma: no cover - unreachable; subcommand is required


if __name__ == "__main__":
    raise SystemExit(main())
