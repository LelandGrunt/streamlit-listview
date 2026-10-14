# Performance benchmarks

How to run the listview's performance benchmarks, compare two versions of the component, and read the results. The benchmarks answer three questions:

1. **Does a change make the listview faster or slower?** Run before and after, then compare.
2. **Which of two implementations is faster?** Run each, then compare.
3. **How fast is it?** Absolute numbers per list size, scenario and metric, for documentation and design decisions.

They are tooling for maintainers: CI does not run them, they enforce no thresholds, and the wheel ships none of them.

**Contents:** [Quick start](#quick-start) · [Test concept](#test-concept) · [Methodology](#methodology) · [Prerequisites](#prerequisites) · [Running the frontend tier](#running-the-frontend-tier) · [Running the browser tier](#running-the-browser-tier) · [Comparing two versions](#comparing-two-versions) · [Reading the results](#reading-the-results) · [Worked example](#worked-example-main-vs-the-render-chunk-branch) · [Reference run](#reference-run-100-to-100000-rows) · [Troubleshooting](#troubleshooting) · [Extending the benchmarks](#extending-the-benchmarks) · [File map](#file-map)

---

## Quick start

From a clone with the frontend built (`npm ci && npm run build` in `streamlit_listview/frontend/`) and the development environment installed (`uv run --extra devel playwright install chromium` once):

```sh
# Frontend tier: React-only, relative numbers (~25 min for everything)
cd streamlit_listview/frontend
LISTVIEW_BENCH_SIZES=1000,50000 npm run bench

# Browser tier: real Chromium + Streamlit, numbers of record (~24 min for everything)
cd ../..
uv run --extra devel pytest e2e/perf/ --perf-out bench-results/quick.jsonl --perf-sizes 1000,50000 --perf-reps 1
uv run --extra devel python -m e2e.perf.report bench-results/quick.jsonl
```

PowerShell sets environment variables differently: `$env:LISTVIEW_BENCH_SIZES = "1000,50000"; npm run bench` (the variable then stays set for the session; clear it with `Remove-Item Env:LISTVIEW_BENCH_SIZES`).

---

## Test concept

### Where the benchmarks sit

| Layer | What it proves | Runs in CI | Gate |
|---|---|---|---|
| Python unit tests (`tests/`) | the wrapper's behavior | yes | 100 % coverage |
| Frontend unit tests (`src/**/*.test.ts`, `*.test.tsx`) | the React component's behavior | yes | 100 % coverage |
| End-to-end tests (`e2e/`) | the component inside a real Streamlit app | yes, in Chromium | pass/fail |
| Performance tests (`e2e/test_performance.py`) | 5,000 rows render within 15 s of the page load; six more tests check responsiveness and the off-screen render chunks | yes, with the end-to-end tests | a 15 s budget; catches only gross regressions |
| **Performance benchmarks** (this document) | how fast, and whether a change helps | no: `pytest e2e/` collects and skips them | none: you read and compare numbers |

A slower result never fails a benchmark. A benchmark fails only when a scenario cannot run: a precondition does not hold, or a wait times out. Each scenario checks one or two rows that show its action took effect (see *Design principles*); the unit and end-to-end tests check the full result.

### Two tiers

| | Frontend tier | Browser tier |
|---|---|---|
| Runs in | `vitest bench` in Node, jsdom DOM, React development build | Playwright driving headless Chromium against a real Streamlit server |
| Measures | React's own work: reconciliation, memo recomputation, DOM mutation | what a user waits for once the page has loaded: Python call, payload transfer, parsing, React, style, layout, paint, scroll |
| Blind to | layout, paint, scroll, Streamlit's rerun round trip | network latency (the server runs on the same machine), the first page load, the browser's input handling (the scenarios click and scroll from a script), the moment the screen shows a frame |
| Use it for | quick A/B of React-side changes, many samples per scenario | the numbers you quote; DOM-size or CSS work; anything Streamlit-side |
| Full matrix | about 25 min on the reference machine, 13 of them in the three 100,000-row cells | about 24 min on the reference machine at 3 reps, 4 of them in the three 100,000-row cells |
| Results | vitest table, JSON through `--outputJson`, built-in `--compare` | JSONL records, `python -m e2e.perf.report` |
| Code | `streamlit_listview/frontend/src/bench/` | `e2e/perf/` |

**Why two tiers.** The frontend tier isolates the part of the cost the component's own code controls, so a React-side improvement appears at full size and with many samples. The browser tier adds everything around it. A fix can therefore look large in the frontend tier and smaller in the browser tier, and both readings are correct: the browser tier also contains the Python call, Streamlit's payload transfer and Chrome's work on a DOM of about 310,000 nodes at 100,000 rows, which React-side changes do not touch. Quote browser-tier numbers to users; use frontend-tier numbers to decide between code alternatives.

### The matrix

Every benchmark runs over the same cells:

- **Sizes:** 100, 1,000, 5,000, 10,000, 25,000, 50,000 and 100,000 options. The 100,000 cells match the largest size the demo offers. Every row stays in the DOM, so the mount and a rerun that sends the options grow with the rows, while the browser lays out and paints only the rows near the frame.
- **Shapes:** `grouped`, in groups of 100 with collapsible group headers; `ungrouped`; and `disabled`, which is `grouped` plus a `disabled` key on every row. In `disabled`, every tenth row is `true` (rows 5, 15, 25, …) and the rest are `false`. No row a scenario clicks, searches for or edits is disabled. The shape measures dict options that carry the key: the key adds 28 % to the payload, and the disabled rows take the component's disabled path.
- **Dataset:** generated by `demo/data.py::make_large_dataset` (id `item-00042`, label `Item 00042`, group `Batch 000`). `e2e/perf/cells.py::shape_rows` derives the other two shapes from it. The frontend tier uses a TypeScript mirror (`src/bench/fixtures.ts`) that unit tests pin to the same literals as the Python code, so both tiers measure identical rows. The five-digit numbers stay unique and in row order up to 100,000 rows (`item-99999`); unit tests in both languages pin that bound.
- **Widget configuration:** single selection, search enabled, height 300 px, collapsible groups in the `grouped` and `disabled` shapes. `add_option` also enables `accept_new_options`.

### Scenarios

| Scenario | What happens | What it exercises | Frontend | Browser |
|---|---|---|---|---|
| `mount` | render N rows from nothing until the last row exists | first render, DOM creation | render + unmount cycle | yes, timed from "show" |
| `rerun_unchanged` | rerun the app with the options unchanged | reuse of unchanged option objects, row memoization | yes, with fresh copies of the same options | yes, through an unrelated button: the first rerun after the mount, which sends the options again (see *Payload*) |
| `rerun_one_changed` | rerun the app with one option's label changed | re-rendering exactly one row | yes | yes |
| `search_narrow` / `search_clear` | type a query matching one row, then clear it | filtering; re-inserting N−1 rows | merged as `search_narrow_then_clear` | separately |
| `click_select` | click an unselected row | selection state; in the browser also the round trip to Python | yes | yes |
| `group_collapse` / `group_expand` | toggle the first group header (`grouped` and `disabled` only) | removing and re-inserting 100 rows | merged as `group_collapse_then_expand` | separately |
| `add_option` | type a new value and press Enter, with one row selected | building the added row, the "already in the list?" lookup | yes | yes, on its own page load |
| `scroll` | scroll through the list in 60 programmatic steps | frame time with the whole DOM | — | yes |

The frontend tier merges the two reset pairs because vitest's `bench()` has no per-iteration setup hook: every timed body must leave the list ready for its own next iteration. The browser tier measures the halves separately.

### Design principles

- **Public surface only.** Both tiers drive the component through its props and DOM (frontend) or the `listview()` API and the rendered page (browser). They import no internal helper, so the same benchmark files run unchanged against any version of the component. That lets you benchmark `main` against your branch.
- **Same machine, no stored baselines.** Absolute numbers depend on the machine, its load and its power settings. A comparison is always two runs on the same machine, close together in time. Results go to the gitignored `bench-results/`; never commit a baseline.
- **Fail loudly, never time a no-op.** Every scenario but `scroll` checks a DOM condition that shows its action took effect: the last row exists after the mount and after a rerun; the search hides the first row and keeps the last; clearing it brings the first row back; the header hides and restores the group's first row; the edited row shows its new label; a clicked row is selected; Enter adds a row. In the browser tier the two reruns and the click must also reach the app's status line. The frontend tier checks its conditions in the untimed setup, before the warm-up and before the measured run, not in every timed iteration; the browser tier makes the condition the end of the timed wait. A condition samples one or two rows. It shows that the action ran, not that every row is right: the unit and end-to-end tests check that. In the browser tier a wait inside the page fails after 240 s and a Playwright wait after 300 s; either fails that cell's test, and the other cells still run. An unknown size or shape in a filter stops the run, and so does a `--perf-reps` or `--perf-throttle` below 1: a run never shrinks the matrix silently or passes without writing a record.

---

## Methodology

### Frontend tier

- **Harness.** `vitest bench` (built on tinybench) in jsdom, rendering with `@testing-library/react`. One `describe` per cell (shape × size) and one `bench` per scenario.
- **Setup is untimed.** A bench's `setup` mounts the list, looks up the DOM elements the timed body needs, and checks the precondition. It runs once before the warm-up and once before the measured run; `teardown` unmounts and releases every cached handle, so 100,000-row trees do not accumulate in memory.
- **Self-resetting bodies.** `rerun_*` alternate between two pre-built fresh copies of the options, so every rerun hands the component new objects, as a rerun that sends the options does, and no JSON is built inside the timed body. `click_select` alternates between two rows; `add_option` commits a new unique value each time.
- **Sample budgets.** Without fixed sample counts, large cells would run for minutes:

  | Scenario group | ≤ 5,000 rows | 10,000 | 25,000 | 50,000 | 100,000 |
  |---|---|---|---|---|---|
  | `mount`, `search_narrow_then_clear` | tinybench default: ≥ 500 ms and ≥ 10 samples | 8 | 5 | 3 | 3 |
  | `rerun_*`, `click_select`, `group_collapse_then_expand` | tinybench default | 15 | 15 | 15 | 15 |
  | `add_option` | 10, fixed, because each added row stays in the list | 15 | 15 | 15 | 15 |

  A fixed count runs after one warm-up iteration, two for the sub-second scenarios; the warm-up does not count as a sample.
- **Positional pairing.** vitest's `--compare` matches benchmarks by the bench file's path and their position in it, not by name; a renamed or moved bench file pairs nothing. The bench file therefore declares every cell and skips the ones a filter leaves out (`describe.skipIf`), so a subset run still aligns with a full baseline, as long as both sides use the same bench file. The `disabled` shape comes last, so a baseline recorded before it existed still aligns with the `grouped` and `ungrouped` cells. A new size, by contrast, moves the cells of every later shape (see *Extending the benchmarks*).

### Browser tier

- **Harness.** pytest starts one Streamlit app (`e2e/perf/app_bench.py`) per session. The query string selects the cell (`?n=…&shape=…&newopt=…`). The list mounts only when the test clicks a "show" button, so the test times the mount itself. A "rerun" button causes an unrelated rerun; an "edit" button flips one option's label. The listview has a `key` (`bench`), as a listview in a dynamic app should.
- **Fresh state per run.** Each measured run opens two new browser contexts (new Streamlit sessions, viewport 1280×900): one for the main scenarios, and one for `add_option`, which needs `accept_new_options`. The first run of each cell is a warm-up and is discarded. The next `--perf-reps` runs (default 3) each write one JSON line.
- **Timing inside the page.** Each scenario is a JavaScript snippet that starts `performance.now()`, performs the action, and waits frame by frame for the DOM condition: `rows_ms`. It then waits one animation frame plus a macrotask: `painted_ms`. By then the main thread has rendered that frame. The page cannot see when the screen shows it, so `painted_ms` marks the end of the main thread's work, not the moment the pixels appear. Doing this in the page avoids a Playwright round trip per check, which at this scale would be the measurement.
- **Main-thread work.** Chrome DevTools Protocol `Performance.getMetrics` snapshots around a scenario show how long the main thread was busy: `task_ms`, split into `script_ms`, `recalcstyle_ms` and `layout_ms`. For `mount` the window opens only after the page has settled, so page loading is excluded. The windows include fixed pauses that let trailing work finish (1,200 ms after the mount, 500 ms after the search, 1,500 ms after each rerun or click), so `task_ms` also counts that trailing work.
- **Two end points for round trips.** `rerun_unchanged`, `rerun_one_changed` and `click_select` go through Python. `roundtrip_ms` ends one painted frame after the app's status line shows the rerun; for `rerun_one_changed` the edited row must also show its new label, and for `click_select` the status line must echo the selection. The component may re-render after that, so `settled_ms` also waits until the main thread has had no long task (≥ 50 ms, through `PerformanceObserver('longtask')`) for 300 ms. Shorter tasks are invisible to it. It reports the later of the round trip's end and the last long task's end, so without a trailing long task it equals `roundtrip_ms`. Use `settled_ms` or `task_ms` to see the frontend's share. A scenario that calls `settled()` must start `watchLongTasks()` before its action.
- **Payload.** `ws_bytes` sums the payload lengths of the WebSocket frames the page receives during the mount and during `rerun_unchanged`, without frame headers. The benchmark server starts with `--server.enableWebsocketCompression=false` (`EXTRA_ARGS` in `test_bench.py`). The flag outranks `config.toml` and the `STREAMLIT_*` environment variables, so the frames are always uncompressed. `py_mount` records the Python call's duration (`py_ms`) and the size of the options as `json.dumps` writes them (`options_bytes`).
- **When Streamlit sends the options.** Streamlit sends a listview's options again only when the listview's payload changes. A rerun that changes nothing sends a cache reference instead, for a payload of 10 KB or more. `rerun_unchanged` is the first rerun after the mount, and on that rerun the payload does change: the harness's listview has a `key`, so from this rerun on the payload carries the selection persisted in `st.session_state`. `rerun_unchanged` therefore measures a rerun that sends the options again, as a click on a keyed listview or a parameter change does. A probe on 2026-10-11 at 10,000 grouped rows received 672 KB for the mount, 672 KB for the first rerun, 1.5 KB for each later rerun that changed nothing, and 672 KB for a click.
- **CPU throttling.** `--perf-throttle 4` slows the page's renderer fourfold through `Emulation.setCPUThrottlingRate`. The Python server and the transfer keep their speed, so a throttled run shows a slow browser, not a slow machine: `py_ms` does not change. The default is 1 (none).
- **Which checkout is measured.** Streamlit registers a component's frontend files from the installed package when the server starts, and `python -m streamlit` puts the working directory first on the import path. The browser tier therefore always measures the checkout it is run from, and refuses to run from any other working directory. Each record carries that checkout's `git describe --always --dirty --abbrev=12` in the field `branch`, and the name of the built script (`index-<hash>.js`) in `bundle`. The bundle is gitignored: a checkout of other sources keeps the old bundle until the next build. When `branch` changes and `bundle` does not, either the change left the frontend alone or nobody rebuilt the bundle. `streamlit` and `browser` hold the Streamlit and Chromium versions.

### A browser record

One line of the JSONL file, abbreviated:

| Key | Fields |
|---|---|
| `n`, `shape`, `grouped`, `throttle`, `rep`, `branch`, `bundle`, `streamlit`, `browser`, `started` | metadata; `branch` holds `git describe`, `bundle` the built script's file name, `streamlit` and `browser` the versions, and `started` the time in UTC when the rep finished. A record written before the `disabled` shape existed has no `shape`, and the report derives it from `grouped`. A record written before 2026-10-13 has no `bundle`, `streamlit` or `browser` |
| `mount` | `rows_ms`, `painted_ms`, `task_ms`, `script_ms`, `recalcstyle_ms`, `layout_ms`, `ws_bytes` |
| `py_mount` | `py_ms`, `options_bytes` |
| `dom_nodes`, `heap_mb` | after the mount and a forced garbage collection; `heap_mb` counts MiB (2^20 bytes) |
| `search_narrow`, `search_clear` | `rows_ms`, `painted_ms` |
| `search_busy` | main-thread time over both search steps |
| `rerun_unchanged` | `roundtrip_ms`, `settled_ms`, `task_ms` and its parts, `ws_bytes` |
| `py_rerun` | `py_ms` |
| `rerun_one_changed` | `roundtrip_ms`, `settled_ms`, `task_ms` and its parts |
| `click_select` | `local_painted_ms` (the highlight before the round trip), `roundtrip_ms`, `settled_ms`, `task_ms` and its parts |
| `group_collapse`, `group_expand` | `rows_ms`, `painted_ms` (`grouped` and `disabled` only) |
| `scroll` | `p50_ms`, `p95_ms`, `max_ms` per frame |
| `add_option` | `rows_ms`, `painted_ms` |

`dom_nodes` is Chromium's count of Node objects (`Performance.getMetrics`), which includes pseudo-elements such as each row's `::before`. A row inside a skipped render chunk has no pseudo-element, so since the off-screen render chunks the count falls with the skipped rows, by 24 % at 100,000 rows, although the DOM gains one element per chunk.

---

## Prerequisites

- **Node 24** and the frontend dependencies: `npm ci` in `streamlit_listview/frontend/`.
- **A built bundle** for the browser tier: `npm run build` in `streamlit_listview/frontend/`. The benchmark stops with a message naming the missing directory if there is none.
- **uv** with the development extra. Every Python command goes through `uv run --extra devel …`.
- **Chromium for Playwright**, once per machine: `uv run --extra devel playwright install chromium`.
- **Memory.** At 100,000 rows the jsdom worker peaks around 3.8 GB. That is close to Node's default heap limit, which Node derives from the machine's memory: 4.3 GB on the 32 GB reference machine, less on smaller ones. On a smaller machine, run a subset. Do not raise the limit with `--max-old-space-size`: with 8 GB, the 100,000-row `mount` varied by ±99 % instead of ±3 %, because fewer but longer garbage collections fell inside single iterations.
- **A quiet machine.** Close heavy applications, keep the laptop plugged in, and never run two benchmarks at the same time.

---

## Running the frontend tier

Run from `streamlit_listview/frontend/`.

```sh
npm run bench                                                         # the full matrix, ~25 min
LISTVIEW_BENCH_SIZES=1000,50000 npm run bench                         # some sizes
LISTVIEW_BENCH_SHAPES=ungrouped npm run bench                         # one shape
npm run bench -- -t "rerun"                                           # only benchmarks whose name matches
npm run bench -- --outputJson ../../bench-results/before.json         # save the results
npm run bench -- --compare ../../bench-results/before.json            # compare with saved results
```

`LISTVIEW_BENCH_SIZES` accepts any of `100,1000,5000,10000,25000,50000,100000`; `LISTVIEW_BENCH_SHAPES` accepts `grouped,ungrouped,disabled`. Anything else stops the run with an error naming the allowed values.

## Running the browser tier

Run from the repository root.

```sh
uv run --extra devel pytest e2e/perf/ --perf-out bench-results/run.jsonl                        # full matrix, 3 reps
uv run --extra devel pytest e2e/perf/ --perf-out bench-results/run.jsonl --perf-sizes 50000    # one size
uv run --extra devel pytest e2e/perf/ --perf-out bench-results/run.jsonl --perf-shapes grouped --perf-reps 5
uv run --extra devel pytest e2e/perf/ --perf-out bench-results/slow.jsonl --perf-throttle 4    # 4x slower CPU
```

| Option | Default | Meaning |
|---|---|---|
| `--perf-out FILE.jsonl` | none | where to append the records; without it pytest skips the benchmark |
| `--perf-reps N` | 3 | measured runs per cell, after one discarded warm-up; at least 1 |
| `--perf-throttle RATE` | 1 | slowdown factor of the page's renderer through DevTools; at least 1 |
| `--perf-sizes LIST` | all | subset of `100,1000,5000,10000,25000,50000,100000` |
| `--perf-shapes LIST` | all | subset of `grouped,ungrouped,disabled` |

Pass these options only with `e2e/perf/` on the command line; plain `pytest e2e/` collects the benchmark and skips it. `--perf-out` appends, so use a new file per run, or delete the old one first.

Summarize one run, or compare two:

```sh
uv run --extra devel python -m e2e.perf.report bench-results/run.jsonl
uv run --extra devel python -m e2e.perf.report bench-results/before.jsonl bench-results/after.jsonl --markdown > bench-results/before-vs-after.md
```

---

## Comparing two versions

### Before and after a change in the same checkout

```sh
# 1. before the change (the browser tier needs a bundle built from these sources)
(cd streamlit_listview/frontend && npm run build && npm run bench -- --outputJson ../../bench-results/before.json)
uv run --extra devel pytest e2e/perf/ --perf-out bench-results/before.jsonl

# 2. make the change; rebuild the bundle for the browser tier
(cd streamlit_listview/frontend && npm run build)

# 3. after the change
(cd streamlit_listview/frontend && npm run bench -- --outputJson ../../bench-results/after.json --compare ../../bench-results/before.json)
uv run --extra devel pytest e2e/perf/ --perf-out bench-results/after.jsonl
uv run --extra devel python -m e2e.perf.report bench-results/before.jsonl bench-results/after.jsonl --markdown
```

Use the same size and shape selection on both sides.

### Against another branch, for example `main`

Benchmark the other version in a worktree of its own, using **this checkout's** benchmark files, so both sides run identical scenarios:

```sh
HERE="$PWD"                                                     # this checkout's root
git worktree add --detach ../bench-baseline main
(cd ../bench-baseline/streamlit_listview/frontend && npm ci && npm run build)

# frontend tier
cp -r streamlit_listview/frontend/src/bench ../bench-baseline/streamlit_listview/frontend/src/
(cd ../bench-baseline/streamlit_listview/frontend && npx vitest bench --run --outputJson "$HERE/bench-results/main.json")
(cd streamlit_listview/frontend && npm run bench -- --outputJson ../../bench-results/branch.json --compare ../../bench-results/main.json)

# browser tier: run from the baseline's root, with the baseline's own uv environment
cp -r e2e/perf ../bench-baseline/e2e/
(cd ../bench-baseline && LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel pytest e2e/perf/ --perf-out "$HERE/bench-results/main.jsonl")
uv run --extra devel pytest e2e/perf/ --perf-out bench-results/branch.jsonl
uv run --extra devel python -m e2e.perf.report bench-results/main.jsonl bench-results/branch.jsonl --markdown > bench-results/main-vs-branch.md

# clean up (--force: the copied files, node_modules and .venv are untracked)
git worktree remove --force ../bench-baseline
```

- **Why copy instead of pointing at the other checkout.** The browser tier always measures the checkout it runs from, and it refuses to run from anywhere else. The frontend tier imports the component relative to the bench file. Copying the benchmark files into the other checkout is the only way to measure its code with these scenarios.
- **Requirements for the other checkout.** It needs what the benchmark files use. `main` has all of it as of October 2026; much older versions may not.
  - Frontend tier: vitest 4, `src/test/makeData.ts`, `Listview` exported from `src/Listview.tsx` with the `data` and `setStateValue` props, the types `Id`, `ListviewData` and `ListviewItem` from `src/types.ts`, and the DOM hooks the scenarios find: `listview-opt-<id>`, `stListviewSearch`, `stListviewNewOption` and the class `listview-group-header--collapsible`, which marks the group header that a click collapses.
  - Browser tier: `demo/data.py::make_large_dataset` (which imports `demo/parsing.py`), the `app` and `_servers` fixtures of `e2e/conftest.py` with `e2e/e2e_utils.py::StreamlitRunner`, and the hooks above plus `stListview` and `.listview-body`.
- **Order.** Run the two sides one after the other, never in parallel, and keep the machine otherwise idle.

---

## Reading the results

### The frontend table

```text
 ✓ src/bench/listview.bench.tsx > grouped n=50000 93551ms
     name                    hz       min       max      mean   …     rme  samples
   · rerun_unchanged     5.1684    160.84    325.88    193.48   …  ±15.28%       15  [3.55x] ⇑
     rerun_unchanged     1.4574    567.63    808.45    686.13   …   ±7.06%       15  (baseline)
```

- `mean` (ms) and `hz` (runs per second, 1000 / mean) are the figures to read first. vitest prints no median in this table, but the JSON file has one.
- `rme` is the relative margin of error: the true mean most likely lies within that percentage of the printed one (a 95 % confidence interval). A difference smaller than the rme of either side is not a result.
- `samples` is the number of measured iterations; see the sample budgets above.
- With `--compare`, each benchmark gets a second line marked `(baseline)` and a ratio on the current line: `[3.55x] ⇑` means 3.55 times as many runs per second as the baseline, that is, faster. `⇓` means slower.

### The browser report

```text
n      shape      scenario      metric      median   low     high    reps
50000  ungrouped  search_clear  painted_ms  839      819     2,138   3
```

Comparing two files gives both medians, both ranges, both rep counts and the difference, `B − A`:

```text
n      shape      scenario      metric      A median  A range       A reps  B median  B range     B reps  Δ       Δ %
50000  ungrouped  search_clear  painted_ms  3,838     3,827..3,873  3       839       819..2,138  3       -2,999  -78%
```

A negative `Δ` means B's value is lower: faster for a time, smaller for `ws_bytes`, `options_bytes`, `dom_nodes` and `heap_mb`. A row present on only one side shows `—`, and the footer counts such rows; the group scenarios are an example when one side ran ungrouped only. A file recorded before the `disabled` shape existed compares as usual: its `grouped` and `ungrouped` rows pair with the new file's, and the new file's `disabled` rows have no A side.

The report groups records by size, shape, scenario and metric only. It ignores `throttle`, `branch`, `bundle` and the versions, so two runs that differ in any of them merge without a warning when appended to one file. Give each run a file of its own.

### Which metric answers which question

| Question | Look at |
|---|---|
| How long does the list take to appear once the page has loaded? | `mount.painted_ms` |
| How long does typing a search, or clearing it, freeze the list? | `search_narrow.painted_ms`, `search_clear.painted_ms` |
| How expensive is a rerun that sends the options again, such as a parameter change? | `rerun_unchanged.settled_ms` and `.task_ms`; `ws_bytes` for the payload |
| How quickly does a click show feedback? | `click_select.local_painted_ms`, and `settled_ms` for the full round trip |
| Does scrolling stay smooth? | `scroll.p95_ms` from 25k to 100k; 60 Hz is about 16.7 ms per frame |
| Is it the React side or everything around it? | the frontend tier for the same scenario |

### Rules for drawing conclusions

These rules screen results; they are not statistical tests. The rme assumes independent samples from one distribution; garbage collection and JIT compilation break that assumption. A low..high range of three reps is the observed spread, not a confidence interval.

1. **A difference inside the spread is not a result.** Frontend tier: compare the mean against its rme. Browser tier: compare medians, and check whether the two low..high ranges overlap. Such a difference is unresolved, not absent: the run neither shows nor rules out an effect of that size.
2. **Check the canaries first.** `mount` and the search scenarios are the canaries: stable, costly, and untouched by most changes. If they moved between A and B by more than the change under test can explain, the machine was disturbed: repeat that cell before reading the cheaper scenarios. Transient load has slowed whole stretches of a run by 2 to 5 times. A change to the mount or the search leaves no canary of its own; read `py_mount.py_ms` instead, which no frontend change affects.
3. **Compare like with like.** Same machine, same size and shape selection, same benchmark files, runs close together in time. The first cell of a run starts cold; that once made a 100-row mount read twice as slow in a subset run. Prefer full runs, or the same subset on both sides.
4. **Frontend numbers are relative.** jsdom is not a browser, and React runs its development build there. Use them to rank alternatives; quote browser numbers.
5. **Expect the browser tier to show a smaller gain for React-side fixes.** A rerun that sends the options also contains the Python call (about 110 ms at 50,000 grouped rows), the payload transfer (2.3 to 4.3 MB at 50,000 rows, depending on the shape), parsing, and Chrome's style, layout and paint for the rows near the frame. Only the React part shrinks.
6. **Small sizes are noisy and fast.** Below 5,000 rows most scenarios take a few milliseconds. `scroll` sits at the 60 Hz frame time at every size. Base decisions on 10,000 to 100,000 rows.
7. **Three reps detect large effects.** For a suspected 5 to 10 % effect in the browser tier, run that cell with `--perf-reps 10` on both sides. Alternate the sides (A, B, A, B), appending each A run to one file and each B run to another, so a drift in machine load reaches both. More reps narrow the range; they do not guarantee that an effect of that size shows.

---

## Worked example: `main` vs. the render-chunk branch

The first comparison, on 2026-10-03, measured `main` (`5dfc413`) against a branch that reuses unchanged option objects across reruns and renders rows in keyed chunks of 100 (merged as `62bdc43`). The machine ran Windows 11 on a Core Ultra 7, with CPU throttling off. These numbers, and those of the sections below, hold for the named commits on that machine; they guide design decisions and set no thresholds.

| Measurement | Rows | main | branch |
|---|---|---|---|
| Frontend: rerun, options unchanged, ungrouped (median) | 50k | 626 ms | 152 ms |
| Frontend: search narrow + clear, ungrouped (median) | 50k | 10.6 s | 1.9 s |
| Browser: clear the search, ungrouped (`painted_ms`) | 50k | 3.8 s | 0.84 s |
| Browser: rerun, options unchanged, ungrouped (`settled_ms`) | 50k | 492 ms | 276 ms |
| Browser: mount, all sizes (`painted_ms`) | | | 1 to 5 % slower, within noise |

How to read it:

- **The rerun fix** cut React's rerun work about fourfold in the frontend tier. In the browser it saved about 45 % at 50,000 ungrouped rows, because the payload transfer and Chrome's work over the full DOM remain. Rule 5 applies; this is not a contradiction.
- **The chunking fix** made clearing the search 4.5 times faster in the browser and 5.6 times faster in the frontend tier. That cost was almost entirely React inserting rows.
- **Mount** was not a target and stayed within the spread.
- **One stretch of the first frontend run** ran 2 to 5 times slower, including 100-row cells the change cannot affect. Re-running those cells gave normal numbers. Rules 2 and 3 caught it.

---

## Reference run: 100 to 100,000 rows

On 2026-10-13 the full matrix ran on the reference machine: Windows 11, Core Ultra 7 155H, 32 GB, on mains power, CPU throttling off, at commit `6a4f035`, with Streamlit 1.65.0 and Chromium 153. Both tiers completed every cell, the frontend tier in 25 minutes and the browser tier in 24. Browser tier, grouped shape, medians of 3 reps:

| Measurement | Metric | 10,000 | 50,000 | 100,000 |
|---|---|---|---|---|
| The list appears | `mount.painted_ms` | 219 ms | 600 ms | 1,149 ms |
| Clearing the search | `search_clear.painted_ms` | 83 ms | 277 ms | 544 ms |
| A rerun that sends the options again | `rerun_unchanged.settled_ms` | 77 ms | 230 ms | 410 ms |
| Rerun, one option changed | `rerun_one_changed.settled_ms` | 90 ms | 228 ms | 422 ms |
| Click: the row highlights | `click_select.local_painted_ms` | 17 ms | 37 ms | 78 ms |
| Click: the round trip and its long tasks end | `click_select.settled_ms` | 98 ms | 262 ms | 488 ms |
| Scroll frame, median / p95 | `scroll.p50_ms` / `p95_ms` | 17 / 18 ms | 17 / 18 ms | 17 / 18 ms |
| Payload sent with the list | `mount.ws_bytes` | 0.67 MB | 3.35 MB | 6.70 MB |
| The `listview()` call in Python | `py_mount.py_ms` | 21 ms | 110 ms | 235 ms |
| DOM nodes | `dom_nodes` | 31,555 | 156,355 | 312,355 |

The ungrouped shape scrolls the same and is 7 to 28 % faster in the other scenarios at 50,000 and 100,000 rows; its payload is a third smaller: 4.5 MB at 100,000 rows.

How to read it:

- **Everything that touches the rows grows in proportion to them.** Doubling the rows from 50,000 to 100,000 multiplies the mount, the search, both reruns and a click by 1.8 to 2.1.
- **Scrolling stays at the frame rate at every size measured.** Over the 60 scripted scroll steps a frame takes 17 ms at the median and 18 ms at the 95th percentile, from 100 to 100,000 rows, in all three shapes: the 60 Hz frame time.
- **What remains of a click is the round trip.** At 100,000 rows a click's `roundtrip_ms` and `settled_ms` both have a median of 488 ms; a long task followed the round trip in one of the three reps. A click on a keyed listview sends the 6.7 MB options again, and the rerun calls `listview()` again (239 ms, `py_rerun.py_ms`). The main thread is busy for 311 ms of the click (`click_select.task_ms`), 165 ms of it in script.
- **Compared with 1.0.1**, measured the same evening from GitHub `main` (`307c2a6`, the library code of the `v1.0.1` tag, with Streamlit 1.64.0), the list appears 2.1 times sooner at 100,000 rows (2,387 ms then), a click settles 2.6 times sooner (1,255 ms), and a scroll frame's p95 falls from 196 ms to 18 ms. The DOM holds 24 % fewer nodes (410,274 then), because a row in a skipped render chunk has no `::before`. The mount's `script_ms` rises by 20 % (561 ms then) and `heap_mb` by 5 %. The `listview()` call stays within the spread in 17 of 21 cells, so the newer Streamlit does not explain the gain.
- **The frontend tier** ran every cell. Its 100,000-row mount takes 6.7 s grouped, 6.4 s ungrouped and 6.8 s disabled in jsdom. Against 1.0.1 it shows only the added script, because jsdom performs no layout or paint: React's work takes 1.1 to 1.6 times as long in 55 of the 76 cells from 10,000 rows up, and the rest stay within their rme. `add_option` in the ungrouped shape takes 3.9 to 5.0 times as long, because an option added to a list without groups changes `aria-setsize` on every row.

### The `disabled` shape

Later on 2026-10-07 the `grouped` and `disabled` shapes ran together at every size, in both tiers, on the same machine, with the code of `328affd`. Browser tier, medians of 3 reps, with the low..high range:

| Measurement at 100,000 rows | Metric | `grouped` | `disabled` | Δ |
|---|---|---|---|---|
| Payload sent with the list | `mount.ws_bytes` | 6.70 MB | 8.59 MB | +28 % |
| The `listview()` call in Python | `py_mount.py_ms` | 222 ms (217..222) | 265 ms (258..268) | +20 % |
| Rerun, options unchanged | `rerun_unchanged.settled_ms` | 788 ms (786..793) | 882 ms (831..915) | +12 % |
| The list appears | `mount.painted_ms` | 2,339 ms (2,337..2,342) | 2,417 ms (2,401..2,534) | +3 % |

How to read it:

- **The cost is the key in the payload.** Every row carries `"disabled": false` or `"disabled": true`, so the options grow by 28 % at every size. Python builds that larger payload on every rerun, and Streamlit sends it whenever the payload changes.
- **Everything else stays within the spread.** At 100,000 rows the search, a click, the group toggles, scrolling and `add_option` show ranges that overlap between the two shapes. The run measured no cost of the disabled rows themselves.
- **The frontend tier agrees.** Only the 100,000-row `mount` moved beyond its error margin: 5.51 s instead of 5.26 s (+5 %, rme ±3 %). The `disabled` cells ran to completion at every size, 100,000 rows included.
- **An app can avoid the cost.** A row without the key is enabled, so passing `disabled` only on the rows that are disabled sends the smaller payload.
- **Since the off-screen render chunks, a rerun and a click show the cost too.** In the reference run of 2026-10-13, at 100,000 rows, a rerun that sends the options took 475 ms with the key and 410 ms without (+16 %), the `listview()` call 271 ms instead of 235 ms (+15 %), and the list appeared after 1,222 ms instead of 1,149 ms (+6 %). A click settled in 537 ms instead of 488 ms (+10 %); the ranges of the 3 reps overlap, and the run of 2026-10-11 measured +15 %. Paint no longer hides the transfer, and a click on a keyed listview sends the larger payload again. Search, scrolling and the group toggles take as long as without the key.

### Off-screen render chunks

On 2026-10-07 the browser tier compared `main` (`328affd`) with the branch that turns each 100-row render chunk into an element with `content-visibility: auto` (merged as `35f6706`), on the reference machine with CPU throttling off. Medians of 3 reps, with the low..high range:

| Measurement at 100,000 rows, grouped | Metric | `main` | branch | Δ |
|---|---|---|---|---|
| The list appears | `mount.painted_ms` | 2,310 ms (2,252..2,323) | 1,120 ms (1,108..1,141) | −52 % |
| Click: the row highlights | `click_select.local_painted_ms` | 262 ms (259..272) | 80 ms (76..81) | −70 % |
| Click: the round trip and its long tasks end | `click_select.settled_ms` | 1,254 ms (1,249..1,259) | 475 ms (448..487) | −62 % |
| Rerun, options unchanged | `rerun_unchanged.settled_ms` | 780 ms (774..853) | 384 ms (383..400) | −51 % |
| Rerun, one option changed | `rerun_one_changed.settled_ms` | 1,183 ms (1,183..1,186) | 424 ms (422..426) | −64 % |
| Clearing the search | `search_clear.painted_ms` | 1,797 ms (1,783..1,826) | 550 ms (548..556) | −69 % |
| Collapsing a group | `group_collapse.painted_ms` | 511 ms (505..519) | 107 ms (107..107) | −79 % |
| Scroll frame, p95 | `scroll.p95_ms` | 158 ms (156..218) | 18 ms (18..18) | −89 % |
| Main thread, mount | `mount.task_ms` | 1,993 ms (1,950..2,015) | 804 ms (788..827) | −60 % |
| Script, mount | `mount.script_ms` | 556 ms (543..565) | 673 ms (655..697) | +21 % |

How to read it:

- **The gain is style, layout and paint.** At mount `layout_ms` falls by 96 % and `recalcstyle_ms` by 87 %.
- **Script time rises with the rows.** Each row now carries `aria-posinset` and `aria-setsize`, and the frontend keeps a map of row positions. At 100,000 rows that adds 117 ms to the mount's `script_ms` and 19 ms to a click's (136 ms to 155 ms); the spike without the attributes measured 23 ms more at mount. Adding an option changes `aria-setsize` on every row, so `add_option.rows_ms` rises from 74 ms to 207 ms, while its `painted_ms` falls from 317 ms to 232 ms.
- **Mount still creates every row.** `mount.rows_ms`, the time until the last row exists in the DOM, rises from 914 ms to 1,084 ms with the script, and the mount's painted time still halves.
- **What remains of a click is the round trip.** At 100,000 rows the click's `roundtrip_ms` is 432 ms of its 475 ms `settled_ms`: Streamlit's rerun with the 6.7 MB options payload, which the render chunks cannot touch.
- **Sizes.** At 50,000 rows the scenarios in the table fall by 28 to 76 %. At 10,000 rows the mount, a click and clearing the search fall by 22 to 67 %, and an unchanged rerun stays within the spread. At 1,000 rows, measured with 10 reps on both sides, the painted times stay within the spread, and three DOM-update times (`add_option`, `group_collapse`, `search_clear`) rise by 1 to 2 ms. Scrolling runs at the 60 Hz frame time at every size.
- **The ungrouped shape behaves the same.** A click settles in 380 ms instead of 763 ms, and a scroll frame's p95 falls from 190 ms to 18 ms.
- **The frontend tier cannot see the gain.** jsdom performs no layout or paint.
- **The review fix leaves these numbers standing.** `useResetChunkHeights`, added after the final review, runs only when the blocks change, never on a click. A rerun of the 100,000-row cells after it stayed within the spread for the ungrouped shape. The grouped cell ran 3 to 11 % slower, and its Python call, which the fix does not touch, ran 7 % slower with it. That points to machine load (rule 2); the run cannot rule out a small cost of the fix.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `LISTVIEW_BENCH_SIZES: "2000" is not one of …` | a typo in the filter; use the listed values |
| `--perf-sizes: '2000' is not one of …` | the same for the browser tier |
| `argument --perf-reps: '0' is not a whole number of at least 1` | `--perf-reps` and `--perf-throttle` take 1 or more |
| `pytest: error: unrecognized arguments: --perf-out` | the options exist only with `e2e/perf/` on the command line; run `pytest e2e/perf/ …` |
| all browser benchmarks show `SKIPPED` | `--perf-out` is missing |
| `no built bundle under …/frontend/build` | run `npm run build` in that checkout's `streamlit_listview/frontend/` |
| `run the browser benchmark from the root of the checkout it lives in …` | `cd` to the repository root that contains the `e2e/perf/` you are running |
| `benchmark precondition failed: …` | the component did not behave as the scenario expects; the message names the condition. Investigate before weakening it |
| `benchmark timeout waiting for …` after 240 s | the page never reached the condition, for example a component that does not render every row |
| `TimeoutError: … 300000ms exceeded` from Playwright | a wait outside the page timed out: the page load, the harness's status line, or the "show" button |
| the frontend run dies with a heap or worker error at 50k or 100k | not enough memory; run a subset or close other applications |
| `UnicodeEncodeError` from the report | an old copy of `report.py`; the current one forces UTF-8 output |

**Known limitation: virtualization.** Both tiers consider a mount finished when the last row exists in the DOM. A virtualized (windowed) list never renders it, so the frontend tier fails its precondition and the browser tier times out. Before a virtualized implementation can be benchmarked, `mount` needs a different end condition, such as the scroll height or a row-count attribute. That condition must stand for the work a user waits for, not merely let the scenario finish.

---

## Extending the benchmarks

**A new frontend scenario.** Add a `bench(...)` at the **end** of the cell's `describe` in `src/bench/listview.bench.tsx`. vitest pairs `--compare` by position, so inserting earlier shifts every later pairing. The pattern:

- `setup` mounts with the shared `mount()` helper, looks up the elements the body needs, and calls `precondition(...)` so the scenario cannot time a no-op.
- The body performs the timed operation and leaves the list ready for its own next iteration.
- `teardown: release` unmounts and clears the cached handles.
- The budget is `budget(n)` for scenarios of about a second or more at 50,000 rows and `cheapBudget(n)` for faster ones.

Appending keeps every existing pairing, so saved frontend baselines stay comparable; the new scenario has no baseline yet. Any change to an existing scenario's body, setup or budget changes what it measures: re-record the baselines on both sides.

**A new browser scenario.** Add a JavaScript snippet to `e2e/perf/measure.py`, using `window.__bench` helpers such as `until`, `painted`, `byId` and `settled`, and call it from `run_cell`. A snippet that reports `settled_ms` calls `watchLongTasks()` before its action and passes the watcher to `settled()`. The record key you write becomes the scenario name. `report.py` includes every numeric field at the top level of a record and one level inside a dict; it skips booleans and the metadata keys in `META`. A new metadata field therefore goes into `META` too, or the report reads it as a measurement.

**A new size or shape.** Extend `SIZES` / `SHAPES` in both `src/bench/fixtures.ts` and `e2e/perf/cells.py`, and adjust the sample budgets for anything larger than 100,000 rows. A size above 100,000 also needs a sixth digit in both dataset generators, since `item-100000` would sort before `item-99999`. A new size, wherever it goes in `SIZES`, moves every cell of the later shapes: the bench file declares the cells shape by shape, each shape with every size, and vitest's `--compare` pairs them by position. A frontend baseline saved before the change therefore pairs the wrong cells; record both sides again with the new bench file. The browser report pairs records by size and shape and needs nothing. A new shape goes at the **end** of both `SHAPES`, for the same positional pairing as a new scenario. Build its rows in `makeLargeDataset` and in `cells.shape_rows`, pin both to the same literals in `fixtures.test.ts` and `e2e/perf/test_cells.py`, and say whether it has groups in `isGrouped` and `Cell.grouped`. The browser tier repeats the grouping rule in `app_bench.py` (`grouped = shape != "ungrouped"`) and takes the scenario's row ids and search text from the grouped rows in `measure.py::cell_ids`; check both, and the shape lists in the `--perf-shapes` help text in `e2e/perf/conftest.py` and in `app_bench.py`'s docstring.

**After any change to the benchmark code**, run the quick checks:

```sh
(cd streamlit_listview/frontend && npm run build && npm test)       # also typechecks the bench files
(cd streamlit_listview/frontend && LISTVIEW_BENCH_SIZES=100 npm run bench)
uv run --extra devel pytest e2e/perf/ -q                              # the report and helper unit tests
uv run --extra devel pytest e2e/perf/ -q --perf-out bench-results/smoke.jsonl --perf-sizes 100 --perf-reps 1
```

---

## File map

| File | Purpose |
|---|---|
| `streamlit_listview/frontend/src/bench/fixtures.ts` | dataset mirror, payload factory, size/shape filters, precondition guard (unit-tested, covered) |
| `streamlit_listview/frontend/src/bench/listview.bench.tsx` | the frontend scenarios, budgets and cells |
| `streamlit_listview/frontend/vitest.config.ts` | `benchmark.include`; bench files excluded from coverage |
| `e2e/perf/app_bench.py` | the Streamlit app the browser tier drives |
| `e2e/perf/measure.py` | in-page timing snippets and the per-run measurement procedure |
| `e2e/perf/test_bench.py` | one test per cell: warm-up, then `--perf-reps` records; the server's flags |
| `e2e/perf/conftest.py` | `--perf-*` options, the `perf` marker, the skip and working-directory guards |
| `e2e/perf/cells.py` | the matrix, each shape's rows, option parsing, bundle check and name, JSONL writer |
| `e2e/perf/report.py` | the summary and comparison report |
| `bench-results/` | your results (gitignored) |
| `CLAUDE.md`, section "Performance benchmarks" | a summary for coding agents that points here |
