#!/usr/bin/env python3
"""Refresh the bundled Unicode IVD table (``src/mojivs/data/ivd.txt``).

The Ideographic Variation Database (IVD) is published by the Unicode Consortium
as ``IVD_Sequences.txt``. mojivs vendors it so that IVS -> CID resolution works
offline with no network access at runtime. This script re-downloads that file
so the vendored copy can be kept in sync with new IVD releases.

Usage::

    # Download the latest release Unicode links from the IVD landing page.
    python scripts/update_ivd.py

    # Pin a specific dated release (recommended for reproducibility).
    python scripts/update_ivd.py --version 2022-09-13

    # Point at an explicit URL or a local file.
    python scripts/update_ivd.py --url https://www.unicode.org/ivd/data/2022-09-13/IVD_Sequences.txt
    python scripts/update_ivd.py --url ./IVD_Sequences.txt

The raw file is written verbatim (comments and header included) so the source
version and date recorded in its header travel with the data. mojivs' parser
(:mod:`mojivs.ivs`) skips comment/blank lines, so the extra header costs
nothing at runtime while making provenance auditable.

Sources:
    IVD landing page:  https://www.unicode.org/ivd/
    Data directory:    https://www.unicode.org/ivd/data/
    Terms of use:      https://www.unicode.org/copyright.html
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

# Unicode publishes each IVD revision under a dated directory. Bump this default
# when adopting a newer release, or pass --version / --url to override.
DEFAULT_VERSION = "2022-09-13"
BASE_URL = "https://www.unicode.org/ivd/data"

DEST = Path(__file__).resolve().parent.parent / "src" / "mojivs" / "data" / "ivd.txt"

# Collections mojivs currently resolves. Purely informational — the vendored
# file keeps every collection; this is only used for the post-download summary.
KNOWN_COLLECTIONS = ("Adobe-Japan1", "Hanyo-Denshi", "Moji_Joho")


def _read_source(url: str) -> str:
    """Fetch ``url`` (http(s) or local path) and return its text."""
    if "://" not in url or url.startswith("file://"):
        path = url[len("file://") :] if url.startswith("file://") else url
        return Path(path).read_text(encoding="utf-8")
    print(f"Downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as response:  # noqa: S310 - fixed Unicode host
        return response.read().decode("utf-8")


def _summarize(text: str) -> None:
    """Print a per-collection sequence count so changes are reviewable."""
    counts = dict.fromkeys(KNOWN_COLLECTIONS, 0)
    total = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(";")
        if len(parts) < 3:
            continue
        total += 1
        collection = parts[1].strip()
        if collection in counts:
            counts[collection] += 1
    print(f"  total sequences: {total}", file=sys.stderr)
    for name, count in counts.items():
        print(f"  {name}: {count}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help=f"Dated IVD release under {BASE_URL} (default: {DEFAULT_VERSION}).",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Explicit URL or local path to IVD_Sequences.txt (overrides --version).",
    )
    args = parser.parse_args()

    url = args.url or f"{BASE_URL}/{args.version}/IVD_Sequences.txt"
    text = _read_source(url)

    if "; Adobe-Japan1;" not in text:
        print(
            "error: downloaded file does not look like IVD_Sequences.txt "
            "(no Adobe-Japan1 rows found)",
            file=sys.stderr,
        )
        return 1

    DEST.write_text(text, encoding="utf-8")
    print(f"Wrote {DEST} ({len(text.encode('utf-8')):,} bytes)", file=sys.stderr)
    _summarize(text)
    print(
        "\nReview the diff, run the tests, and update CHANGELOG.md before committing.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
