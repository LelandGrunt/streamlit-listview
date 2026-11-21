# Pinned Search Width Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The pinned search field and the Select all toggle shrink with a narrow frame instead of running out past its right border.

**Architecture:** One CSS declaration, `min-width: 0` on `.listview-header > .listview-search`, lets the flex item shrink below the input's intrinsic width. A stylesheet test pins the declaration, and an e2e test measures three searchable listviews in a 180 px container.

**Tech Stack:** CSS, vitest (`listview-css.test.ts`), Playwright e2e on Streamlit 1.66.

**Spec:** `docs/superpowers/specs/2026-11-21-pinned-search-width-design.md`

## Global Constraints

- Every command runs from the repository root through `uv` or `npm --prefix streamlit_listview/frontend`; Python commands that serve the bundle take `LISTVIEW_SKIP_NPM_BUILD=1` after a fresh `npm run build`.
- The root `CLAUDE.md` requires the hero GIF in the same commit as a change to `listview.css`, so the fix, its tests, the changelog and any new GIF land in **one** commit. Commit the GIF only if its bytes change.
- Never pass `--no-verify`; fix what a pre-commit hook reports.
- The changelog entry follows the repository's writing rule (Strunk & White, measured numbers, written for a Python user).

## Review Focus

- A sidebar listview: the e2e test measures a main-body container; the sidebar only swaps colors, so the same rule governs it. The visual comparison's `sidebar` scenario shows it.
- Firefox and WebKit: CI runs the e2e test in Chromium only. Firefox was measured by hand (see the spec); `pre-commit run --hook-stage manual e2e-browsers --all-files` covers both before the next release.
- The clear (×) button in a narrow pinned field: it sits absolutely inside `.listview-search`, so it moves with the field's right edge. No extra test.

---

### Task 1: Let the pinned search field shrink

**Files:**

- Modify: `streamlit_listview/frontend/src/listview.css:941-944`
- Test: `streamlit_listview/frontend/src/__tests__/listview-css.test.ts` (describe "Milestone C feature styling")
- Modify: `e2e/app_features.py` (append a section)
- Modify: `e2e/conftest.py:37` (`LISTVIEW_COUNTS["app_features.py"]`: 9 → 12)
- Test: `e2e/test_features.py`

**Interfaces:**

- Produces: three keyed listviews in `app_features.py`, labels `Narrow in-flow`, `Narrow pinned`, `Narrow pinned with Select all`, keys `narrow_inflow`, `narrow_pinned`, `narrow_selectall`.

- [ ] **Step 1: Record the visual baseline before any change**

```sh
npm --prefix streamlit_listview/frontend ci
npm --prefix streamlit_listview/frontend run build
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel playwright install chromium
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --all --record bench-results/visual/before
```

Expected: `bench-results/visual/before/meta.json` exists.

- [ ] **Step 2: Write the failing stylesheet test**

```ts
it("lets the pinned search field shrink below its input's intrinsic width", () => {
  expect(css).toMatch(
    /\.listview-header\s*>\s*\.listview-search\s*\{[^}]*min-width:\s*0/,
  );
});
```

Run: `npx vitest run src/__tests__/listview-css.test.ts` in `streamlit_listview/frontend/`. Expected: this one test FAILS.

- [ ] **Step 3: Add the narrow listviews to the harness**

Append to `e2e/app_features.py` a subheader "Narrow frame" and, inside `st.container(width=180)`, three listviews over `OPTIONS` with `height=120` and `enable_search=True`: `narrow_inflow` (single), `narrow_pinned` (single, `pin_search=True`), `narrow_selectall` (multi, `pin_search=True`, `select_all=True`). A comment says why 180 px: the input's intrinsic width makes the field about 250 px wide. Update `LISTVIEW_COUNTS` to 12 and its comment, and add the three names to `_INSTANCE_NAME` in `test_features.py`.

- [ ] **Step 4: Write the failing e2e test**

```python
@pytest.mark.parametrize(
    "instance", ["narrow_inflow", "narrow_pinned", "narrow_selectall"]
)
def test_the_search_field_fits_a_narrow_frame(page: Page, instance: str):
    search = _root(page, instance).get_by_test_id("stListviewSearch")
    edges = search.evaluate(
        """input => {
            const part = input.closest('.listview-header, .listview-body');
            return {
                frame: part.getBoundingClientRect().right,
                controls: [...part.querySelectorAll('.listview-search__input, .listview-select-all')]
                    .map(el => el.getBoundingClientRect().right),
            };
        }"""
    )
    assert len(edges["controls"]) == (2 if instance == "narrow_selectall" else 1)
    assert all(right <= edges["frame"] for right in edges["controls"]), edges
```

Run: `LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel pytest e2e/test_features.py -k narrow`. Expected: `narrow_inflow` PASSES, `narrow_pinned` and `narrow_selectall` FAIL with the input about 75 px past the frame.

- [ ] **Step 5: Add `min-width: 0` to `.listview-header > .listview-search`**

Extend the comment above the rule: a flex item keeps `min-width: auto` and so never shrinks below the input's intrinsic width of about 20 characters.

- [ ] **Step 6: Build and run both tests**

```sh
npm --prefix streamlit_listview/frontend run build
npm --prefix streamlit_listview/frontend test
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel pytest e2e/test_features.py
```

Expected: all pass, 100 % frontend coverage.

### Task 2: Changelog, visual check, hero GIF and commit

**Files:**

- Modify: `CHANGELOG.md` (new `## [Unreleased]` section above `## [1.1.0]`, and the link `[Unreleased]: https://github.com/LelandGrunt/streamlit-listview/compare/v1.1.0...HEAD` above `[1.1.0]: …`)
- Maybe modify: `assets/listview-demo.gif`

- [ ] **Step 1: Write the *Fixed* entry**

It says: with `pin_search=True`, a listview narrower than about 270 px showed its search field past the frame's right border, and with `select_all` the toggle left the frame below about 360 px; the field now shrinks with the frame, as the unpinned field does.

- [ ] **Step 2: Record the after state and compare**

```sh
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --all --record bench-results/visual/after
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/compare.py bench-results/visual/before bench-results/visual/after
```

Expected: exit 0, or differences only where a pinned search or Select all sits in a frame narrower than about 360 px. Look at `report.html` for any difference.

- [ ] **Step 3: Regenerate the hero GIF**

Run: `LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py`, then `git status --short assets/`. Keep the file only if it changed.

- [ ] **Step 4: Run the remaining checks**

```sh
uv run --extra devel pytest tests/ --cov --cov-report=term-missing
pre-commit run --all-files
```

Expected: all pass.

- [ ] **Step 5: Commit the fix in one commit**

```sh
git add streamlit_listview/frontend/src/listview.css streamlit_listview/frontend/src/__tests__/listview-css.test.ts e2e/app_features.py e2e/conftest.py e2e/test_features.py CHANGELOG.md
git commit -m "fix(frontend): shrink the pinned search field with a narrow frame"
```

Add `assets/listview-demo.gif` only if Step 3 changed it.
