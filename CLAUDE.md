# CLAUDE.md

This file guides Claude Code (claude.ai/code) in this repository. It holds what every session needs. The detailed rules for one area live next to that area and load only when Claude works there (see *Where the detailed rules live*).

## What this is

`streamlit-listview` is a Streamlit **custom component** built on the **Components V2 API** (`st.components.v2.component`, Streamlit ≥ 1.51). A V2 component renders **inline** in the host page, inside a **Shadow DOM** (`isolate_styles=True`) that inherits Streamlit's `--st-*` theme variables. The legacy v1 API rendered into an iframe; none of it applies here. The widget is a selectable, scrollable list with single and multi selection, grouping, search, sorting, collapsible groups, `accept_new_options`, and Markdown labels and help.

The package has two languages: a thin Python wrapper (`streamlit_listview/`) and a React/TypeScript frontend (`streamlit_listview/frontend/`). Vite compiles the frontend into a bundle that the wrapper registers.

## Where the detailed rules live

A `CLAUDE.md` in a subdirectory loads when Claude reads a file in that directory. The last three entries load only on request: read them before working in their area.

| File | Covers |
|---|---|
| `streamlit_listview/CLAUDE.md` | the Python wrapper: id rules, row identity, new entries, the `format_func` contract |
| `streamlit_listview/frontend/CLAUDE.md` | the frontend: file map, selection state, render chunks and row height, theming, the sidebar swap, surface pairs, painted states, the `data-testid`s |
| `demo/CLAUDE.md` | the demo: the widget key, the theme switcher |
| `.claude/skills/release/SKILL.md` | the release checklist (`/release`) |
| `BENCHMARKS.md` | the performance benchmarks: concept, how to run, compare and read them |
| `scripts/gif/README.md` | the README GIFs, the tour and the visual comparison |

## Commands

Always go through `uv`: the system `python` on `PATH` may lack this project's dependencies. The test and dev dependencies live in the `devel` extra, so `uv run pytest` fails; run `uv run --extra devel pytest`.

### Checks before each commit
```sh
uv tool install pre-commit                  # once per machine
pre-commit install --allow-missing-config   # once per clone; worktrees share the hook
pre-commit run --all-files                  # every check on every file, as CI runs it
pre-commit run ty --all-files               # a single hook
```
`.pre-commit-config.yaml` runs ruff (`check --fix` and `format`) on the staged Python files and ty over the whole project on every commit, and `uv audit` when `uv.lock` or `pyproject.toml` is staged. It runs tsc, oxlint, Prettier and `npm audit` only when a file under `streamlit_listview/frontend/` is staged; these four need `npm ci` there first. The configuration lives in `[tool.ruff]` and `[tool.ty]` in the root `pyproject.toml` and in `streamlit_listview/frontend/.oxlintrc.json`.
- **When a hook fails, fix the finding and commit again. Never pass `--no-verify`.** A ruff fix leaves the file modified: stage it and commit again. The Prettier hook only checks: run `npm run format`, stage, and commit again.
- **Suppress a finding only on purpose, on the narrowest scope, with its reason:** `# noqa: CODE` or `# ty: ignore[rule]` on the line, or a per-file ignore in `pyproject.toml`; in the frontend, `// eslint-disable-next-line rule -- reason` (oxlint reads the ESLint syntax). An unused suppression fails the check; remove it when its finding goes away.
- **Line endings:** a Windows checkout has CRLF endings, and Prettier (`endOfLine: auto`) fails a file with mixed endings. A shell `>>` append writes LF into a CRLF file; `npm run format` evens it out.
- **`ruff format` also formats the `python` blocks in Markdown files.** `<!-- fmt:off -->` / `<!-- fmt:on -->` keeps the README's signature block aligned.
- **oxlint, not ESLint:** TypeScript 7 ships no JavaScript compiler API, which typescript-eslint needs.
- **A new directory of modules imported by name** (as `demo/` and `scripts/` are, through `sys.path` inserts) goes into both ty's `extra-paths` and ruff's `src`.
- **A commit that only deletes frontend files runs no frontend hook.** CI's `lint` job catches what the deletion breaks.

### Tests
Python, gated at 100 % coverage over `streamlit_listview` and `demo` (except `demo/app.py`, which the e2e suite exercises):
```sh
uv run --extra devel pytest tests/                                   # the unit suite
uv run --extra devel pytest tests/ --cov --cov-report=term-missing   # with the coverage gate
uv run --extra devel pytest tests/test_listview.py::test_name        # one test
```
Frontend, from `streamlit_listview/frontend/`; `npm test` itself enforces 100 % statements, branches, functions and lines:
```sh
npm run build && npm test              # what CI runs: build FIRST
npx vitest run src/Listview.test.tsx   # one test file
npm run coverage                       # the coverage gate without the typecheck
npm run typecheck                      # tsc --noEmit over the app code
npm run typecheck:all                  # tsc over the app code and the tests (the pre-commit hook)
npm run lint                           # oxlint
npm run format                         # prettier --write
npm run format:check                   # prettier --check (the pre-commit hook)
```
**`npm test` needs a built bundle.** `src/__tests__/single-file-build.test.ts` asserts on the gitignored `build/` directory and fails with `ENOENT … scandir '…/frontend/build'` without it. `npm run build` empties `build/` first, so the test always sees the bundle of the current sources. Mark an unreachable defensive guard with `/* v8 ignore */`.

### Build and install
```sh
npm ci                                  # once, in streamlit_listview/frontend/
npm run build                           # clean + typecheck + production vite build -> frontend/build/
npm run dev                             # vite build --watch
uv pip install -e . --force-reinstall   # from the root; the build backend runs npm run build
uv build                                # wheel + sdist; also builds the frontend
```
`LISTVIEW_SKIP_NPM_BUILD=1` skips the npm step when the bundle is current.

**The bundle is gitignored.** `streamlit_listview/frontend/build/` is generated, and `git reset` never touches it. After editing anything under `frontend/src/`, run `npm run build` and restart Streamlit; a running app shows the old bundle until then. The in-tree build backend (`_build_backend.py`) runs `npm run build` for wheel, sdist and editable builds, and fails when the bundle is missing.

### e2e (Playwright; not in CI)
```sh
uv run --extra devel playwright install   # once
uv run --extra devel pytest e2e/
```
Each test starts a Streamlit subprocess (`e2e/e2e_utils.py::StreamlitRunner`) on a harness app (`e2e/app.py`, `app_features.py`, `app_performance.py`) and needs a built bundle. `pytest e2e/` skips the browser-tier benchmark in `e2e/perf/`.

### Performance benchmarks (not in CI; no thresholds)
**Read `BENCHMARKS.md` before running, changing or reading a benchmark.** Both tiers drive the component only through its public surface, so the same files benchmark any checkout. The full matrix takes about 27 minutes in the frontend tier and 28 in the browser tier.
- **Frontend tier** (vitest `bench` in jsdom, `frontend/src/bench/`): `npm run bench`, for React-side A/B work. It runs React's development build, so its numbers are relative.
- **Browser tier** (Playwright against a real Streamlit server, `e2e/perf/`): `uv run --extra devel pytest e2e/perf/ --perf-out bench-results/<label>.jsonl`, summarized by `uv run --extra devel python -m e2e.perf.report`. It gives the numbers of record, and only it can judge DOM-size or CSS work. It measures the checkout it runs from.
- **A delta inside the spread is not a result.** Results go to the gitignored `bench-results/` and are never committed: the numbers are machine-specific. The only gated performance check is `e2e/test_performance.py`.

### Visual comparison (not in CI; one machine only)
The README GIF scenarios double as a before/after check of the widget's look. Build the bundle before each recording:
```sh
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --all --record bench-results/visual/before
# change the widget, run npm run build, then:
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --all --record bench-results/visual/after
uv run --extra devel python scripts/gif/compare.py bench-results/visual/before bench-results/visual/after   # exit 0 same, 1 differs, 2 invalid input
```
A difference is not a failure: an intended change reports too, and a person judges `report.html`. Fonts and the Chromium version change pixels, so compare only recordings from one machine, and never commit them.

### Run the demo
```sh
uv run --extra devel streamlit run demo/app.py   # needs the package installed and a built bundle
```

## Architecture

**Python wrapper.** `streamlit_listview/__init__.py` declares the component at import time (`js="index-*.js"`, `css="index-*.css"`) and defines `listview(...)`. It validates the parameters, normalizes the options, ships a `data` dict to the frontend, and maps the returned ids back to the original Python objects. `_options.py` holds the option rules. The nested `streamlit_listview/pyproject.toml` ships in the wheel as the component manifest; its `name` must match the distribution name.

**Frontend.** `index.tsx` is the V2 `FrontendRenderer` entry and mounts one React root per instance. `Listview.tsx` composes the hooks (`hooks/`) and the presentational components (`components/`). `utils/` holds the shared helpers, and `markdown/` renders Markdown as Streamlit does, without raw HTML or LaTeX.

### Invariants that span both languages

- **Two rules exist in both languages; change both copies together.** Row identity: the frontend keys rows by `idKey` (`utils/ids.ts`, JavaScript `String(id)`), and Python mirrors it with `_id_key` (`_options.py`). Every question about row identity goes through one of the two; never write a second `String(id)` or `str(id)` for it. The canonical-integer rule for new entries: `_parse_new_int_id` and `parseNewIntId`, which both suites test with the same input table.
- **Ids are exactly `str` or `int`** (never `bool`), an `int` id satisfies `abs(id) <= 2**53 - 1`, and ids are unique as rendered. The JSON boundary and JavaScript's `String()` set these limits.
- **Selection state lives on the frontend.** `useSelection` holds the selected ids as React state and seeds them once, at mount: from `data.state_selection` (the persisted `st.session_state[key]` of a keyed instance) when present, else from `default`. A later change to either seeds nothing.
- **A reconciliation fires `on_change` once, on purpose.** When a rerun's payload invalidates the selection (a keyed caller shrinks `options`, lowers `max_selections` or switches `selection_mode`), `useSelection` corrects it and commits the correction through `setStateValue("selection", …)`. The V2 layer cannot tell that commit from a click. Do not suppress the write-back, and do not use `setTriggerValue`: it fires and forgets, it does not persist. `_options.map_selection` applies the same corrections on the way out, with the same survivors, so the returned value never waits for the write-back. Change one, change the other.
- **Only a new `key` resets the widget.** A keyed instance keeps its selection and its UI state (collapse, search, scroll) across parameter changes; an unkeyed instance remounts on any parameter change. `default` never commits a value.
- **The bundle is a single chunk.** Vite emits exactly one `index-[hash].js` and one `index-[hash].css`, and each Python glob requires exactly one match. Never add a dynamic `import()`: it splits off a second chunk and breaks registration. For this reason `remark-emoji` is imported statically and KaTeX is gone.
- **CSS reads Streamlit's `--st-*` variables only**, with fallbacks. Never use `prefers-color-scheme` or `light-dark()`: lightningcss rewrites them so that they miss the shadow tree.
- **The GIF scenarios, the tour and the e2e suite find the widget by its `data-testid`s and the demo by its labels.** A rename breaks them; fix them in the same change.

## CI (`.github/workflows/ci.yml`)
Three jobs run in parallel. `lint` runs `uvx pre-commit run --all-files --show-diff-on-failure`. `test-build-verify` runs, in order: `npm ci`, `npm run build`, `npm test`, an editable install with `LISTVIEW_SKIP_NPM_BUILD=1`, `pytest tests/` with the coverage gate, a wheel build from a clean bundle, and `scripts/verify_wheel.py`. That script checks that the wheel ships exactly one `index-*.js` and one `index-*.css` under `frontend/build/`, plus the manifest and the license files. `push-gate` runs on a push to `main` only: `python3 scripts/push_gate.py check main` checks the version information and the release state (see *Pushing to GitHub*). **The build must precede `npm test`** (see *Tests*). The e2e suite does not run in CI. Actions are referenced by version tag, not by SHA, on purpose.

## Releasing
A `v*.*.*` tag pushed to GitHub publishes to PyPI through Trusted Publishing (`.github/workflows/release.yml`). **Cut a release with the `release` skill** (`.claude/skills/release/SKILL.md`): five files assert the version, the release job fails when one disagrees, and the order of the pushes matters.

### Pushing to GitHub
GitHub `main` shows released code only: Streamlit Community Cloud runs the hosted demo from it and installs the version that `demo/requirements.txt` pins from PyPI. A pre-push hook, `scripts/push_gate.py`, refuses every push to GitHub except `main` and `v*` tags. It lets those pass only with a command-line confirmation that names the version, consistent version information, a changelog without "Unreleased", the release order (the tag, then the PyPI release, then `main`), and a passing CI suite on the pushed commit, which must be `HEAD` of a clean tree. CI's `push-gate` job and `release.yml` repeat the version checks on GitHub.
```sh
uv run --no-project python scripts/push_gate.py install       # once per clone; the worktrees share the hook
git branch --set-upstream-to=azure/main main                  # in a clone with an Azure DevOps remote `azure`
git -c listview.pushGithub=<version> push origin v<version>   # then the same for main, once PyPI serves the version
```
- **Never pass `--no-verify`.** CI reports such a push on `main`, but by then the commit is public.
- **`git push --dry-run` runs the hook and sends nothing.** Use it to see what the gate says.
- **The suite runs once per commit.** `.git/push-gate/passed` lists the commits that passed; delete the file to force a new run.

## Docs
`README.md` documents the public API, `demo/README.md` the playground, `CHANGELOG.md` the user-visible changes per release (Keep a Changelog format), and `BENCHMARKS.md` the benchmarks. Update `BENCHMARKS.md` when a benchmark tier changes.

**Writing rule: every technical document in this repository (`README.md`, `demo/README.md`, `CHANGELOG.md`, `BENCHMARKS.md`, every `CLAUDE.md` and every skill under `.claude/skills/`) follows plain English according to Strunk & White, *The Elements of Style*.** In practice: short sentences with one idea each; the active voice; statements in positive form (say what the code does, not what it no longer does); definite, concrete words and the measured number rather than "fast" or "large"; omit needless words and qualifiers ("very", "really", "simply"); parallel form for coordinate items (table columns, bullet lists, the halves of a comparison); no colloquialisms or metaphors the reader must decode ("under the hood", "canaries" without a gloss); jargon defined for the document's audience — a changelog reader is a Python user, not a React developer. Why: users and coding agents read these files in every session, so a sentence that has to be read twice costs everyone, and a vague one leads to a wrong change. Review a draft against this rule before committing it.

**Keep the `CLAUDE.md` files short.** Claude loads them into every session that touches their directory. A rule goes into the `CLAUDE.md` of the directory it concerns; only a rule that spans directories goes into this file. State the rule and the one reason a reader needs to keep it. Measurements, dates and the history of a fix belong in the commit message, in `BENCHMARKS.md` or in a comment next to the code.

### README GIFs (`assets/*.gif`)
**Regenerate the gallery GIFs in the same commit as any change to how the widget looks or behaves.** The README links each GIF at `HEAD`, so a style change merged without new GIFs advertises a widget the code no longer renders. The rule covers `listview.css`, the markup in `Listview.tsx` and `components/`, the Markdown renderer, any hook whose effect the user sees, a Python default that changes rendering, and `scripts/gif/` itself. A refactor, a performance change or a test change needs no new GIF.
```sh
npm --prefix streamlit_listview/frontend run build
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --gallery             # every gallery GIF
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --scenario keyboard   # one GIF
```
- **Build first.** The generator captures the bundle in `frontend/build/`; a stale bundle yields GIFs of the old widget.
- **Commit a GIF only when its frames show a real change.** On one machine an unchanged widget yields byte-identical files. Another machine's fonts or a newer Chromium change pixels too.
- **The tour** (`assets/listview-tour.gif`) differs on every run. Regenerate it when the demo changes visibly and with every version bump, because it shows the version badge.
- **Never launch the tour's Chromium with `--use-fake-ui-for-media-stream`:** that flag records the whole monitor, not the demo's tab.

`scripts/gif/README.md` covers the scenarios, the tour and how to add a scenario.

## Components V2 references
This repo hand-rolls the V2 stack. The official docs help to cross-check boilerplate (registration, the `FrontendRenderer` contract, packaging) but say nothing about this repo's invariants; for those, trust the `CLAUDE.md` files. **Most search hits still describe the legacy v1 iframe API.** `declare_component`, `Streamlit.setComponentValue`, `withStreamlitConnection`, `streamlit-component-lib` and a frontend dev server on `:3001` mark v1 material; ignore it.
- **V2 concepts** (registration, state vs. triggers, theming): <https://docs.streamlit.io/develop/concepts/custom-components/components-v2>. `setStateValue` persists state; `setTriggerValue` fires and forgets.
- **API reference:** <https://docs.streamlit.io/develop/api-reference/custom-components>. The frontend types `index.tsx` implements (`FrontendRenderer`, `FrontendRendererArgs`, `FrontendState`, `CleanupFunction`) come from the npm package `@streamlit/component-v2-lib`.
- **React + TypeScript tutorial** (V2 as of 2026-06): <https://docs.streamlit.io/develop/tutorials/custom-components/template-react>.
- **Official template:** <https://github.com/streamlit/component-template>. Only `templates/v2/` applies.
