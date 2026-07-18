---
name: Bug report
about: Report incorrect rendering, a crash, or unexpected behavior
title: "[bug] "
labels: bug
---

## Description

A clear description of what went wrong.

## Reproduction

```python
from mojivs import IVSFont

font = IVSFont("...otf")
# Put variation selectors as escapes, e.g. "辻\U000e0100"
font.render("...", size=64)
```

- **Font used** (name / source):
- **Input string** (with selectors as `\U000eXXXX`):
- **Backend**: cairo / freetype
- **Output format**: PNG / SVG / PDF

## Expected vs. actual

- Expected:
- Actual (attach the image/SVG if it's a rendering issue):

## Environment

- mojivs version (`python -c "import mojivs; print(mojivs.__version__)"`):
- Python version:
- OS:
- Installed extras (`mojivs[cairo]` / `mojivs[freetype]` / `mojivs[pdf]`):
