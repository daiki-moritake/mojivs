# Releasing mojivs

Releases are published to [PyPI](https://pypi.org/project/mojivs/) automatically
by [`.github/workflows/publish.yml`](.github/workflows/publish.yml) whenever a
GitHub Release is published. Publishing uses **PyPI Trusted Publishing (OIDC)**,
so no API token or secret is stored in the repository.

Once published, the package installs with either pip or uv:

```bash
pip install "mojivs[cairo]"
uv add "mojivs[cairo]"
```

## One-time setup (PyPI side)

Do this once, before the first release. It requires a PyPI account and can only
be done by a maintainer.

1. **Register a Trusted Publisher (pending publisher)** on PyPI:
   <https://pypi.org/manage/account/publishing/>

   Fill in the "Add a new pending publisher" form:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `mojivs` |
   | Owner | `daiki-moritake` |
   | Repository name | `mojivs` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   (A "pending publisher" lets you claim a brand-new project name; PyPI creates
   the project on the first successful upload.)

2. **Create the `pypi` GitHub environment** (optional but recommended):
   Repo → Settings → Environments → **New environment** → name it `pypi`. You can
   add required reviewers here so a human approves each publish.

## Cutting a release

1. Update the version in [`pyproject.toml`](pyproject.toml) (`[project] version`)
   and in [`src/mojivs/__init__.py`](src/mojivs/__init__.py) (`__version__`).
2. Move the `CHANGELOG.md` `[Unreleased]` entries under a new version heading.
3. Commit, then tag and push:

   ```bash
   git commit -am "release: v0.3.0"
   git tag v0.3.0
   git push origin main --tags
   ```

4. Create the GitHub Release for that tag (this triggers publishing):

   ```bash
   gh release create v0.3.0 --title v0.3.0 --notes-from-tag
   ```

5. Watch the run under the **Actions** tab. On success the version appears on
   <https://pypi.org/project/mojivs/>.

## Testing against TestPyPI (optional)

To rehearse without touching real PyPI, register a second Trusted Publisher on
<https://test.pypi.org/manage/account/publishing/> and temporarily point the
publish step at TestPyPI:

```yaml
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
```

Then install with `pip install --index-url https://test.pypi.org/simple/ mojivs`.
