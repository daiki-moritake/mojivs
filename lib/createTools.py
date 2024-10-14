from PIL import Image, ImageDraw
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import tempfile
import re


def create_unicode_to_id_dict(file_path, collection_name, is_re=False):
    """
    与えられたテキストファイルから、指定されたコレクションの Unicode コードポイントと ID の対応関係を辞書として作成します。

    Args:
        file_path (str): テキストファイルのパス
        collection_name (str): コレクション名 (例: 'Adobe-Japan1', 'Moji_Joho')
        is_re (bool): デフォルト False  Trueで辞書のキーとUnicodeを逆にする

    Returns:
        dict: Unicode コードポイントと ID の対応関係を格納した辞書
    """

    unicode_to_id_dict = {}
    unicode_to_id_dict_reLookup = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line:
                continue
            parts = line.split(";")
            # リストの要素数が 4 つ以上ある場合のみ、parts[3] にアクセス
            if len(parts) >= 3:
                unicode_codepoint = parts[0]
                collection = parts[1]
                # 空白がある可能性がある
                if re.sub(r"\s+", "", collection) == re.sub(
                    r"\s+", "", collection_name
                ):
                    id_value = parts[2]
                    id_code = re.sub(
                        r"\s+", "", re.sub("\n", "", id_value)
                    )  # 改行コードと空白を消去
                    unicode_to_id_dict[unicode_codepoint] = id_code
                    unicode_to_id_dict_reLookup[id_code] = unicode_codepoint
    if is_re:
        return unicode_to_id_dict_reLookup
    else:
        return unicode_to_id_dict


# テキストファイルのパス
file_path = "ivd.txt"  # ファイル名を指定

# Adobe-Japan1 の辞書を作成
adobe_japan1_dict = create_unicode_to_id_dict(file_path, "Adobe-Japan1")
adobe_japan1_dict_re = create_unicode_to_id_dict(file_path, "Adobe-Japan1", True)
Hanyo_Denshi = create_unicode_to_id_dict(file_path, "Hanyo-Denshi")
Hanyo_Denshi_re = create_unicode_to_id_dict(file_path, "Hanyo-Denshi", True)
Moji_Joho = create_unicode_to_id_dict(file_path, "Moji_Joho")
Moji_Joho_re = create_unicode_to_id_dict(file_path, "Moji_Joho", True)


def create_glyphId_CodePoint(font: TTFont, is_re=False):
    """
    フォントのグリフIDとコードポイントの関係を取得する
    キー:グリフID
    バリュー:コードポイント

    font_path (str): OTFフォントのパス
    is_re (bool): デフォルト: False   Trueにすると、キーとバリューが逆になる
    """

    # グリフ名を取得
    glyph_names = font.getGlyphNames()

    # グリフセットを取得
    glyph_set = font.getGlyphSet()

    # cmap テーブルを取得
    cmap_table = font["cmap"]

    # cmap テーブルのフォーマットを確認
    cmap_format = cmap_table.tables[0].format

    glyphId_CodePoint = {}
    glyphId_CodePoint_reLookup = {}

    # フォーマットが 4 の場合、サブテーブルを直接アクセス
    if cmap_format == 4:
        # サブテーブルの情報を表示
        # print(f"Platform ID: {cmap_table.tables[0].platformID}")
        # print(f"Encoding ID: {cmap_table.tables[0].platEncID}")
        # print(f"Language ID: {cmap_table.tables[0].language}")
        # print("-------------------------")

        # サブテーブル内のすべての文字コードとグリフ ID のペアをループ処理
        for codepoint, glyph_id in cmap_table.tables[0].cmap.items():
            # 文字コードとグリフ ID を表示
            # print(f"コードポイント: U+{codepoint:04X}, グリフ ID: {glyph_id}")
            glyphId_CodePoint[glyph_id] = codepoint
            glyphId_CodePoint_reLookup[codepoint] = glyph_id
        # print("=========================")
    else:
        # フォーマットが 4 以外の場合、通常のアンパック処理を行う
        for platform_id, encoding_id, language_id, table in cmap_table.tables:
            # サブテーブルの情報を表示
            # print(f"Platform ID: {platform_id}")
            # print(f"Encoding ID: {encoding_id}")
            # print(f"Language ID: {language_id}")
            # print("-------------------------")

            # サブテーブル内のすべての文字コードとグリフ ID のペアをループ処理
            for codepoint, glyph_id in table.cmap.items():
                # 文字コードとグリフ ID を表示
                # print(f"コードポイント: U+{codepoint:04X}, グリフ ID: {glyph_id}")
                glyphId_CodePoint[glyph_id] = codepoint
                glyphId_CodePoint_reLookup[codepoint] = glyph_id
            # print("=========================")

    if is_re:
        return glyphId_CodePoint_reLookup
    else:
        return glyphId_CodePoint
