# mojivs

[![CI](https://github.com/daiki-moritake/mojivs/actions/workflows/ci.yml/badge.svg)](https://github.com/daiki-moritake/mojivs/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[日本語](README.md) | **English**

**IVS-aware Japanese text → image renderer**

![The same 辻 with different variation selectors — Pillow vs mojivs](https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/hero_ivs.png)

Render Japanese text to images. In particular, it resolves **IVS (Ideographic
Variation Sequences / 異体字)** through the Adobe-Japan1 IVD and maps them to the
font's CID glyphs — something Pillow's `ImageFont` cannot do.

For example, variant forms of 辻, 葛, 髙, 﨑, 鯛 render with the correct glyph shape.

```
辻󠄀  辻󠄁      ← the same 辻, but the variation selector changes the glyph
             (one-dot vs two-dot shinnyō radical)
```

## Features

- **IVS applied to glyph shape** — base character + variation selector resolved
  to an Adobe-Japan1 CID.
- **Font parsed once** — the cmap, glyph set, and metrics are cached instead of
  being rebuilt on every render.
- **Horizontal / vertical / multi-line** — split rows/columns on `\n`; vertical
  writing honors `vmtx`/`VORG` and vertical punctuation forms.
- **Latin rotation & tate-chu-yoko** — rotate Latin/digits 90° in vertical text
  (`orientation`), or set short digit runs upright and horizontal
  (`tate_chu_yoko`).
- **Outline (stroke), background color, letter/line spacing, alignment**.
- **PNG / SVG / PDF output** — multiple formats from one layout engine.
- **Fit to a box** — fit text into an exact pixel rectangle (`render_to_box`).
- **Selectable backend** — cairo (default) or FreeType. `backend="freetype"` is
  cairo-free and faster (it falls back to cairo automatically when stroking).
- **Few dependencies** — the core is only `fonttools` / `pillow` / `numpy`. The
  rasterizer (`pycairo` or `freetype-py`) and PDF output (`reportlab`) are all
  optional extras.

## Gallery

**Outline (stroke) + background**

<img src="https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/feature_outline.png" alt="Stroked text" width="360">

**Vertical writing + tate-chu-yoko**

<img src="https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/feature_vertical.png" alt="Vertical writing with tate-chu-yoko" width="130">

**Fit into an exact pixel box (`render_to_box`)**

<img src="https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/feature_box.png" alt="Fit to a box" width="440">

## Installation

Install **at least one** rasterizer backend:

```bash
pip install mojivs[cairo]             # default backend (also required for strokes)
pip install mojivs[freetype]          # FreeType backend (cairo-free, faster)
pip install mojivs[cairo,freetype]    # both
```

[uv](https://docs.astral.sh/uv/) works the same way (it installs from PyPI):

```bash
uv pip install "mojivs[cairo]"        # into an existing environment
uv add "mojivs[cairo]"                # add to a uv-managed project
```

- **cairo** — required for the default backend and for stroked text. `pycairo`
  needs the native cairo library:

  ```bash
  # macOS
  brew install cairo pkg-config
  # Debian / Ubuntu
  sudo apt-get install libcairo2-dev pkg-config
  ```

- **freetype** — `freetype-py` ships self-contained wheels, so no system cairo
  is needed.

> `pip install mojivs` with no extras installs no rasterizer. `import mojivs`
> works, but the default `render()` uses the cairo backend — install
> `mojivs[cairo]`, or use `backend="freetype"` with `mojivs[freetype]`.

```bash
# Development (both backends + tests/type checking)
pip install -e ".[dev]"
```

## Usage

```python
from mojivs import IVSFont

font = IVSFont("fonts/HaranoAjiFonts-master/HaranoAjiGothic-Medium.otf")

# 1. Render with the font's natural metrics (em size).
img = font.render("辻\U000e0100鯛", size=96, color="#1a1a1a")
img.save("out.png")

# 2. With an outline (stroke).
font.render(
    "異体字レンダリング",
    size=96,
    color="#ffffff",
    stroke="#e5484d",
    stroke_width=6,
    background="#1a1a1a",
).save("outlined.png")

# 3. Multi-line (\n) and alignment.
font.render("異体字\nレンダリング", size=64, align="center").save("multiline.png")

# 4. Vertical writing (\n starts a new column, right-to-left; punctuation is
#    substituted with vertical forms).
font.render("辻\U000e0100鯛の\n「縦書き」。", size=72, direction="vertical").save("vertical.png")

# 4b. Latin rotation in vertical text (default orientation="mixed": Latin/digits
#     rotate 90°, kanji/kana stay upright).
font.render("縦書きABC\n令和6年です", size=64, direction="vertical").save("mixed.png")

# 4c. Tate-chu-yoko (short digit runs set upright and horizontal in one cell;
#     tate_chu_yoko = max digit count).
font.render("平成31年\n5月1日", size=64, direction="vertical", tate_chu_yoko=2).save("tcy.png")

# 5. Fit into an exact pixel box (compress if wide, justify spacing if narrow).
font.render_to_box("辻鯛テ体", (400, 80), color="#000").save("boxed.png")

# 5b. FreeType backend (optional, cairo-free and faster; requires mojivs[freetype]).
#     Output is nearly identical to cairo; strokes fall back to cairo automatically.
font.render("高速レンダリング", size=96, backend="freetype").save("ft.png")

# Vector output (SVG needs no extra deps; PDF needs reportlab).
open("out.svg", "w").write(font.to_svg("辻\U000e0100鯛", size=96))
font.to_pdf("辻\U000e0100鯛", "out.pdf", size=96)     # pip install mojivs[pdf]

# Check coverage without rendering.
font.supports("辻鯛テ体")   # -> True
font.missing("辻鯛𠮷")       # -> list of unsupported clusters
```

`\U000e0100` is variation selector VS17 (U+E0100); include it directly in the string.

### Command line (CLI)

Installing the package provides a `mojivs` command (`python -m mojivs` works too).

```bash
# Type variation selectors as \U... escapes with --escape
mojivs render '辻\U000e0100鯛' --font Gothic.otf --escape -o out.png --size 96

# Vertical writing + tate-chu-yoko; SVG is inferred from the extension
mojivs render '平成31年' --font Gothic.otf --direction vertical --tate-chu-yoko 2 -o out.svg

# Inspect font coverage
mojivs supports '辻鯛テ体' --font Gothic.otf   # -> true
mojivs missing  '辻鯛𠮷'   --font Gothic.otf   # unsupported clusters, one per line
```

Key options: `--size` `--color` `--stroke` `--stroke-width` `--background`
`--direction` `--align` `--orientation` `--tate-chu-yoko` `--backend`
(`cairo`|`freetype`) `--on-missing` (`raise`|`skip`). See `mojivs render --help`.

### Output formats and layout

`shape()` computes the layout, and PNG/SVG/PDF each draw that result. `render` /
`to_svg` / `to_pdf` accept the same layout arguments (`size`, `direction`,
`align`, `line_spacing`, `letter_spacing`, `padding`, `orientation`,
`tate_chu_yoko`) and style arguments (`color`, `stroke`, `stroke_width`,
`background`).

- `orientation` (vertical): `"mixed"` (default — rotate Latin/digits 90°) or
  `"upright"` (everything upright).
- `tate_chu_yoko` (vertical): `0` disables it. `N` sets runs of up to N halfwidth
  digits upright and horizontal (tate-chu-yoko).
- `backend` (`render` / `render_to_box` only): `"cairo"` (default) or
  `"freetype"`. This chooses the rasterizer only; the layout is unchanged (not
  applicable to SVG/PDF).

```python
from mojivs import IVSFont

font = IVSFont("...otf")
shaped = font.shape("辻\U000e0100鯛\nテ体", size=64, align="center")
shaped.width, shaped.height          # pixel size
shaped.glyphs                        # placed glyphs (PlacedGlyph)
```

### Specifying colors

`color` / `stroke` / `background` accept:

- Hex strings: `"#000"`, `"#1a1a1a"`, `"#1a1a1aff"`
- 0–255 tuples: `(26, 26, 26)` or `(26, 26, 26, 255)`
- `None` (the default for `stroke` / `background`: no stroke / no background)

## API

### `IVSFont(font, *, font_number=0)`

Loads a font once and caches subsequent lookups. `font` is a path or a
`fontTools.ttLib.TTFont`.

Common layout arguments: `size` / `direction` (`"horizontal"` | `"vertical"`) /
`align` (`"start"` | `"center"` | `"end"`) / `line_spacing` / `letter_spacing` /
`padding` / `orientation` (`"mixed"` | `"upright"`) / `tate_chu_yoko` (int).
Common style arguments: `color` / `stroke` / `stroke_width` / `background`.
The rasterizing methods (`render` / `render_to_box`) also accept `backend`
(`"cairo"` default | `"freetype"`).

| Method | Description |
|---|---|
| `render(text, *, ...) -> Image` | Return an RGBA image at natural metrics |
| `render_to_box(text, box, *, ...) -> Image` | Fit into `box=(width, height)` exactly (single horizontal line) |
| `shape(text, *, ...) -> ShapedText` | Return placed glyphs (`PlacedGlyph`) and size |
| `to_svg(text, *, ...) -> str` | Return an SVG document string |
| `to_pdf(text, path, *, ...) -> None` | Write a single-page PDF (requires `reportlab`) |
| `supports(text) -> bool` | Whether every cluster can be rendered |
| `missing(text) -> list[str]` | The clusters that cannot be rendered, in order |
| `glyph_name(base, selectors=None) -> str \| None` | Resolve the glyph name for a base + selectors |

`on_missing` is `"raise"` (default — `UnsupportedCharacterError`) or `"skip"`.

### `mojivs.ivs` (the render-independent resolver layer)

A pure layer that resolves IVS → CID without cairo/Pillow.

```python
from mojivs import ivs

ivs.is_variation_selector("\U000e0100")   # -> True
ivs.cid_glyph_name("辻", ["\U000e0100"])   # -> "cid03056"
list(ivs.iter_clusters("A辻\U000e0100"))   # -> [('A', []), ('辻', ['\U000e0100'])]
```

## Architecture

A lightweight resolver layer, with layout → per-format output built on top.

```
mojivs/
├─ ivs.py       … IVS → Adobe-Japan1 CID resolution (stdlib + fonttools only)
├─ font.py      … IVSFont: font loading and caching
├─ shaping.py   … shape(): text → placed glyphs (horizontal/vertical/multi-line)
├─ render.py    … rasterization via cairo/Pillow (PNG)
├─ render_ft.py … FreeType backend (optional; freetype-py; backend="freetype")
├─ export.py    … SVG (fonttools) / PDF (reportlab; optional) output
├─ colors.py    … color parsing
└─ data/ivd.txt … Unicode IVD (bundled data)
```

`shape()` is the single layout engine; PNG/SVG/PDF all render its result.

## Sample font

`fonts/` bundles only **`HaranoAjiGothic-Medium.otf`** (from the Harano Aji
Fonts, Adobe-Japan1-7, own license) for tests and examples. Other weights and
the Mincho family are downloadable from the link below (they are not tracked, to
keep the repository small).
<https://github.com/trueroad/HaranoAjiFonts>

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                       # tests
ruff check src tests         # lint (unused imports, real bugs)
ruff format src tests        # formatting
pyright                      # type checking

python examples/basic.py     # write PNGs into examples/
```

Lint/type-check settings live under `[tool.ruff]` / `[tool.pyright]` in
`pyproject.toml`. pyright runs in `basic` mode to suppress "stub not found"
noise from C extensions (pycairo, reportlab). CI (GitHub Actions) runs the same
four checks. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## Limitations / roadmap

- Latin rotation/upright in vertical text uses a **Unicode-range heuristic** (an
  approximation of UAX #50). Per-character vertical glyph selection is not
  supported.
- `tate_chu_yoko` only targets runs of halfwidth ASCII digits (mixed cases like
  `No.` are out of scope).
- Only the Adobe-Japan1 IVD collection is supported (Hanyo-Denshi / Moji_Joho are
  not yet resolved).
- No automatic line breaking (word wrap); only explicit `\n`.
- `render_to_box` supports a single horizontal line only.

## License

Code is MIT. See [LICENSE](LICENSE) for the bundled data and font licenses.
