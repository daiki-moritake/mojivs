# Changelog

All notable changes to this project are documented here.

From v0.4.0 onward, releases are generated automatically by
[python-semantic-release](https://python-semantic-release.readthedocs.io/) from
[Conventional Commits](https://www.conventionalcommits.org/); each new version is
inserted below the marker. Entries up to and including v0.3.0 were hand-written in
the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style.

<!-- version list -->

## v0.4.0 (2026-07-23)

### Bug Fixes

- **docs**: ヒーロー画像と README の主張を正確化（Pillow+libraqm でも IVS は描ける）
  ([`c24249d`](https://github.com/daiki-moritake/mojivs/commit/c24249d5e3b20c0ce23049aeea3668cbc7dcf0e6))

- **types**: Cmap テーブルを Any 経由で参照し pyright エラーを解消
  ([`17e8b64`](https://github.com/daiki-moritake/mojivs/commit/17e8b64ddb47142a2b55f62ec2fa94d179e15cb9))

### Code Style

- ヒーロー生成スクリプトの長い行を折り返し（ruff E501）
  ([`603655f`](https://github.com/daiki-moritake/mojivs/commit/603655f007f4e2674cff8b28e81fa07b22937962))

### Continuous Integration

- Main へのマージで自動リリース(python-semantic-release)
  ([`c6e0e44`](https://github.com/daiki-moritake/mojivs/commit/c6e0e44a7d9d197f44a6481a6f62abb0a0e68143))

### Documentation

- 「枠にフォントを綺麗に埋める」を README の主役に
  ([`f199998`](https://github.com/daiki-moritake/mojivs/commit/f199998722e8200d0e91f6f50156e78fb658b1c0))

### Features

- CLI・README ビジュアル・GitHub メタデータで発見性を強化
  ([`bf09779`](https://github.com/daiki-moritake/mojivs/commit/bf09779b15c363382611074431412457ef2c7e42))

- Cmap format-14(UVS) で IVS/SVS を解決し任意フォントに対応
  ([`4203406`](https://github.com/daiki-moritake/mojivs/commit/42034066389d5c58aeef78c5b40849e84a11710a))

- **render**: 依存ゼロの純Python builtin バックエンドを追加し既定に
  ([`14a85d5`](https://github.com/daiki-moritake/mojivs/commit/14a85d597b8c77f6b5e8154f75fcd62df2020cbd))

### Testing

- SVS クラスタリング挙動の回帰テストを追加
  ([`2b63e03`](https://github.com/daiki-moritake/mojivs/commit/2b63e0353ce98c290f13d7e9bbd1d8817190e6f8))


## [0.3.0] - 2026-07-21

First release published to PyPI (installable with pip or uv).

### Added
- FreeType rasterizer backend (`backend="freetype"`), a cairo-free, faster fill
  path; stroked text automatically falls back to cairo.
- Glyph outline caching in `IVSFont`, roughly 2.4× faster rendering on repeated
  glyphs.
- `py.typed` marker (PEP 561) so downstream type checkers pick up the package's
  inline type hints.
- Automated PyPI release via GitHub Actions Trusted Publishing (OIDC),
  `.github/workflows/publish.yml`, documented in `RELEASING.md`.
- `scripts/update_ivd.py` to re-fetch the bundled Unicode IVD table, with the
  source, version, and license recorded in `scripts/README.md`.
- Test coverage measurement (`pytest-cov`) and an expanded CI matrix
  (Ubuntu + macOS across Python 3.9 / 3.12 / 3.13).
- `CONTRIBUTING.md`, GitHub issue/PR templates, an English `README.en.md`, and
  status badges in the README.

### Changed
- `cairo` (pycairo) is now an optional dependency (`mojivs[cairo]`) instead of a
  hard requirement; install at least one rasterizer backend.
- Introduced `ruff` (lint + format) and `pyright` (type checking), enforced in CI.
- Only `HaranoAjiGothic-Medium.otf` is tracked in `fonts/`; the other Harano Aji
  faces (~70 MB) are no longer committed and are downloadable from upstream.

## [0.2.0]

### Added
- Vertical and multi-line layout, `shape()` as the single layout engine, and
  SVG / PDF output built on top of it.
- Latin rotation and tate-chu-yoko (縦中横) for vertical text.

## [0.1.0]

### Added
- Initial release: IVS → Adobe-Japan1 CID resolution and IVS-aware PNG rendering,
  packaged as the `mojivs` library.

[0.3.0]: https://github.com/daiki-moritake/mojivs/releases/tag/v0.3.0
[0.2.0]: https://github.com/daiki-moritake/mojivs/releases/tag/v0.2.0
[0.1.0]: https://github.com/daiki-moritake/mojivs/releases/tag/v0.1.0
