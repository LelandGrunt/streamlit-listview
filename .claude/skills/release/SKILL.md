---
name: release
description: Cut a streamlit-listview release to PyPI. Chooses the version, bumps it in the five files that assert it, dates the changelog, regenerates the README tour, runs the manual checks, and hands the user the tag push and the push of main in the right order. Use when the user asks to release, publish, bump the version, cut a pre-release or rc, or tag a version.
---

# Release streamlit-listview to PyPI

A `v*.*.*` tag pushed to GitHub runs `.github/workflows/release.yml`, which publishes through PyPI Trusted Publishing (OIDC). No API token lives in the repo. The clone needs the pre-push hook (root `CLAUDE.md`, *Pushing to GitHub*).

## What the workflow does

- **build:**
  1. `scripts/push_gate.py check tag` checks that the tag names `[project].version`, that the five files and `uv.lock` agree, that the changelog dates the version and contains no "Unreleased", that PyPI lacks the version, and that GitHub's `main` can fast-forward to the tagged commit.
  2. It builds the frontend, then runs its tests, in that order, as CI does.
  3. It installs the package editable and runs the unit tests with the coverage gate.
  4. It runs `uv build` with `LISTVIEW_SKIP_NPM_BUILD=1`, so the tested bundle is the packaged one.
  5. It runs `scripts/verify_wheel.py` and `uvx twine check --strict`, and uploads the distributions.
- **publish-to-pypi:** runs `pypa/gh-action-pypi-publish` in the `pypi` environment with `id-token: write`; it also uploads PEP 740 attestations.
- **github-release:** signs the distributions with Sigstore and creates the GitHub Release. Its notes are the version's section of `CHANGELOG.md`, with relative links pointed at the tag, followed by GitHub's generated compare link. An `a`, `b` or `rc` tag adds `--prerelease`.

## Steps

1. **Choose the version by Semantic Versioning,** from the entries under *Unreleased*: a patch (`1.0.2`) when they are only *Fixed* or *Security*, a minor (`1.1.0`) otherwise. An entry marked **Breaking** also takes a minor, because the project stays on 1.x. The section then opens with the notice that the release breaks compatibility, as the header of `CHANGELOG.md` promises.
2. **Bump the version in the five files that assert it.** The push gate refuses the tag, and the release job fails, when one disagrees.
   1. `[project].version` in the root `pyproject.toml`, the source of truth. The tag guard and `verify_wheel.py`'s wheel-filename check compare against it.
   2. `[project].version` in `streamlit_listview/pyproject.toml`. `tests/test_packaging.py::test_versions_agree` pins it to the root.
   3. `EXPECTED_VERSION` in `tests/test_packaging.py`. `test_root_version_is_target` and `test_nested_version_is_target` compare both files against it.
   4. The wheel and sdist filename examples in `README.md`. `tests/test_readme.py::test_version_matches_pyproject_and_no_stale_scaffold` pins them to the root. The version badge needs no bump: it is the live shields.io PyPI badge.
   5. The `streamlit-listview==<version>` pin in `demo/requirements.txt`, which Streamlit Community Cloud and the Codespaces dev container (`.devcontainer/devcontainer.json`) install. `tests/test_packaging.py::test_demo_requirements_pin_the_released_version` pins it to the root.

   `streamlit_listview/frontend/package.json` and `package-lock.json` carry `1.0.0` and do not follow the release: the frontend package is private and never published.
3. **Run `uv lock`,** so that `uv.lock` records the new version; otherwise the next `uv run` rewrites it as an unrelated diff. The `uv-audit` hook refuses the commit, and the push gate the push, until then.
4. **Turn the `Unreleased` section of `CHANGELOG.md` into the release.**
   - The heading becomes `## [<version>] - <date>`, and the link `[Unreleased]: …/compare/v<previous>...HEAD` becomes `[<version>]: …/compare/v<previous>...v<version>`.
   - The notice of a release that breaks compatibility stays the first line of the section.
   - The date lies at most one day after the current UTC date; the push gate refuses a later one.
   - The push gate and the release job refuse the tag while the word "Unreleased" remains anywhere in the file.
5. **Regenerate the README tour** (`assets/listview-tour.gif`). The demo shows the installed version next to its title, so record the tour after the bump has reached the editable install and before the release commit. `uv run` reinstalls the project once `pyproject.toml` changes, and the tour command runs through it:

   ```sh
   npm --prefix streamlit_listview/frontend run build
   LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel --with imageio-ffmpeg python scripts/gif/screencast.py
   ```

   Check that the badge in the new GIF reads the new version. No check enforces this.
6. **Run the manual checks:** `pre-commit run --hook-stage manual --all-files`. They check the links in every Markdown file, render every Mermaid diagram and run the e2e suite in Firefox and WebKit; no commit, CI run or push runs them. Fix what they report before the release commit. CI and the push gate run the e2e suite in Chromium.
7. **Commit, then tag.** Land the release commit on local `main` as `chore(release): bump the version to <version>`, then tag it: `git tag v<version>`.
8. **Hand the user the tag push; never run it yourself.** The confirmation `-c listview.pushGithub=<version>` is the user's decision to publish:

   ```sh
   git -c listview.pushGithub=<version> push <github-remote> v<version>
   ```

   - The command names the GitHub remote, because the workflow runs only on GitHub, and a bare `git push --tags` goes to the default remote, which need not be GitHub.
   - The push gate refuses a version that PyPI already has and a tag that GitHub's `main` could not fast-forward to.
   - It then runs CI's checks locally on the tagged commit, the browser tests in Chromium included. The commit must be `HEAD` of a clean tree. The checks take several minutes.
   - The build job fails when the tag differs from `[project].version`, so the tag and the published wheel always agree.
9. **Hand the user the push of `main`, to run once the publish job has finished:**

   ```sh
   git -c listview.pushGithub=<version> push <github-remote> main
   ```

   - Community Cloud redeploys on every push to `main` and installs the pin from PyPI. The push gate refuses this push until PyPI serves the version, so the hosted demo never installs a missing pin.
   - The checks pass at once: the gate remembers that the tag push ran them on the same commit.

## Pre-releases

- **Use PEP 440's canonical spelling:** `1.0.0rc1` (or `a1`, `b1`) in the five files, tagged `v1.0.0rc1`. `uv lock` and the changelog heading follow it.
- **The push gate accepts only `X.Y.Z`, or `X.Y.Z` followed by `a`, `b` or `rc` and a number.** It refuses `1.0.0-rc.1`, `1.0.0.post1` and `1.0.0.dev1` before anything leaves the clone.
- **PyPI never accepts a version number twice,** not even after a deletion, so a broken rc is followed by `rc2`.
- **`pip install streamlit-listview` skips pre-releases;** the exact pin in `demo/requirements.txt` lets the hosted demo run the rc.

## Settings outside the repo

These settings exist since the 1.0.0 release. Check them when a release fails for want of permission; set them up again only for a new repository or a new PyPI project.

1. **PyPI:** under *Account settings → Publishing*, a **Trusted Publisher** names this GitHub repo's owner and name, the workflow `release.yml` and the environment `pypi`. For a project that PyPI does not know yet, the **pending publisher** form adds the project name `streamlit-listview`.
2. **GitHub environment:** under *Settings → Environments*, the environment **`pypi`**. Required reviewers there would gate each publish.
3. **GitHub rulesets**, under *Settings → Rules → Rulesets*:
   - `main`: the default branch can be neither deleted nor force-pushed.
   - `release tags`: a `v*` tag can be neither updated nor deleted nor force-pushed.
   - `only main`: no other branch can be created or updated on GitHub, so feature branches go to Azure DevOps.

## Background

- **One wheel and one sdist cover every platform.** The package is pure `py3-none-any`, because the React bundle is data, not a compiled extension. The sdist ships the prebuilt `frontend/build/` and omits `frontend/src/`, so installing from it needs no Node.
- **The workflow references actions by version tag,** as CI does. `pypa/gh-action-pypi-publish` follows its `release/v1` branch, which pypa moves to ship fixes. `sigstore/gh-action-sigstore-python` uses a full version tag, because the project publishes no floating major tag.
- **uv installs cold in the release build.** `astral-sh/setup-uv` (v10.2.0) skips its cache on tag pushes by default (`enable-cache: auto`), so no cache from another run feeds the release. `actions/setup-node` restores the npm cache (`cache: npm`), and `npm ci` checks every package against the integrity hashes in `package-lock.json`.
