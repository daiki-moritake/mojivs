from pathlib import Path

import pytest

from mojivs import IVSFont

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts" / "HaranoAjiFonts-master"
GOTHIC = FONT_DIR / "HaranoAjiGothic-Medium.otf"


@pytest.fixture(scope="session")
def font_path() -> Path:
    if not GOTHIC.exists():
        pytest.skip(f"sample font not found: {GOTHIC}")
    return GOTHIC


@pytest.fixture(scope="session")
def font(font_path) -> IVSFont:
    return IVSFont(font_path)
