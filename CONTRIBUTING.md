# Contributing to mojivs

Thanks for your interest in improving mojivs. This project renders Japanese text
— including Ideographic Variation Sequences (異体字 / IVS) — to images. Bug
reports, documentation fixes, and pull requests are all welcome.

## Development setup

Install a system cairo (needed by pycairo) and the package in editable mode with
the dev extras:

```bash
# system cairo
brew install cairo pkg-config           # macOS
sudo apt-get install libcairo2-dev pkg-config   # Debian/Ubuntu

python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before you open a pull request

Run the same four checks CI runs — please make sure they all pass:

```bash
ruff check src tests            # lint
ruff format --check src tests   # formatting (drop --check to auto-format)
pyright                         # type checking
pytest                          # tests (add --cov=mojivs for coverage)
```

Guidelines:

- **Keep the layers separate.** `ivs.py` must stay free of rendering deps;
  `shape()` is the single layout engine that PNG/SVG/PDF all build on. See the
  architecture section in the [README](README.md).
- **Add tests** for new behavior. The FreeType backend is validated against cairo
  pixel-for-pixel within tolerance (`tests/test_render_ft.py`) — keep that
  invariant when touching rasterization.
- **Update docs together.** When user-facing behavior changes, update both
  `README.md` and `README.en.md`, and add a `CHANGELOG.md` entry under
  `[Unreleased]`.
- **Don't commit large binaries.** Only `HaranoAjiGothic-Medium.otf` is tracked;
  other fonts are downloadable from
  [Harano Aji Fonts](https://github.com/trueroad/HaranoAjiFonts).

## Updating the bundled IVD data

`src/mojivs/data/ivd.txt` is a vendored copy of the Unicode IVD. To refresh it,
use [`scripts/update_ivd.py`](scripts/update_ivd.py) (see
[`scripts/README.md`](scripts/README.md)) rather than editing the file by hand.

## Good first issues

- Extend IVS support beyond Adobe-Japan1 to the Hanyo-Denshi / Moji_Joho IVD
  collections (the data is already bundled).
- Word-wrapping / automatic line breaking (currently only explicit `\n`).
- Multi-line support in `render_to_box`.

## Reporting bugs

Please include the font, the exact input string (with variation selectors as
`\U000eXXXX` escapes), the code you ran, and what you expected versus what you
got. A minimal reproducible example makes fixes much faster.

## License

By contributing, you agree that your contributions are licensed under the
project's MIT license.
