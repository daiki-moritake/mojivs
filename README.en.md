# mojivs

[![CI](https://github.com/daiki-moritake/mojivs/actions/workflows/ci.yml/badge.svg)](https://github.com/daiki-moritake/mojivs/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[日本語](README.md) | **English**

**A Japanese renderer that fits text neatly into a given box (IVS / 異体字 aware)**

![The same phrase fitted edge-to-edge into a wide box, an exact box, and a narrow box](https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/hero_box.png)

**This library's purpose is to fill a given box neatly with text.** Pass
`render_to_box` a string and a `(width, height)` pixel rectangle, and it returns
an image sized to exactly that box. The line is scaled to the box height, and the
width is filled — the glyphs are compressed when the text is too wide, and evenly
spaced out when it is too narrow — so the box is filled edge to edge. It fits
banners, buttons, thumbnails, and label strips: anywhere you need text poured into
a fixed-size box without overflow or leftover gaps.

```python
from mojivs import IVSFont

font = IVSFont("Gothic.otf")
# Just a string and a (width, height). The returned image is exactly that size.
font.render_to_box("枠にフィット", (400, 80)).save("boxed.png")
```

And since what you pour into the box is Japanese, getting the **correct glyph
shape** matters just as much. mojivs resolves **IVS (Ideographic Variation
Sequences / 異体字)** and **SVS (Standardized Variation Sequences)** straight from
**the font's own cmap format-14 (UVS) subtable**.

![Rendering 辻+VS17: Pillow BASIC ignores it, while Pillow+libraqm and mojivs render it correctly](https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/hero_ivs.png)

Because that is the standard OpenType mechanism, it works beyond Adobe-Japan1 —
including other IVD collections such as Hanyo-Denshi / Moji_Joho, and both
CID-keyed and name-keyed fonts (falling back to the Adobe-Japan1 IVD when a font
ships no format-14 table). Pillow's `ImageFont` ignores variation selectors in its
default (BASIC) layout; with libraqm/HarfBuzz it can shape them. **mojivs resolves
IVS/SVS with fonttools alone — no libraqm/HarfBuzz required.** For example, variant
forms of 辻, 葛, 髙, 﨑, 鯛 fill the box with the correct glyph shape.

```
辻󠄀  辻󠄁      ← the same 辻, but the variation selector changes the glyph
             (one-dot vs two-dot shinnyō radical)
```

## Features

- **Fit into a box (`render_to_box`)** — fit one line into an exact
  `(width, height)` pixel rectangle: compress the glyphs when the text is too
  wide, distribute even spacing when it is too narrow, filling the box with no
  overflow and no leftover gap.
- **IVS / SVS applied to glyph shape** — resolved from the font's own cmap
  format-14 (UVS) subtable, so any font works — not just Adobe-Japan1 (falls
  back to the Adobe-Japan1 IVD when a font has no format-14 table).
- **Font parsed once** — the cmap, glyph set, and metrics are cached instead of
  being rebuilt on every render.
- **Horizontal / vertical / multi-line** — split rows/columns on `\n`; vertical
  writing honors `vmtx`/`VORG` and vertical punctuation forms.
- **Latin rotation & tate-chu-yoko** — rotate Latin/digits 90° in vertical text
  (`orientation`), or set short digit runs upright and horizontal
  (`tate_chu_yoko`).
- **Outline (stroke), background color, letter/line spacing, alignment**.
- **PNG / SVG / PDF output** — multiple formats from one layout engine.
- **Selectable backend** — the default `builtin` backend is a dependency-free
  pure-Python rasterizer. Switch to `backend="cairo"` / `backend="freetype"` for
  speed (both fall back to cairo automatically when stroking).
- **Very few dependencies** — the core is just `fonttools` + `pillow` (two
  packages). A bare `pip install mojivs` already renders. `pycairo` /
  `freetype-py` (plus numpy) are optional accelerators for speed and strokes, and
  PDF output (`reportlab`) is an optional extra too.

## Gallery

**Fit into an exact pixel box (`render_to_box`)** — filled edge to edge with even spacing

<img src="https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/feature_box.png" alt="Fit to a box" width="440">

**Outline (stroke) + background**

<img src="https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/feature_outline.png" alt="Stroked text" width="360">

**Vertical writing + tate-chu-yoko**

<img src="https://raw.githubusercontent.com/daiki-moritake/mojivs/main/docs/images/feature_vertical.png" alt="Vertical writing with tate-chu-yoko" width="130">

## Installation

It works out of the box with no extras (it pulls only `fonttools` + `pillow`):

```bash
pip install mojivs                    # renders with the default builtin backend (no system libs)
```

Add an optional accelerator when you need one:

```bash
pip install mojivs[cairo]             # cairo backend (required for strokes)
pip install mojivs[freetype]          # FreeType backend (fastest fill; bundles numpy)
pip install mojivs[cairo,freetype]    # both
```

[uv](https://docs.astral.sh/uv/) works the same way (it installs from PyPI):

```bash
uv pip install mojivs                 # into an existing environment
uv add "mojivs[cairo]"                # add to a uv-managed project (with cairo)
```

- **builtin (default)** — pure Python + Pillow. No C extensions or system
  libraries; `pip install mojivs` alone renders fills and backgrounds, with
  output nearly identical to cairo/freetype.
- **cairo** — required for stroked text, and faster for fills too. `pycairo`
  needs the native cairo library:

  ```bash
  # macOS
  brew install cairo pkg-config
  # Debian / Ubuntu
  sudo apt-get install libcairo2-dev pkg-config
  ```

- **freetype** — the fastest fill path. `freetype-py` ships self-contained
  wheels, so no system cairo is needed (numpy, used for compositing, comes along).

> Only cairo can stroke, so `backend="builtin"` / `"freetype"` fall back to cairo
> automatically when a stroke is requested — which needs `mojivs[cairo]`.

```bash
# Development (both backends + tests/type checking)
pip install -e ".[dev]"
```

## Usage

```python
from mojivs import IVSFont

font = IVSFont("fonts/HaranoAjiFonts-master/HaranoAjiGothic-Medium.otf")

# 1. Fit into an exact pixel box (the headline feature).
#    The returned image is exactly (width, height); the line scales to the height.
font.render_to_box("辻鯛テ体", (400, 80), color="#000").save("boxed.png")
#    Wide box -> spacing spread evenly. Narrow box -> glyphs compressed.
font.render_to_box("辻鯛テ体", (640, 80)).save("boxed_wide.png")   # justified
font.render_to_box("辻鯛テ体", (200, 80)).save("boxed_narrow.png") # compressed
#    Stroke and background too (the stroke stays inside the box).
font.render_to_box(
    "SALE 50%", (480, 120), color="#fff", stroke="#e5484d", stroke_width=6, background="#1a1a1a"
).save("boxed_banner.png")

# 2. Render with the font's natural metrics (em size; not fitted to a box).
img = font.render("辻\U000e0100鯛", size=96, color="#1a1a1a")
img.save("out.png")

# 3. With an outline (stroke).
font.render(
    "異体字レンダリング",
    size=96,
    color="#ffffff",
    stroke="#e5484d",
    stroke_width=6,
    background="#1a1a1a",
).save("outlined.png")

# 4. Multi-line (\n) and alignment.
font.render("異体字\nレンダリング", size=64, align="center").save("multiline.png")

# 5. Vertical writing (\n starts a new column, right-to-left; punctuation is
#    substituted with vertical forms).
font.render("辻\U000e0100鯛の\n「縦書き」。", size=72, direction="vertical").save("vertical.png")

# 5b. Latin rotation in vertical text (default orientation="mixed": Latin/digits
#     rotate 90°, kanji/kana stay upright).
font.render("縦書きABC\n令和6年です", size=64, direction="vertical").save("mixed.png")

# 5c. Tate-chu-yoko (short digit runs set upright and horizontal in one cell;
#     tate_chu_yoko = max digit count).
font.render("平成31年\n5月1日", size=64, direction="vertical", tate_chu_yoko=2).save("tcy.png")

# 6. Backend selection (default is the dependency-free builtin; switch only for speed).
#     Output is nearly identical across all three; strokes fall back to cairo automatically.
font.render("高速レンダリング", size=96, backend="freetype").save("ft.png")  # needs mojivs[freetype]

# Vector output (SVG needs no extra deps; PDF needs reportlab).
open("out.svg", "w").write(font.to_svg("辻\U000e0100鯛", size=96))
font.to_pdf("辻\U000e0100鯛", "out.pdf", size=96)     # pip install mojivs[pdf]

# Check coverage without rendering.
font.supports("辻鯛テ体")   # -> True
font.missing("辻鯛𠮷")       # -> list of unsupported clusters
```

`\U000e0100` is variation selector VS17 (U+E0100); include it directly in the string.

### Fitting text into a box (`render_to_box`)

This is the library's headline feature. `render_to_box(text, (width, height))`
returns an image with one line of text fitted **exactly** into the given pixel
rectangle (the return value is always `(width, height)`).

- **Height** — the font's line height is scaled proportionally to the box height.
- **Width** — once scaled, the natural width is compared against the box:
  - **too wide** → each glyph is compressed horizontally to fit (aspect narrows);
  - **too narrow** → the slack is distributed as **even inter-character spacing**,
    filling the box to both edges.
- **Stroke** — the stroke width is reserved inside the box, so the outline never
  spills past the frame.

So you can pour text into a fixed box without computing a font size yourself. It
is horizontal single-line only (use `render` / `shape` for vertical, multi-line,
or wrapped text).

```python
# Fix the height at 80px; only the width changes how the text is packed.
font.render_to_box("在庫僅少", (600, 80))   # wide  → spacing distributed evenly
font.render_to_box("在庫僅少", (220, 80))   # narrow → glyphs compressed
```

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
(`builtin`|`cairo`|`freetype`) `--on-missing` (`raise`|`skip`). See `mojivs render --help`.

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
- `backend` (`render` / `render_to_box` only): `"builtin"` (default —
  dependency-free pure Python), `"cairo"`, or `"freetype"`. This chooses the
  rasterizer only; the layout is unchanged (not applicable to SVG/PDF).

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
(`"builtin"` default | `"cairo"` | `"freetype"`).

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

A pure layer for cluster splitting (IVS/SVS selectors) and the Adobe-Japan1 IVD
fallback, without cairo/Pillow. Primary glyph resolution lives in `font.py`,
which reads the font's format-14 subtable.

```python
from mojivs import ivs

ivs.is_variation_selector("\U000e0100")   # -> True (SVS U+FE00–FE0F is True too)
ivs.cid_glyph_name("辻", ["\U000e0100"])   # -> "cid03056" (Adobe-Japan1 fallback)
list(ivs.iter_clusters("A辻\U000e0100"))   # -> [('A', []), ('辻', ['\U000e0100'])]
```

## Architecture

A lightweight resolver layer, with layout → per-format output built on top.

```
mojivs/
├─ ivs.py       … cluster splitting (IVS/SVS) + Adobe-Japan1 IVD fallback (stdlib only)
├─ font.py      … IVSFont: font loading, format-14 (UVS) glyph resolution, caching
├─ shaping.py   … shape(): text → placed glyphs (horizontal/vertical/multi-line)
├─ render.py    … backend dispatch + cairo rasterization (PNG)
├─ render_builtin.py … default backend (pure Python + Pillow, no extra deps; backend="builtin")
├─ render_ft.py … FreeType backend (optional; freetype-py + numpy; backend="freetype")
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
- Variants are resolved from the font's cmap format-14 (UVS) subtable, so any
  font with one works across all collections (Adobe-Japan1, Hanyo-Denshi,
  Moji_Joho, …) and SVS. A font that has **no format-14 table and is not
  Adobe-Japan1 CID-named** cannot resolve variants (and, of course, nothing can
  render a glyph the font does not contain).
- No automatic line breaking (word wrap); only explicit `\n`.
- `render_to_box` supports a single horizontal line only.

## License

Code is MIT. See [LICENSE](LICENSE) for the bundled data and font licenses.
