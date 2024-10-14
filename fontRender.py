import lib.isIVS as isIVS  # 文字が異体字セレクタ（IVS）かを判定する関数
import lib.createTools as createTools

import numpy as np
from PIL import Image, ImageDraw
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from scipy.spatial import Delaunay
import tempfile
import re

from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import RecordingPen
import cairo
import io
from typing import Union


# Adobe-Japan1 の辞書を作成
adobe_japan1_dict = createTools.adobe_japan1_dict
adobe_japan1_dict_re = createTools.adobe_japan1_dict_re


# print(adobe_japan1_dict)


def getGlyph(
    glyphId_CodePoint: dict,
    glyph_names: list[str],
    t: str,
    n_t: Union[str, None] = None,
    nn_t: Union[str, None] = None,
    nnn_t: Union[str, None] = None,
):
    """_summary_
    テキストのグリフ名を取得する
    Args:
        glyphId_CodePoint (dict): キー: コードポイント バリュー: グリフ名
        glyph_names (list): 使えるグリフ名の一覧
        t (str): _description_
        n_t (str, optional): _description_. Defaults to None.
        nn_t (str, optional): _description_. Defaults to None.
        nnn_t (str, optional): _description_. Defaults to None.

    Returns:
        str: _description_
    """
    codePoint = ord(t)
    uniCode16 = hex(codePoint).upper()[
        2:
    ]  # コードポイントを16進数に変換して、.upper()[2:]で0xの部分を取り除き、大文字に変換します。
    runUni = uniCode16
    # 異体字であるかを
    is_ivs = False
    if n_t != None and isIVS.is_in_ivs_range(n_t):
        # print('次の文字がIVSなので、異体字と判断')
        is_ivs = True  # IVSが一つでもあれば、True
        runUni += " " + hex(ord(n_t)).upper()[2:]
        if nn_t != None and isIVS.is_in_ivs_range(nn_t):
            # print('次の次の文字もIVSなので、IVSが二つの異体字と判断')
            runUni += " " + hex(ord(nn_t)).upper()[2:]
            if nnn_t != None and isIVS.is_in_ivs_range(nnn_t):
                # print('次の次の次の文字もIVSなので、IVSが三つの異体字と判断')
                runUni += " " + hex(ord(nnn_t)).upper()[2:]

    # print('処理するUnicode => ', runUni)

    glyphCid = None

    if is_ivs:
        # 異体字があるので、IVDから作った辞書を参考に、CIDを取得する
        if runUni in adobe_japan1_dict:
            cid = adobe_japan1_dict[runUni]
            cid = cid.replace("CID+", "").zfill(
                5
            )  # 不要な文字を消去 & 5文字以下は0埋め
            # print('ここを確認 => ',cid)
            cid = "cid" + cid
            # グリフに存在するかを確認
            if cid in glyph_names:
                glyphCid = cid  # グリフにある場合のみ更新

    # 異体字の対応ができない場合は、通常文字になる
    if glyphCid == None:
        # 異体字ではない時
        if codePoint in glyphId_CodePoint:
            glyphCid = glyphId_CodePoint[codePoint]

    return glyphCid


def isFontRenderable(text: str, fontObj: TTFont):
    """
    入力したテキストにフォントを適用できるかを確認
    基準文字の後ろに、IVSが1~3個までに対応
    注意：この関数では、文字化けするかどうかしかわからない

    Args:
        text (str): 確認するテキスト

    Returns:
        bool: フォントが対応している場合は、TRUE: 非対応はFALSE
    """
    glyphId_CodePoint = createTools.create_glyphId_CodePoint(fontObj, True)

    # グリフ名を取得
    glyph_names = fontObj.getGlyphNames()

    # テキストを１バイトずつ繰り返す
    is_success = True

    for t, n_t, nn_t, nnn_t in zip(
        text, text[1:] + "\0", text[2:] + "\0\0", text[3:] + "\0\0\0"
    ):  # '\0' は任意の終端を意味する特殊文字
        # print(t)
        # print('n_t => ', n_t)
        # print('nn_t => ', nn_t)
        # print('nnn_t => ', nnn_t)

        # 基本文字がIVDの場合は、スキップ
        if isIVS.is_in_ivs_range(t):
            continue  # 基本文字がIVSなので、処理をスキップ

        if n_t == "\0":
            n_t = None  # 値がない

        if nn_t == "\0":
            nn_t = None

        if nnn_t == "\0":
            nnn_t = None

        glyphCid = getGlyph(glyphId_CodePoint, glyph_names, t, n_t, nn_t, nnn_t)

        if glyphCid == None:
            is_success = False

    return is_success


# フォントのレンダリング関数
def fontRender(
    text: str,
    fontObj: TTFont,
    field_size_xy: tuple[int, int],
    weight: float = 1.0,
    color=(0, 0, 0),
    outLineColor=(0, 0, 0),
    vertical=False,
    margin=50,
):
    """
    与えられたテキストから、画像データにレンダリングする
    異体字セレクタ(IVD)も処理する
    対応している文字がない場合は、エラー
    縦書きオプション付き
    """

    glyphId_CodePoint = createTools.create_glyphId_CodePoint(fontObj, True)
    glyph_names = fontObj.getGlyphNames()

    ascent = fontObj["hhea"].ascent
    descent = fontObj["hhea"].descent
    line_height = ascent - descent
    ascent_v = fontObj["vhea"].ascent
    descent_v = fontObj["vhea"].descent
    lene_weight = ascent_v - descent_v

    # VORGテーブルの取得
    vorg_table = fontObj["VORG"] if "VORG" in fontObj else None

    if vertical:
        vmtx = fontObj["vmtx"]
        # print('縦書きに使うデータ => ', ascent_v, descent_v)
        # print('vmtx => ', vmtx)

    # print(fontObj.keys())

    # print(line_height, ascent, descent)

    # 色情報をRGBに変換
    r = int(color[0]) / 255.0
    g = int(color[1]) / 255.0
    b = int(color[2]) / 255.0

    o_r = int(outLineColor[0]) / 255.0
    o_g = int(outLineColor[1]) / 255.0
    o_b = int(outLineColor[2]) / 255.0

    margin += int(weight / 2)

    # 縦書き専用文字に変換
    if vertical:
        vertical_mapping = {
            "、": "︑",
            "。": "︒",
            "（": "︵",
            "）": "︶",
            "〈": "︿",
            "〉": "﹀",
            "《": "︽",
            "》": "︾",
            "「": "﹁",
            "」": "﹂",
            "『": "﹃",
            "』": "﹄",
            "【": "︻",
            "】": "︼",
            "-": "|",
        }
        text = "".join(vertical_mapping.get(c, c) for c in text)

    images: list[Image.Image] = []
    max_width = 0
    max_heigth = 0
    total_height = 0

    run_text = []
    run_glyphs = []

    for t, n_t, nn_t, nnn_t in zip(
        text, text[1:] + "\0", text[2:] + "\0\0", text[3:] + "\0\0\0"
    ):

        if isIVS.is_in_ivs_range(t):
            continue

        if n_t == "\0":
            n_t = None

        if nn_t == "\0":
            nn_t = None

        if nnn_t == "\0":
            nnn_t = None

        glyphCid = getGlyph(glyphId_CodePoint, glyph_names, t, n_t, nn_t, nnn_t)

        if glyphCid is None:
            print("エラー: 対応していない文字があります")
            break

        glyph = fontObj.getGlyphSet()[glyphCid]

        # グリフの境界ボックスを計算
        class BoundingBoxPen(BasePen):
            def __init__(self):
                super().__init__()
                self.xMin = float("inf")
                self.yMin = float("inf")
                self.xMax = float("-inf")
                self.yMax = float("-inf")

            def moveTo(self, pt):
                self.xMin = min(self.xMin, pt[0])
                self.yMin = min(self.yMin, pt[1])
                self.xMax = max(self.xMax, pt[0])
                self.yMax = max(self.yMax, pt[1])

            def lineTo(self, pt):
                self.xMin = min(self.xMin, pt[0])
                self.yMin = min(self.yMin, pt[1])
                self.xMax = max(self.xMax, pt[0])
                self.yMax = max(self.yMax, pt[1])

            def curveTo(self, pt1, pt2, pt3):
                self.xMin = min(self.xMin, pt1[0], pt2[0], pt3[0])
                self.yMin = min(self.yMin, pt1[1], pt2[1], pt3[1])
                self.xMax = max(self.xMax, pt1[0], pt2[0], pt3[0])
                self.yMax = max(self.yMax, pt1[1], pt2[1], pt3[1])

        pen = BoundingBoxPen()
        glyph.draw(pen)

        # マージンを追加
        glyph_width = 0
        glyph_height = 0
        if vertical:
            glyph_width = lene_weight
            glyph_height = line_height + 2 * margin
        else:
            if pen.xMax == float("-inf") or pen.xMin == float("inf"):
                glyph_width = 2 * margin
            else:
                glyph_width = int(pen.xMax - pen.xMin) + 2 * margin
            glyph_height = int(line_height) + 2 * margin

        # cairoサーフェスの作成
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, glyph_width, glyph_height)
        ctx = cairo.Context(surface)

        # フォントの太さを設定
        ctx.set_line_width(weight)

        # グリフのアウトラインを描画
        class CairoPen(BasePen):
            def __init__(self, ctx, height, offset=(0, 0)):
                super().__init__(None)
                self.ctx = ctx
                self.height = height
                self.offset_x, self.offset_y = offset

            def moveTo(self, pt):
                self.ctx.move_to(
                    pt[0] + self.offset_x, self.height - (pt[1] + self.offset_y)
                )

            def lineTo(self, pt):
                self.ctx.line_to(
                    pt[0] + self.offset_x, self.height - (pt[1] + self.offset_y)
                )

            def curveTo(self, pt1, pt2, pt3):
                self.ctx.curve_to(
                    pt1[0] + self.offset_x,
                    self.height - (pt1[1] + self.offset_y),
                    pt2[0] + self.offset_x,
                    self.height - (pt2[1] + self.offset_y),
                    pt3[0] + self.offset_x,
                    self.height - (pt3[1] + self.offset_y),
                )

            def closePath(self):
                self.ctx.close_path()

        offset_x = 0
        offset_y = 0
        if vertical:
            glyph_v_metrics = vmtx[glyphCid]
            advance = glyph_v_metrics[0]  # グリフの進行量
            bearing = glyph_v_metrics[1]  # グリフの垂直オフセット

            # VORGテーブルを使用してオフセットを調整
            if vorg_table is not None:
                glyph_id = fontObj.getGlyphID(glyphCid)
                if glyph_id in vorg_table.VOriginRecords:
                    vorg_y = vorg_table.VOriginRecords[glyph_id].YPlacement
                    offset_y = (glyph_height - line_height) / 2 + vorg_y
                else:
                    offset_y = (
                        glyph_height - line_height
                    ) / 2  # ベースラインに合わせたオフセット
            else:
                offset_y = (
                    glyph_height - line_height
                ) / 2  # ベースラインに合わせたオフセット

            offset_x = (lene_weight - (pen.xMax - pen.xMin)) / 2 - bearing
        else:
            offset_x = -pen.xMin + margin
            offset_y = glyph_height - ascent

        # print(t, ' => ', pen.xMin, pen.xMax, margin)

        pen = CairoPen(ctx, glyph_height, offset=(offset_x, offset_y))

        # グリフのアウトラインを描画
        glyph.draw(pen)

        # アウトラインを描画
        ctx.set_source_rgb(o_r, o_g, o_b)  # 指定色で描画
        ctx.stroke_preserve()  # アウトラインを描画して保持

        # 塗りつぶし
        ctx.set_source_rgb(r, g, b)
        ctx.fill()

        # cairoサーフェスからPIL画像に変換
        img = Image.frombuffer(
            "RGBA",
            (surface.get_width(), surface.get_height()),
            surface.get_data(),
            "raw",
            "BGRA",
            0,
            1,
        )

        images.append(img)
        run_text.append(t)
        run_glyphs.append(glyphCid)
        max_width = max(max_width, glyph_width)
        max_heigth = max(max_heigth, glyph_height)

        total_height += glyph_height

    base_aspect = field_size_xy[0] / field_size_xy[1]

    # 文字列全体を描画するためのキャンバスを作成
    if vertical:
        # TODO 現状では横書きしか使えない -> 縦書きの時の、文字間隔と文字の引き伸ばしの処理を追加
        canvas = Image.new("RGBA", (max_width, total_height))
        y_offset = 0
        for img in images:
            canvas.paste(img, (0, y_offset))
            y_offset += img.height
    else:
        # 横書き
        total_width = sum(img.width for img in images)
        aspect = total_width / max_heigth
        rate = 1
        space_px = 0
        over_x = 0
        if base_aspect < aspect:
            # フィールドに対して、横が長い時 -> 文字の横幅を圧縮する
            rate = aspect / base_aspect  # rateの分だけ圧縮する
        else:
            # フィールドに対して、横が短い時 -> 文字の間隔をあける
            # 余るスペースのpxを算出し、それを文字の間隔を増やして調整する
            field_x_px = max_heigth * base_aspect
            over_x = field_x_px - total_width
            text_len = len(images)
            space_px = over_x / text_len

        canvas = Image.new("RGBA", (round((total_width / rate) + over_x), max_heigth))
        x_offset = 0
        for i, img in enumerate(images):
            s_px = space_px
            if i == 0:
                s_px = (
                    space_px / 2
                )  # 初回だけ半分 -> 文字の最初と最後はスペースの半分開ける
            img = img.resize((round(img.width / rate), img.height))
            canvas.paste(img, (round(x_offset + s_px), max_heigth - img.height))
            x_offset += img.width + s_px

    # TODO フォントレンダリングの画像確認用
    # canvas.save('text_image.png')

    return canvas


text = "テ鯛鯛󠄀炱鯛󠄁体󠄂辻辻󠄀辻󠄁"
# text = '「テ鯛鯛󠄀鯛󠄁体󠄂辻辻󠄀辻󠄁」。dgysDFEY./'
# # text = '鯛'
# # text = 'あ'
# # text = 'テ'
# # text = '辻'
# # text = '辻󠄁'
# # text = 'さ'

# フォントファイルのパス
font_path = "fonts/HaranoAjiFonts-master/HaranoAjiGothic-Medium.otf"
font = TTFont(font_path)

# isFontRenderable(text, font)
field_size_xy = (150, 20)

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
