# mojivs

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
- **アウトライン（縁取り）・背景色・文字間隔**に対応
- **箱にフィット** — 指定ピクセル矩形に収める（`render_to_box`）
- **依存が少ない** — `fonttools` / `pillow` / `pycairo` / `numpy` のみ

## インストール

pycairo はネイティブの cairo ライブラリを必要とします。

```bash
# macOS
brew install cairo pkg-config

# Debian / Ubuntu
sudo apt-get install libcairo2-dev pkg-config
```

```bash
pip install mojivs   # 公開後
# または開発版
pip install -e .
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

# 3. 指定ピクセルの矩形にフィット（広ければ圧縮・狭ければ字間を均等配分）
font.render_to_box("辻鯛テ体", (400, 80), color="#000").save("boxed.png")

# 描画せずに対応状況を確認
font.supports("辻鯛テ体")   # -> True
font.missing("辻鯛𠮷")       # -> 未対応クラスタのリスト
```

`\U000e0100` は異体字セレクタ VS17（U+E0100）です。文字列にそのまま含めます。

### 色の指定

`color` / `stroke` / `background` は次を受け付けます。

- 16進文字列: `"#000"`, `"#1a1a1a"`, `"#1a1a1aff"`
- 0–255 のタプル: `(26, 26, 26)` または `(26, 26, 26, 255)`
- `None`（`stroke` / `background` の既定。縁取り・背景なし）

## API

### `IVSFont(font, *, font_number=0)`

フォントを 1 度だけ読み込み、以降のルックアップをキャッシュします。
`font` はパスまたは `fontTools.ttLib.TTFont`。

| メソッド | 説明 |
|---|---|
| `render(text, *, size=64, color, stroke, stroke_width, background, letter_spacing, padding, on_missing)` | 自然なメトリクスで RGBA 画像を返す |
| `render_to_box(text, box, *, color, stroke, stroke_width, background, on_missing)` | `box=(幅, 高さ)` ちょうどの画像に収める |
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

依存の軽い解決レイヤの上に、重いラスタライザを載せる 2 層構成です。

```
mojivs/
├─ ivs.py     … IVS → Adobe-Japan1 CID 解決（標準ライブラリ＋fonttoolsのみ）
├─ font.py    … IVSFont：フォント読み込みとキャッシュ
├─ render.py  … cairo/Pillow によるラスタライズ
└─ data/ivd.txt … Unicode IVD（同梱データ）
```

## サンプルフォント

`fonts/` に Harano Aji Fonts（Adobe-Japan1-7 対応、独自ライセンス）を同梱しています。
<https://github.com/trueroad/HaranoAjiFonts>

## 開発

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
python examples/basic.py   # examples/ に PNG を出力
```

## 制限事項・今後

- 現状は **横書き 1 行** のみ（旧実装の縦書きは未完成のため一旦除外）。
- IVS のうち Adobe-Japan1 コレクションのみ対応（IVD の Hanyo-Denshi / Moji_Joho は未対応）。
- 複数行・自動改行は未対応。

## ライセンス

コードは MIT。同梱データ・フォントのライセンスは [LICENSE](LICENSE) を参照。
