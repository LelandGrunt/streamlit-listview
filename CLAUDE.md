# CLAUDE.md

This file guides Claude Code (claude.ai/code) in this repository. It holds what every session needs. The detailed rules for one area live next to that area and load only when Claude works there (see *Where the detailed rules live*).

## What this is

`streamlit-listview` is a Streamlit **custom component** built on the **Components V2 API** (`st.components.v2.component`, Streamlit ≥ 1.51). A V2 component renders **inline** in the host page, inside a **Shadow DOM** (`isolate_styles=True`, Streamlit's default) that inherits Streamlit's `--st-*` theme variables. The legacy v1 API rendered into an iframe; none of it applies here. The widget is a selectable, scrollable list with single and multi selection, grouping, search, sorting, collapsible groups, `accept_new_options`, and Markdown labels and help.

The package has two languages: a thin Python wrapper (`streamlit_listview/`) and a React/TypeScript frontend (`streamlit_listview/frontend/`). Vite compiles the frontend into a bundle that the wrapper registers.

## Where the detailed rules live

A `CLAUDE.md` in a subdirectory loads the first time Claude reads, writes or edits a file in that directory. Claude never loads the last four entries on its own: read each one when the task touches its area, whether or not the user names it. Another coding assistant loads none of these files: it reads this file first, then the guide of each directory the task touches.

| File | Covers |
|---|---|
| `streamlit_listview/CLAUDE.md` | the Python wrapper: file map, parameter checks, id rules, row identity, new entries, the `format_func` contract |
| `streamlit_listview/frontend/CLAUDE.md` | the frontend: file map, shared helpers, selection state, groups, render chunks and row height, Markdown safety, the selectors that tests use |
| `.claude/rules/frontend-theming.md` | the stylesheet: theming, the sidebar swap, surface pairs, painted states; loads with the files its `paths` name |
| `demo/CLAUDE.md` | the demo: the widget key, presets and generated code, the theme switcher, deployment, the tour's labels |
| `.claude/skills/release/SKILL.md` | the release checklist (`/release`) |
| `BENCHMARKS.md` | the performance benchmarks: concept, how to run, compare and read them |
| `scripts/gif/README.md` | the README GIFs, the tour and the visual comparison |
| `HARNESS.md` | the quality harness: every check, the stages it runs at, the gaps |

## Commands

Always go through `uv`: the system `python` on `PATH` may lack this project's dependencies. The test and dev dependencies live in the `devel` extra, so `uv run pytest` fails; run `uv run --extra devel pytest`.

The commands run from the repository root unless their block names another directory. They use POSIX shell syntax, as Claude Code's Bash tool and CI do. PowerShell rejects the prefix `NAME=1 command`; set the variable for one command as `$env:NAME = "1"; command; Remove-Item Env:NAME`.

### Checks before each commit

```sh
uv tool install pre-commit                  # once per machine
pre-commit install --allow-missing-config   # once per clone; worktrees share the hook
pre-commit run --all-files                  # every check on every file, as CI runs it
pre-commit run ty --all-files               # a single hook
```

`.pre-commit-config.yaml` runs on every commit: ruff (`check --fix`, `format`) on the staged Python files, ty over the project, gitleaks over the staged changes and the history of `HEAD`, typos on every staged text file, markdownlint-cli2 on every staged Markdown file, and `uv audit` when `uv.lock` or `pyproject.toml` is staged. For staged files under `streamlit_listview/frontend/` it adds tsc and oxlint (`.ts`, `.tsx`, `.json`), Prettier (also `.css`) and `npm audit` (`package.json`, `package-lock.json`). These four need `npm ci` there first; without it, the `frontend-deps` hook stops the commit. `npm test` checks the rules of `listview.css` through `listview-css.test.ts`. The configuration lives in `[tool.ruff]`, `[tool.ty]` and `[tool.typos]` in the root `pyproject.toml`, in `.markdownlint-cli2.jsonc` and in `streamlit_listview/frontend/.oxlintrc.json`.

- **When a hook fails, fix the finding and commit again. Never pass `--no-verify`.** A ruff or typos fix leaves the file modified: stage it and commit again. The Prettier hook only checks: run `npm run format`, stage, and commit again. The markdownlint-cli2 hook only checks as well: fix the Markdown by hand.
- **Suppress a finding only on purpose, on the narrowest scope, with its reason:** `# noqa: CODE` or `# ty: ignore[rule]` on the line, or a per-file ignore in `pyproject.toml`; in the frontend, `// eslint-disable-next-line rule -- reason` (oxlint reads the ESLint syntax). An unused suppression fails the check; remove it when its finding goes away.
- **A secret that gitleaks reports stops the work.** Remove it, and rotate it if it left the machine. A false positive goes into `.gitleaksignore`: its fingerprint, below a comment that gives the reason. pre-commit builds gitleaks with Go on its first run; behind a proxy that breaks downloads from `proxy.golang.org`, run that first install as `GOPROXY=direct pre-commit run gitleaks --all-files`.
- **A function stays at a cyclomatic complexity of 10 or below** (ruff C901, oxlint `complexity`). A function above it when the limit came in carries a suppression with the reason; split it on the next change and remove the suppression.
- **Line endings:** a Windows checkout has CRLF endings, and Prettier (`endOfLine: auto`) fails a file with mixed endings. An append with Bash's `>>` writes LF lines, one with PowerShell 7's `>>` CRLF lines. `npx prettier --write <file>` in `streamlit_listview/frontend/` evens out one file; `npm run format` rewrites every frontend file.
- **`ruff format` also formats the `python` blocks in Markdown files.** `<!-- fmt:off -->` / `<!-- fmt:on -->` keeps the README's signature block aligned.
- **oxlint, not ESLint:** TypeScript 7 ships no JavaScript compiler API, which typescript-eslint needs.
- **A new directory of modules imported by name** (as `demo/` and `scripts/` are, through `sys.path` inserts) goes into both ty's `extra-paths` and ruff's `src`.
- **A commit that only deletes frontend files runs no frontend hook.** CI's `lint` job catches what the deletion breaks.

### Manual checks (before each release)

```sh
pre-commit run --hook-stage manual --all-files                        # every manual check
pre-commit run --hook-stage manual markdown-link-check --all-files    # one of them
```

These hooks need the network or their own browser, so no commit, CI run or push runs them: `markdown-link-check` checks the links of every Markdown file, `mermaid` renders every Mermaid diagram, and `e2e-browsers` runs the e2e suite in Firefox and WebKit. The release skill runs them before the tag.

### Tests

Python, gated at 100 % coverage over `streamlit_listview`, `demo`, `scripts/push_gate.py`, `scripts/verify_wheel.py`, `scripts/smoke_wheel.py` and `_build_backend.py` (except `demo/app.py`, which the e2e suite and the `AppTest` runs in `tests/test_demo_app.py` exercise):

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

From `streamlit_listview/frontend/`:

```sh
npm ci          # once per clone
npm run build   # clean + typecheck + production vite build -> frontend/build/
npm run dev     # vite build --watch
```

From the root:

```sh
uv pip install -e . --force-reinstall   # the build backend runs npm run build
uv build                                # wheel + sdist; also builds the frontend
```

**The bundle is gitignored.** `streamlit_listview/frontend/build/` is generated, and `git reset` never touches it. After editing anything under `frontend/src/`, run `npm run build` and restart Streamlit; a running app shows the old bundle until then.

**The in-tree build backend (`_build_backend.py`) runs `npm run build` for wheel, sdist and editable builds,** after `npm ci` when `node_modules` is missing; without npm on `PATH` it fails. With `LISTVIEW_SKIP_NPM_BUILD=1`, or without `frontend/src` (a wheel built from the sdist), it skips npm and packages the bundle in `build/`. It then fails unless `build/` holds exactly one `index-*.js` and one `index-*.css`. It cannot tell a stale bundle, so set the variable only when the bundle is current. Before a wheel build it deletes setuptools' staged copy in `build/lib`, which would otherwise ship files of an earlier build. When it cannot delete the copy, for example because another process holds one of its files open on Windows, the build stops and names the file.

### e2e (Playwright)

```sh
uv run --extra devel playwright install   # once
uv run --extra devel pytest e2e/
```

Each test module serves one Streamlit script through `e2e/e2e_utils.py::StreamlitRunner`: a harness app (`e2e/app*.py`), `demo/app.py` (the modules in `e2e/demo/`), `example.py`, or `e2e/perf/app_bench.py`. `e2e/conftest.py` boots one server per script, flags and environment and shares it across modules (`_servers`). A new harness for a module directly under `e2e/` needs an entry in `LISTVIEW_COUNTS` there. Every run needs a built bundle. `pytest e2e/` skips the browser-tier benchmark in `e2e/perf/` unless `--perf-out` is given.

CI's `e2e` job and the push gate run the suite in Chromium. `e2e/test_accessibility.py` loads axe-core from `streamlit_listview/frontend/node_modules`, so it needs `npm ci` there. Firefox and WebKit run by hand: `pre-commit run --hook-stage manual e2e-browsers --all-files` (`playwright install` above installs all three browsers). A test that holds only in some browsers carries `@pytest.mark.only_browser` or `@pytest.mark.skip_browser` with its reason.

### Performance benchmarks (not in CI; no thresholds)

**Read `BENCHMARKS.md` before running, changing or reading a benchmark.** Both tiers drive the component only through its public surface, so the same files benchmark any checkout.

- **Frontend tier** (vitest `bench` in jsdom, `frontend/src/bench/`): `npm run bench` in `streamlit_listview/frontend/`, for React-side A/B work. It runs React's development build, so its numbers are relative.
- **Browser tier** (Playwright against a real Streamlit server, `e2e/perf/`): `uv run --extra devel pytest e2e/perf/ --perf-out bench-results/<label>.jsonl`, summarized by `uv run --extra devel python -m e2e.perf.report bench-results/<label>.jsonl`, or compared with a second results file given after it. It gives the numbers of record, and only it can judge DOM-size or CSS work. It measures the checkout it runs from.
- **A delta inside the spread is not a result.** Results go to the gitignored `bench-results/` and are never committed: the numbers are machine-specific. The only gated performance check is `e2e/test_performance.py`.

### Visual comparison (not in CI; one machine only)

The GIF scenarios in `scripts/gif/` double as a before/after check of the widget's look: record every scenario before and after the change, building the bundle before each recording, and compare the two with `scripts/gif/compare.py`. `scripts/gif/README.md` (*Compare before and after a change*) gives the commands. A difference is not a failure: an intended change reports too, and a person judges `report.html`. Fonts and the Chromium version change pixels, so compare only recordings from one machine, and never commit them.

### Run the demo

```sh
uv run --extra devel streamlit run demo/app.py   # needs the package installed and a built bundle
```

## Architecture

**Python wrapper.** `streamlit_listview/__init__.py` declares the component at import time (`js="index-*.js"`, `css="index-*.css"`) and defines `listview(...)`. It validates the parameters, normalizes the options, ships a `data` dict to the frontend, and maps the returned ids back to the original Python objects. `_options.py` holds the option rules. The nested `streamlit_listview/pyproject.toml` ships in the wheel as the component manifest. Its `name`, `streamlit_listview`, must equal the distribution name `streamlit-listview` after PEP 503 normalization, and it prefixes the component key `streamlit_listview.listview`.

**Frontend.** `index.tsx` is the V2 `FrontendRenderer` entry and mounts one React root per instance. `Listview.tsx` composes the hooks (`hooks/`) and the presentational components (`components/`). `utils/` holds the shared helpers. `components/Markdown.tsx` renders Markdown as Streamlit does, with the plugins in `markdown/`; it escapes raw HTML and shows LaTeX as literal text.

### Invariants that span both languages

- **Five rules exist in both languages; change both copies together.** Row identity: the frontend keys rows by `idKey` (`utils/ids.ts`, JavaScript `String(id)`), and Python mirrors it with `_id_key` (`_options.py`). Every question about row identity goes through one of the two; never write a second `String(id)` or `str(id)` for it. The canonical-integer rule for new entries: `_parse_new_int_id` and `parseNewIntId`, which both suites test with the same input table. The block a row renders in: `blockKeyOf` (`utils/blocks.ts`) puts a group named like `ungrouped_label` into the block without a group, and `sort_items` sorts the two as one block. The row of a new entry with dict options: `newOptionRow` (`hooks/useNewOptionRows.ts`) and `_new_entry` (`_options.py`) both build it from the id, labeled with the id as text. The fifth rule, the reconciliation of the selection, follows below.
- **Ids are `str` or `int`** (never `bool`), an `int` id satisfies `abs(id) <= 2**53 - 1`, and ids are unique as rendered. The JSON boundary and JavaScript's `String()` set these limits. A subclass, such as an enum member, is keyed by the plain value JSON carries, not by its own `str()`.
- **Selection state lives on the frontend.** `useSelection` holds the selected ids as React state and seeds them once, at mount: from `data.state_selection` (the persisted `st.session_state[key]` of a keyed instance) when present, else from `data.default_ids` (the `default` that `listview()` resolved). A later change to either seeds nothing. A value under the key that is not a listview's state raises `ValueError` in `listview()`: the component would return it while the rows showed `default`.
- **A reconciliation fires `on_change` once, on purpose.** When a rerun's payload invalidates the selection (a keyed caller shrinks `options`, lowers `max_selections` or switches `selection_mode`), `useSelection` corrects it and commits the correction through `setStateValue("selection", …)`. The V2 layer cannot tell that commit from a click. Do not suppress the write-back, and do not use `setTriggerValue`: it fires and forgets, it does not persist. `_options.map_selection` applies the same corrections on the way out, with the same survivors, so the returned value never waits for the write-back. Change one, change the other.
- **A keyed widget keeps its selection while Streamlit keeps its state; a new `key` resets it on purpose.** A keyed instance keeps its selection and its UI state (collapse, search, scroll) across parameter changes; an unkeyed instance remounts on any parameter change. A run that does not call `listview()` for the key ends with Streamlit deleting the widget's state, as for its own widgets, and the next call mounts it from `default`; the demo's former lazy tabs lost the selection this way (`demo/CLAUDE.md`). A move between `st.sidebar` and the main body remounts the frontend: the selection survives through `state_selection`, and the UI state resets. `default` fires no `on_change`: it sets the V2 mount state, which `listview()` returns until the first commit.
- **The bundle is a single chunk.** Vite emits exactly one `index-[hash].js` and one `index-[hash].css`, and each Python glob requires exactly one match. Never add a dynamic `import()`: it splits off a second chunk and breaks registration. For this reason `remark-emoji` is imported statically.
- **The GIF scenarios, the tour and the e2e suite find the widget by its `data-testid`s and `listview-*` classes, and the demo by its labels.** Before you rename one, search `e2e/` and `scripts/gif/` for it, and fix every use in the same change.

## CI (`.github/workflows/ci.yml`)

Three jobs run in parallel on every pull request and push to `main`; a push to `main` adds a fourth. `lint` runs `uvx pre-commit run --all-files --show-diff-on-failure`. `test-build-verify` runs, in order: `npm ci`, `npm run build`, `npm test`, an editable install with `LISTVIEW_SKIP_NPM_BUILD=1` (`uv pip install`, which takes the newest Python dependencies that `pyproject.toml` admits, not `uv.lock`), `pytest tests/` with the coverage gate, a wheel build from a clean bundle, `scripts/verify_wheel.py` and `scripts/smoke_wheel.py`. `verify_wheel.py` checks the wheel's contents: under `frontend/build/` exactly one `index-*.js`, one `index-*.css` and `THIRD_PARTY_LICENSES.md` (the licenses of the bundled npm packages), and nothing else there; no other package file that the source tree lacks, and every module and `py.typed` that it holds; the manifest, parsed as Streamlit parses it; the license files; and no `_build_backend.py`. It also checks that the file name carries the version of the root `pyproject.toml`. `smoke_wheel.py` installs the wheel into a new virtual environment and renders a listview there through Streamlit's `AppTest`, which finds the component and resolves its bundle as a server does. `push-gate` runs on a push to `main` only: `python3 scripts/push_gate.py check main` checks the version information and the release state (see *Pushing to GitHub*). `e2e` builds the bundle, installs the package and Chromium, and runs `pytest e2e/`; the push gate runs the same suite. `release.yml` calls this workflow (`workflow_call`) on a release tag and publishes only when its jobs pass; `push-gate` skips that run, because `check tag` covers the tag. **The build must precede `npm test`** (see *Tests*). Actions are referenced by version tag, not by SHA, on purpose.

## Releasing

A `v*.*.*` tag pushed to GitHub publishes to PyPI through Trusted Publishing (`.github/workflows/release.yml`). **Cut a release with the `release` skill** (`.claude/skills/release/SKILL.md`). Five files assert the version, and `uv.lock` and `CHANGELOG.md` must agree with them; the release job fails when one of the seven disagrees. The order of the pushes matters.

### Pushing to GitHub

GitHub `main` shows released code only: Streamlit Community Cloud runs the hosted demo from it and installs the version that `demo/requirements.txt` pins from PyPI. A pre-push hook, `scripts/push_gate.py`, checks every push to a remote URL that contains `github.com`, in four stages: the refs (only `main` and a new tag `v<version>`), the local state (a command-line confirmation that names the version, a clean tree, the seven version files in agreement), the release order (the tag, then the PyPI release, then `main`), and CI's suite on the pushed commit, which needs npm, uv and uvx on `PATH`. `HARNESS.md` (*The push gate*) describes each stage. **`main` must carry the library code of its release tag,** so between releases GitHub `main` takes no change to the shipped package; docs, tests, the demo and the scripts may change. CI's `push-gate` job and `release.yml` repeat the version and release checks on GitHub.

```sh
uv run --no-project python scripts/push_gate.py install       # once per clone; the worktrees share the hook
git branch --set-upstream-to=azure/main main                  # in a clone with an Azure DevOps remote `azure`
git -c listview.pushGithub=<version> push origin v<version>   # then the same for main, once PyPI serves the version
```

- **Never pass `--no-verify`.** CI reports such a push on `main`, but by then the commit is public. On a tag, `release.yml` runs CI's jobs and publishes only when they pass.
- **`git push --dry-run` runs the hook and sends nothing.** Use it to see what the gate says.
- **The suite runs once per commit.** `.git/push-gate/passed` lists the commits that passed; delete the file to force a new run.

## Docs

`README.md` documents the public API, `demo/README.md` the playground, `CHANGELOG.md` the user-visible changes per release (Keep a Changelog format), `BENCHMARKS.md` the benchmarks, and `HARNESS.md` the quality checks. Update `BENCHMARKS.md` when a benchmark tier changes, and `HARNESS.md` when a check is added, removed or moved to another stage.

**Writing rule: every technical document in this repository (`README.md`, `demo/README.md`, `CHANGELOG.md`, `BENCHMARKS.md`, `HARNESS.md`, every `CLAUDE.md`, every rule under `.claude/rules/` and every skill under `.claude/skills/`) follows plain English according to Strunk & White, *The Elements of Style*.** In practice: short sentences with one idea each; the active voice; statements in positive form (say what the code does, not what it no longer does); definite, concrete words and the measured number rather than "fast" or "large"; omit needless words and qualifiers ("very", "really", "simply"); parallel form for coordinate items (table columns, bullet lists, the halves of a comparison); no colloquialisms or metaphors the reader must decode ("under the hood", "canaries" without a gloss); jargon defined for the document's audience — a changelog reader is a Python user, not a React developer. Why: users and coding agents read these files in every session, so a sentence that has to be read twice costs everyone, and a vague one leads to a wrong change. Review a draft against this rule before committing it.

**Keep the `CLAUDE.md` files short.** Claude loads them into every session that touches their directory. A rule goes into the `CLAUDE.md` of the directory it concerns; only a rule that spans directories goes into this file. A long set of rules that only some files need goes into `.claude/rules/`, with `paths` that name those files. State the rule and the one reason a reader needs to keep it. Measurements, dates and the history of a fix belong in the commit message, in `BENCHMARKS.md` or in a comment next to the code.

### README GIFs (`assets/*.gif`)

**Regenerate the hero GIF (`assets/listview-demo.gif`) in the same commit as any change to how the widget looks or behaves.** The PyPI pages of 1.0.0 and 1.0.1 link it at `HEAD`, so a style change merged without a new GIF advertises a widget the code no longer renders. The rule covers `listview.css`, the markup in `Listview.tsx` and `components/`, the Markdown renderer, any hook whose effect the user sees, a Python default that changes rendering, and `scripts/gif/` itself. A refactor, a performance change or a test change needs no new GIF.

- **Build first.** `scripts/gif/generate.py` (the hero) and `scripts/gif/screencast.py` (the tour) capture the bundle in `frontend/build/`; a stale bundle yields a GIF of the old widget. `scripts/gif/README.md` gives the commands and covers the scenarios.
- **Commit the hero GIF only when its frames show a real change.** On one machine an unchanged widget yields a byte-identical file. Another machine's fonts or a newer Chromium change pixels too.
- **The tour** (`assets/listview-tour.gif`) differs on every run. Regenerate it when the demo changes visibly and with every version bump, because it shows the version badge.
- **Never launch the tour's Chromium with `--use-fake-ui-for-media-stream`:** that flag records the whole monitor, not the demo's tab.

## Components V2 references

This repo hand-rolls the V2 stack. The official docs help to cross-check boilerplate (registration, the `FrontendRenderer` contract, packaging) but say nothing about this repo's invariants; for those, read the `CLAUDE.md` files, and check SDK behavior against the docs of the installed Streamlit version. When a guide, the code and the tests disagree, report the conflict and settle the intended behavior with the user before you edit. **Most search hits still describe the legacy v1 iframe API.** `declare_component`, `Streamlit.setComponentValue`, `withStreamlitConnection`, `streamlit-component-lib` and a frontend dev server on `:3001` mark v1 material; ignore it.

- **V2 concepts** (registration, state vs. triggers, theming): <https://docs.streamlit.io/develop/concepts/custom-components/components-v2>. `setStateValue` persists state; `setTriggerValue` fires and forgets.
- **API reference:** <https://docs.streamlit.io/develop/api-reference/custom-components>. `index.tsx` implements the `FrontendRenderer` type from the npm package `@streamlit/component-v2-lib` and takes `FrontendRendererArgs` from it; `ListviewState` in `types.ts` satisfies its `FrontendState`.
- **React + TypeScript tutorial** (V2 as of 2026-06): <https://docs.streamlit.io/develop/tutorials/custom-components/template-react>.
- **Official template:** <https://github.com/streamlit/component-template>. Only `templates/v2/` applies.
