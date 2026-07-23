# Releasing mojivs

Releases are **fully automated**. You never bump a version, write a tag, or draft
release notes by hand — you just merge to `main` with
[Conventional Commits](https://www.conventionalcommits.org/), and
[`.github/workflows/publish.yml`](.github/workflows/publish.yml) does the rest:

1. runs the quality gate (ruff / pyright / pytest),
2. [python-semantic-release](https://python-semantic-release.readthedocs.io/)
   reads the commits since the last tag, computes the next version, bumps it in
   `pyproject.toml` and `src/mojivs/__init__.py`, prepends the release to
   `CHANGELOG.md`, commits, tags, and creates a **GitHub Release**,
3. builds the sdist + wheel and uploads them to
   [PyPI](https://pypi.org/project/mojivs/) via **Trusted Publishing (OIDC)** —
   no API token or secret is stored in the repo.

If no releasable commits are present, nothing is published.

## Branch model

| Branch | Purpose |
|---|---|
| feature branches | One change each; open a PR into `develop`. |
| `develop` | Integration branch where work accumulates. |
| `main` | Release branch. **Merging into `main` triggers a release.** |

Day-to-day: `feature/*` → PR → `develop`. When you want to ship, open a PR from
`develop` into `main` and merge it. That merge is what cuts the release.

## Commit messages drive the version

python-semantic-release parses the commit subjects on `main`. Use Conventional
Commit types:

| Commit | Example | Effect (while on 0.x) |
|---|---|---|
| `fix:` | `fix(render): clip overhanging ink` | patch — `0.4.0 → 0.4.1` |
| `feat:` | `feat(render): builtin backend` | minor — `0.4.0 → 0.5.0` |
| `feat!:` / `BREAKING CHANGE:` | breaking API change | minor while on 0.x (see below) |
| `docs:` / `test:` / `chore:` / `refactor:` / `ci:` | housekeeping | no release |

We stay on 0.x semantics (`allow_zero_version = true`, `major_on_zero = false` in
[`pyproject.toml`](pyproject.toml)), so even a breaking change bumps the *minor*
rather than jumping to 1.0.0. Flip `major_on_zero = true` (or cut `v1.0.0`
manually once) when the API is ready to commit to stability.

> **If you squash-merge**, the squash commit message becomes the release note
> source — keep the squash commit's title Conventional (GitHub uses the PR title
> by default, so name PRs like `feat(render): …`).

## One-time setup

Do these once, as a maintainer.

1. **Register a Trusted Publisher on PyPI**
   (<https://pypi.org/manage/account/publishing/>). For a brand-new project use
   the "Add a new pending publisher" form:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `mojivs` |
   | Owner | `daiki-moritake` |
   | Repository name | `mojivs` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   The publisher is bound to the **workflow filename** (`publish.yml`) and the
   **environment** (`pypi`). Keep both as-is — renaming either breaks OIDC.

2. **Create the `pypi` GitHub environment**: Repo → Settings → Environments →
   **New environment** → `pypi`. Optionally add required reviewers there to put a
   human approval in front of each PyPI upload.

3. **Let the release job write to `main`.** python-semantic-release pushes the
   version-bump commit and tag using `GITHUB_TOKEN`, so:
   - Settings → Actions → General → **Workflow permissions** → enable
     **Read and write permissions**.
   - If `main` is a protected branch, allow the automation to push to it —
     Settings → Branches → the `main` rule → add **`github-actions[bot]`** (or
     the repo's app) to **"Allow specified actors to bypass required pull
     requests"**. Otherwise the release job fails to push.

   > Pushes and releases made with `GITHUB_TOKEN` do **not** trigger new workflow
   > runs, so the version-bump commit will not start another release or CI loop.

## Cutting a release

Just merge into `main`:

```bash
# from an up-to-date develop
gh pr create --base main --head develop --title "release: ship latest" --body "..."
# review, then merge — this triggers publish.yml
```

Then watch the run under the **Actions** tab. On success the new version appears
on <https://pypi.org/project/mojivs/> and a matching GitHub Release is created.

To retry a stuck run without new commits, use the **workflow_dispatch** trigger
("Run workflow" button) on the `publish.yml` workflow.

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
