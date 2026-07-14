"""Tests for the SVG and PDF exporters."""

import pytest


def test_to_svg_is_wellformed(font):
    import xml.etree.ElementTree as ET

    svg = font.to_svg("辻鯛テ", size=64, color="#123456")
    assert svg.startswith("<svg")
    # Parses as XML and has one <path> per glyph.
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    paths = root.findall(f"{ns}path")
    assert len(paths) == 3
    assert root.get("width") and root.get("height")


def test_to_svg_background_adds_rect(font):
    svg = font.to_svg("辻", size=48, background="#ffffff")
    assert "<rect" in svg


def test_to_svg_vertical(font):
    svg = font.to_svg("あい", size=48, direction="vertical")
    assert svg.startswith("<svg") and "<path" in svg


def test_to_pdf_writes_file(font, tmp_path):
    reportlab = pytest.importorskip("reportlab")
    out = tmp_path / "out.pdf"
    font.to_pdf("辻鯛テ", out, size=64, color="#000", stroke="#f00", stroke_width=3)
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")


def test_to_pdf_vertical(font, tmp_path):
    pytest.importorskip("reportlab")
    out = tmp_path / "v.pdf"
    font.to_pdf("あい\nうえ", out, size=48, direction="vertical")
    assert out.exists() and out.read_bytes().startswith(b"%PDF")
