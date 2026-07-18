# mojivs

[![CI](https://github.com/daiki-moritake/mojivs/actions/workflows/ci.yml/badge.svg)](https://github.com/daiki-moritake/mojivs/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**日本語** | [English](README.en.md)

**IVS（異体字セレクタ）対応の日本語テキスト → 画像レンダラ**

日本語テキストを画像にレンダリングします。とくに **IVS（Ideographic Variation
Sequence / 異体字）** を Adobe-Japan1 の IVD から解決し、フォント内の CID グリフに
マッピングします。これは Pillow の `ImageFont` ではできない処理です。

たとえば「辻」「葛」「髙」「﨑」「鯛」などの異体字を、正しい字形で画像化できます。

```
辻󠄀  辻󠄁      ← 同じ「辻」でも異体字セレクタで字形（一点しんにょう/二点しんにょう）が変わる
```

## 特徴

- **IVS を字形に反映** — 基底文字＋異体字セレクタを Adobe-Japan1 CID へ解決
- **フォントは一度だけ解析** — cmap・グリフ集合・メトリクスをキャッシュし、描画のたびに再構築しない
- **横書き・縦書き・複数行** — `\n` で行/列を分割、縦書きは `vmtx`/`VORG` と縦書き用約物に対応
- **欧文回転・縦中横** — 縦書きで欧文/数字を90°回転（`orientation`）、桁数字を正立横組みに（`tate_chu_yoko`）
- **アウトライン（縁取り）・背景色・文字間隔・行間・揃え**に対応
- **PNG / SVG / PDF 出力** — 同一のレイアウトエンジンから複数フォーマットへ
- **箱にフィット** — 指定ピクセル矩形に収める（`render_to_box`）
- **選べるバックエンド** — cairo（既定）か FreeType。`backend="freetype"` は cairo 非依存で高速（縁取り時は自動で cairo にフォールバック）
- **依存が少ない** — コアは `fonttools` / `pillow` / `numpy` のみ。ラスタライザ（`pycairo` または `freetype-py`）と PDF 出力（`reportlab`）はいずれも任意の extra

## インストール

ラスタライザのバックエンドを**最低ひとつ**選んでインストールします。

```bash
pip install mojivs[cairo]             # 既定バックエンド（縁取りにも必須）
pip install mojivs[freetype]          # FreeType バックエンド（cairo 非依存・高速）
pip install mojivs[cairo,freetype]    # 両方
```

- **cairo** — 既定バックエンドと縁取り（stroke）に必須。`pycairo` はネイティブの cairo ライブラリを必要とします:

  ```bash
  # macOS
  brew install cairo pkg-config
  # Debian / Ubuntu
  sudo apt-get install libcairo2-dev pkg-config
  ```

- **freetype** — `freetype-py` は自己完結した wheel を配布するため、システムの cairo ライブラリは不要です。

> extra 無しの `pip install mojivs` ではラスタライザが入りません。`import mojivs` は
> 通りますが、既定の `render()` は cairo バックエンドを使うため `mojivs[cairo]` を、
> FreeType だけで使うなら `backend="freetype"` と `mojivs[freetype]` を入れてください。

```bash
# 開発版（両バックエンド＋テスト/型チェック）
pip install -e ".[dev]"
```

## 使い方

```python
from mojivs import IVSFont

font = IVSFont("fonts/HaranoAjiFonts-master/HaranoAjiGothic-Medium.otf")

# 1. フォント本来のメトリクスで素直に描画（em サイズ指定）
img = font.render("辻\U000e0100鯛", size=96, color="#1a1a1a")
img.save("out.png")

# 2. 縁取り付き
font.render(
    "異体字レンダリング",
    size=96,
    color="#ffffff",
    stroke="#e5484d",
    stroke_width=6,
    background="#1a1a1a",
).save("outlined.png")

# 3. 複数行（\n）・揃え（align）
font.render("異体字\nレンダリング", size=64, align="center").save("multiline.png")

# 4. 縦書き（\n で改列、右の列から左へ。約物は縦書き用字形に置換）
font.render("辻\U000e0100鯛の\n「縦書き」。", size=72, direction="vertical").save("vertical.png")

# 4b. 縦書きの欧文回転（既定 orientation="mixed"：欧文/数字は90°回転、漢字仮名は正立）
font.render("縦書きABC\n令和6年です", size=64, direction="vertical").save("mixed.png")

# 4c. 縦中横（桁数字を正立の横組みで1マスに。tate_chu_yoko=最大桁数）
font.render("平成31年\n5月1日", size=64, direction="vertical", tate_chu_yoko=2).save("tcy.png")

# 5. 指定ピクセルの矩形にフィット（広ければ圧縮・狭ければ字間を均等配分）
font.render_to_box("辻鯛テ体", (400, 80), color="#000").save("boxed.png")

# 5b. FreeType バックエンド（任意・cairo 非依存で高速。要 pip install mojivs[freetype]）
#     出力は cairo とほぼ同一。縁取り指定時は自動で cairo にフォールバックします。
font.render("高速レンダリング", size=96, backend="freetype").save("ft.png")

# ベクター出力（SVG は依存追加なし。PDF は reportlab が必要）
open("out.svg", "w").write(font.to_svg("辻\U000e0100鯛", size=96))
font.to_pdf("辻\U000e0100鯛", "out.pdf", size=96)     # pip install mojivs[pdf]

# 描画せずに対応状況を確認
font.supports("辻鯛テ体")   # -> True
font.missing("辻鯛𠮷")       # -> 未対応クラスタのリスト
```

`\U000e0100` は異体字セレクタ VS17（U+E0100）です。文字列にそのまま含めます。

### 出力フォーマットとレイアウト

レイアウトは `shape()` が計算し、PNG/SVG/PDF はその結果を各フォーマットに描画します。
`render` / `to_svg` / `to_pdf` は共通のレイアウト引数
（`size`・`direction`・`align`・`line_spacing`・`letter_spacing`・`padding`・
`orientation`・`tate_chu_yoko`）と
スタイル引数（`color`・`stroke`・`stroke_width`・`background`）を受け付けます。

- `orientation`（縦書き時）: `"mixed"`（既定・欧文/数字を90°回転）｜`"upright"`（すべて正立）
- `tate_chu_yoko`（縦書き時）: `0` で無効。`N` で連続する半角数字を最大 N 桁ずつ正立の横組み（縦中横）に。
- `backend`（`render` / `render_to_box` のみ）: `"cairo"`（既定）｜`"freetype"`。ラスタライズ方式の選択で、レイアウト結果は変わりません（SVG/PDF は対象外）。

```python
from mojivs import IVSFont

font = IVSFont("...otf")
shaped = font.shape("辻\U000e0100鯛\nテ体", size=64, align="center")
shaped.width, shaped.height          # ピクセルサイズ
shaped.glyphs                        # 配置済みグリフ（PlacedGlyph）の列
```

### 色の指定

`color` / `stroke` / `background` は次を受け付けます。

- 16進文字列: `"#000"`, `"#1a1a1a"`, `"#1a1a1aff"`
- 0–255 のタプル: `(26, 26, 26)` または `(26, 26, 26, 255)`
- `None`（`stroke` / `background` の既定。縁取り・背景なし）

## API

### `IVSFont(font, *, font_number=0)`

フォントを 1 度だけ読み込み、以降のルックアップをキャッシュします。
`font` はパスまたは `fontTools.ttLib.TTFont`。

共通のレイアウト引数: `size` / `direction`（`"horizontal"`｜`"vertical"`）/
`align`（`"start"`｜`"center"`｜`"end"`）/ `line_spacing` / `letter_spacing` / `padding` /
`orientation`（`"mixed"`｜`"upright"`）/ `tate_chu_yoko`（int）。
共通のスタイル引数: `color` / `stroke` / `stroke_width` / `background`。
ラスタライズ系（`render` / `render_to_box`）は追加で `backend`（`"cairo"` 既定 ｜ `"freetype"`）を受け付けます。

| メソッド | 説明 |
|---|---|
| `render(text, *, ...) -> Image` | 自然なメトリクスで RGBA 画像を返す |
| `render_to_box(text, box, *, ...) -> Image` | `box=(幅, 高さ)` ちょうどの画像に収める（横1行） |
| `shape(text, *, ...) -> ShapedText` | 配置済みグリフ（`PlacedGlyph`）とサイズを返す |
| `to_svg(text, *, ...) -> str` | SVG 文書文字列を返す |
| `to_pdf(text, path, *, ...) -> None` | 1ページの PDF を書き出す（`reportlab` 必須） |
| `supports(text) -> bool` | 全クラスタを描画できるか |
| `missing(text) -> list[str]` | 描画できないクラスタを順に返す |
| `glyph_name(base, selectors=None) -> str \| None` | 基底文字＋セレクタのグリフ名を解決 |

`on_missing` は `"raise"`（既定・`UnsupportedCharacterError`）または `"skip"`。

### `mojivs.ivs`（描画に依存しない解決レイヤ）

cairo/Pillow を使わず、IVS → CID の解決だけを行う純粋なレイヤです。

```python
from mojivs import ivs

ivs.is_variation_selector("\U000e0100")   # -> True
ivs.cid_glyph_name("辻", ["\U000e0100"])   # -> "cid03056"
list(ivs.iter_clusters("A辻\U000e0100"))   # -> [('A', []), ('辻', ['\U000e0100'])]
```

## アーキテクチャ

依存の軽い解決レイヤの上に、レイアウト → 各フォーマット出力を載せる構成です。

```
mojivs/
├─ ivs.py      … IVS → Adobe-Japan1 CID 解決（標準ライブラリ＋fonttoolsのみ）
├─ font.py     … IVSFont：フォント読み込みとキャッシュ
├─ shaping.py  … shape()：テキスト → 配置済みグリフ（横/縦/複数行）
├─ render.py   … cairo/Pillow によるラスタライズ（PNG）
├─ render_ft.py … FreeType バックエンド（任意・freetype-py。backend="freetype"）
├─ export.py   … SVG（fonttools）/ PDF（reportlab・任意）出力
├─ colors.py   … 色のパース
└─ data/ivd.txt … Unicode IVD（同梱データ）
```

`shape()` が唯一のレイアウトエンジンで、PNG/SVG/PDF はいずれもその結果を描画します。

## サンプルフォント

`fonts/` にはテスト・サンプル用として Harano Aji Fonts（Adobe-Japan1-7 対応、独自
ライセンス）の **`HaranoAjiGothic-Medium.otf` 1 面のみ**を同梱しています。他のウェイト
や明朝は下記から取得してください（リポジトリ肥大化を避けるため追跡していません）。
<https://github.com/trueroad/HaranoAjiFonts>

## 開発

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                       # テスト
ruff check src tests         # lint（未使用importや実バグを検出）
ruff format src tests        # 整形
pyright                      # 型チェック

python examples/basic.py     # examples/ に PNG を出力
```

lint/型チェックの設定は `pyproject.toml` の `[tool.ruff]` / `[tool.pyright]` にあります。
型スタブを持たない C 拡張（pycairo・reportlab）向けに pyright は `basic` モードで、
「スタブが無い」系の誤検知を抑制しています。CI（GitHub Actions）でも同じ4つを実行します。

## 制限事項・今後

- 縦書きの欧文回転/正立は **Unicode 範囲によるヒューリスティック**（UAX #50 準拠の近似）で判定します。厳密な字ごとの縦書き字形指定には未対応。
- `tate_chu_yoko` は半角 ASCII 数字の連続のみを対象とします（`No.` 等の混在は対象外）。
- IVS のうち Adobe-Japan1 コレクションのみ対応（IVD の Hanyo-Denshi / Moji_Joho は未対応）。
- 自動改行（ワードラップ）は未対応。`\n` による明示的な改行/改列のみ。
- `render_to_box` は横書き 1 行のみ対応。

## ライセンス

コードは MIT。同梱データ・フォントのライセンスは [LICENSE](LICENSE) を参照。
