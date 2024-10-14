# fontRender

python でフォントを描画するためのツール
特に、特殊な漢字（異体字）に対応できるようにしています。

## 概要

描画範囲（縦横のピクセル数）を決めて、その範囲内に収まるように文字をレンダリングする関数

### 使い方

1. python の仮想環境を構築

```
python -m venv venv
```

または、

```
python3 -m venv venv
```

- Win の場合 VENV をアクティブにするために、PowerShell を有効かする

PowerShell を開いて、下記のコマンドを実行する

```
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

2. VENV をアクティブにする
   プロジェクトのフォルダで下記を実行

Win

```
.\venv\scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\activate
```

Mac

```
source ./venv/bin/activate
```

3. ライブラリをインストール

```
pip install -r requirements.txt
python -m pip install --upgrade pip
```

---

### cairo をインストール

Mac

```
brew install cairo
brew install pkg-config cairo
```

### ライブラリ

```
pip install numpy
pip install pillow
pip install fonttools
pip install reportlab
pip install scipy
pip install --no-cache-dir pycairo
```

### サンプルフォント

おそらく Adobe-Japan1-7 に対応している
https://github.com/trueroad/HaranoAjiFonts

## 使用例

```py
from fontTools.ttLib import TTFont
from fontRender import fontRender

font_path = "fonts/HaranoAjiFonts-master/HaranoAjiGothic-Medium.otf"

font = TTFont(font_path)

field_size_xy = (300, 20)

text = 'テ鯛鯛󠄀炱鯛󠄁体󠄂辻辻󠄀辻󠄁' # 異体字を含む文字

img = fontRender(
    text,
    font,
    field_size_xy,
    weight=5.0,
    color=(0, 0, 0),
    outLineColor=(255, 0, 0),
    vertical=False,
)
img.save("test.png", "PNG")

```
