# scripts/

Maintenance scripts for mojivs. Not shipped in the wheel or sdist.

## `update_ivd.py` — refresh the bundled IVD table

`src/mojivs/data/ivd.txt` is a vendored copy of the Unicode **Ideographic
Variation Database** (`IVD_Sequences.txt`). It powers IVS → CID resolution in
[`mojivs.ivs`](../src/mojivs/ivs.py) and is bundled so resolution works offline.

To update it to a newer Unicode IVD release:

```bash
python scripts/update_ivd.py --version 2022-09-13   # pin a dated release
python scripts/update_ivd.py                         # use the script default
```

Then review the diff, run `pytest`, and note the change in
[`CHANGELOG.md`](../CHANGELOG.md).

- **Source:** <https://www.unicode.org/ivd/> (data under
  <https://www.unicode.org/ivd/data/>)
- **License:** the IVD is subject to the Unicode Terms of Use
  (<https://www.unicode.org/copyright.html>); see the repository
  [`LICENSE`](../LICENSE).
