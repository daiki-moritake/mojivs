"""Tests for the ``mojivs`` command-line interface."""

import pytest

from mojivs import cli

VS17 = "\U000e0100"
PUA = chr(0xE000)  # Private Use Area character with no glyph in the sample font.


def test_unescape_handles_selectors_and_newline():
    assert cli._unescape(r"辻\U000e0100鯛\n体") == f"辻{VS17}鯛\n体"
    # Surrounding non-ASCII text must survive untouched.
    assert cli._unescape("日本語") == "日本語"


def test_render_writes_png(font_path, tmp_path):
    out = tmp_path / "out.png"
    rc = cli.main(["render", "辻鯛テ", "--font", str(font_path), "-o", str(out), "--size", "48"])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


def test_render_infers_svg_from_extension(font_path, tmp_path):
    out = tmp_path / "out.svg"
    rc = cli.main(["render", "辻鯛", "--font", str(font_path), "-o", str(out)])
    assert rc == 0
    assert out.read_text(encoding="utf-8").lstrip().startswith("<")


def test_render_escape_flag_applies_variation_selector(font_path, tmp_path):
    # With --escape the selector changes the glyph, so the two files differ.
    plain = tmp_path / "plain.png"
    variant = tmp_path / "variant.png"
    cli.main(["render", "辻", "--font", str(font_path), "-o", str(plain), "--backend", "freetype"])
    cli.main(
        [
            "render",
            r"辻\U000e0100",
            "--font",
            str(font_path),
            "-o",
            str(variant),
            "--escape",
            "--backend",
            "freetype",
        ]
    )
    assert plain.read_bytes() != variant.read_bytes()


def test_supports_prints_true(font_path, capsys):
    rc = cli.main(["supports", "辻鯛テ体", "--font", str(font_path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "true"


def test_missing_lists_unsupported(font_path, capsys):
    rc = cli.main(["missing", "辻鯛", "--font", str(font_path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == ""


def test_render_unsupported_returns_error(font_path, tmp_path, capsys):
    # A Private Use Area char has no glyph, so the default on_missing="raise" must
    # surface as a non-zero exit with a message, not an uncaught traceback.
    rc = cli.main(["render", PUA, "--font", str(font_path), "-o", str(tmp_path / "x.png")])
    assert rc == 1
    assert "error" in capsys.readouterr().err


def test_missing_subcommand_exits_nonzero():
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code != 0
