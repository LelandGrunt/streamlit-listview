---
name: release
description: Cut a streamlit-listview release to PyPI. Bumps the version in all five places that assert it, updates the changelog, regenerates the README tour, and tags and pushes in the right order. Use when the user asks to release, publish, bump the version, cut a pre-release or rc, or tag a version.
---

# Release streamlit-listview to PyPI

A `v*.*.*` tag pushed to GitHub runs `.github/workflows/release.yml`, which publishes through PyPI Trusted Publishing (OIDC). No API token lives in the repo.

## What the workflow does
- **build:** runs `scripts/push_gate.py check tag`, which checks that the tag names `[project].version`, that the five places and `uv.lock` agree, that the changelog dates the version and contains no "Unreleased", that PyPI lacks the version, and that GitHub's `main` can fast-forward to the tagged commit; builds the frontend, then runs its tests (in that order, as in CI); installs the package editable and runs the unit tests; runs `uv build` with `LISTVIEW_SKIP_NPM_BUILD=1`, so the tested bundle is the packaged one; then runs `scripts/verify_wheel.py` and `uvx twine check --strict`.
- **publish-to-pypi:** runs `pypa/gh-action-pypi-publish` in the `pypi` environment with `id-token: write`; it also uploads PEP 740 attestations.
- **github-release:** signs the distributions with Sigstore and creates the GitHub Release with `--generate-notes`, adding `--prerelease` for an `a`, `b` or `rc` tag.

## Steps
1. **Bump the version in all five places that assert it.** The release job runs the unit suite and `verify_wheel.py` before it publishes, so a missed place fails the release.
   1. `[project].version` in the root `pyproject.toml`, the source of truth. The tag guard and `verify_wheel.py`'s wheel-filename check compare against it.
   2. `[project].version` in `streamlit_listview/pyproject.toml`. `tests/test_packaging.py::test_versions_agree` pins it to the root.
   3. `EXPECTED_VERSION` in `tests/test_packaging.py`. `test_root_version_is_target` and `test_nested_version_is_target` compare both files against it.
   4. The wheel and sdist filename examples in `README.md`. `tests/test_readme.py::test_version_matches_pyproject_and_no_stale_scaffold` pins them to the root. The version badge needs no bump: it is the live shields.io PyPI badge.
   5. The `streamlit-listview==<version>` pin in `demo/requirements.txt`, which Streamlit Community Cloud and the Codespaces dev container (`.devcontainer/devcontainer.json`) install. `tests/test_packaging.py::test_demo_requirements_pin_the_released_version` pins it to the root.
2. **Run `uv lock`,** so that `uv.lock` records the new version; otherwise the next `uv run` rewrites it as an unrelated diff. The `uv-audit` hook refuses the commit, and the push gate the push, until then.
3. **Turn the `Unreleased` section of `CHANGELOG.md` into the release.** The heading becomes `## [<version>] - <date>`, and the link `[Unreleased]: …/compare/v<previous>...HEAD` becomes `[<version>]: …/compare/v<previous>...v<version>`. The push gate and the release job refuse the tag while the word "Unreleased" remains anywhere in the file.
4. **Regenerate the README tour** (`assets/listview-tour.gif`). The demo shows the installed version next to its title, so record the tour after the bump has reached the editable install and before the release commit. `uv run` reinstalls the project once `pyproject.toml` changes, and the tour command runs through it:
   ```sh
   npm --prefix streamlit_listview/frontend run build
   LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel --with imageio-ffmpeg python scripts/gif/screencast.py
   ```
   Check that the badge in the new GIF reads the new version. No check enforces this.
5. **Commit, then tag:** `git tag v<version>`.
6. **Push the tag to the GitHub remote by name, with the confirmation:** `git -c listview.pushGithub=<version> push <github-remote> v<version>`. The workflow runs only on GitHub, and a bare `git push --tags` goes to the default remote, which need not be GitHub. The push gate refuses a version that PyPI already has and a tag that GitHub's `main` could not fast-forward to, and it runs the full CI suite on the tagged commit, which must be `HEAD` of a clean tree; the suite takes several minutes. The build job fails when the tag differs from `[project].version`, so the tag and the published wheel always agree.
7. **Push the branch only after the publish job has finished:** `git -c listview.pushGithub=<version> push <github-remote> main`. Community Cloud redeploys on every branch push and installs the pin from PyPI. The push gate refuses the push until PyPI serves the version, so the hosted demo never installs a missing pin. The suite result comes from the tag push of the same commit.

Steps 6 and 7 publish. Confirm each push with the user before running it.

## Pre-releases
- **Use PEP 440's canonical spelling in all five places:** `1.0.0rc1` (or `a1`, `b1`), tagged `v1.0.0rc1`.
- **Never `1.0.0-rc.1` or `1.0.0-preRelease`.** The second is no valid version. The first becomes `1.0.0rc1` in the wheel filename, while the tag guard and `verify_wheel.py` compare the raw string, so the release fails.
- **PyPI never accepts a version number twice,** not even after a deletion, so a broken rc is followed by `rc2`.
- **`pip install streamlit-listview` skips pre-releases;** the exact pin in `demo/requirements.txt` lets the hosted demo run the rc.

## One-time setup
A maintainer with PyPI access does this once, before the first release:
1. On PyPI, under *Account settings → Publishing*, add a **Trusted Publisher**: this GitHub repo's owner and name, the workflow `release.yml` and the environment `pypi`. Before the first publish the project does not exist yet; use the **pending publisher** form, which adds the project name `streamlit-listview`.
2. In the GitHub repo, under *Settings → Environments*, create the environment **`pypi`**. Required reviewers or a tag protection rule can gate the releases.

## Background
- **One wheel and one sdist cover every platform.** The package is pure `py3-none-any`, because the React bundle is data, not a compiled extension. The sdist ships the prebuilt `frontend/build/` and omits `frontend/src/`, so installing from it needs no Node.
- **The workflow references actions by version tag,** as CI does. `pypa/gh-action-pypi-publish` follows its `release/v1` branch, which pypa moves to ship fixes. `sigstore/gh-action-sigstore-python` uses a full version tag, because the project publishes no floating major tag.
- **The release build installs cold, on purpose.** With `astral-sh/setup-uv` ≥ v10, the default `enable-cache: auto` skips the uv cache on tag pushes.
