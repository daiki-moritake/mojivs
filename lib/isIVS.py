
def is_in_ivs_range(unicode_char):
    """
    与えられた文字の Unicode コードポイントが、E0100 から E01EF の範囲内にあるかを判定します。

    Args:
        unicode_char (str): 判定する文字

    Returns:
        bool: 文字の Unicode コードポイントが範囲内にある場合は True、そうでなければ False
    """

    codepoint = ord(unicode_char)
    return 0xE0100 <= codepoint <= 0xE01EF

# 使用例

# text = '葛󠄀'
# for c in text:
#     print(f"'{c}' は IVS ですか？: {is_in_ivs_range(c)}")
    
