# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `py.typed` marker (PEP 561) so downstream type checkers pick up the package's
  inline type hints.
- Automated PyPI release via GitHub Actions Trusted Publishing (OIDC),
  `.github/workflows/publish.yml`, documented in `RELEASING.md`. The package
  then installs with pip or uv (`uv add mojivs`).
- `scripts/update_ivd.py` to re-fetch the bundled Unicode IVD table, with the
  source, version, and license recorded in `scripts/README.md`.
- Test coverage measurement (`pytest-cov`) and an expanded CI matrix
  (Ubuntu + macOS across Python 3.9 / 3.12 / 3.13).
- `CONTRIBUTING.md`, GitHub issue/PR templates, an English `README.en.md`, and
  status badges in the README.

### Changed
- Only `HaranoAjiGothic-Medium.otf` is tracked in `fonts/`; the other Harano Aji
  faces (~70 MB) are no longer committed and are downloadable from upstream.

## [0.3.0]

### Added
- FreeType rasterizer backend (`backend="freetype"`), a cairo-free, faster fill
  path; stroked text automatically falls back to cairo.
- Glyph outline caching in `IVSFont`, roughly 2.4× faster rendering on repeated
  glyphs.

### Changed
- `cairo` (pycairo) is now an optional dependency (`mojivs[cairo]`) instead of a
  hard requirement; install at least one rasterizer backend.
- Introduced `ruff` (lint + format) and `pyright` (type checking), enforced in CI.

## [0.2.0]

### Added
- Vertical and multi-line layout, `shape()` as the single layout engine, and
  SVG / PDF output built on top of it.
- Latin rotation and tate-chu-yoko (縦中横) for vertical text.

## [0.1.0]

### Added
- Initial release: IVS → Adobe-Japan1 CID resolution and IVS-aware PNG rendering,
  packaged as the `mojivs` library.

[Unreleased]: https://github.com/daiki-moritake/mojivs/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/daiki-moritake/mojivs/releases/tag/v0.3.0
[0.2.0]: https://github.com/daiki-moritake/mojivs/releases/tag/v0.2.0
[0.1.0]: https://github.com/daiki-moritake/mojivs/releases/tag/v0.1.0
