# README GIFs and the visual comparison

Scripts that regenerate the GIFs in the top-level `README.md`, and that record the same scenarios as PNG frames, so that two recordings show what a change did to the widget's look.

## Parts

- **`scenarios/`**: the catalogue. Each module defines one `SCENARIO`: the Streamlit page it renders, the steps that drive it, and its takes. Eight gallery scenarios write a GIF to `assets/`; three test scenarios (`dark`, `sidebar`, `limits`) only record frames.
- **`stage.py`**: `Take`, `Scenario`, and the `Stage` helper the steps use. It holds locators for the widget's parts, `rerun()` and `settle()` to wait for a state instead of a fixed time, `snap()` to take a frame, `press()` with a key badge, `scroll_list()` and `park_pointer()`.
- **`app.py`**: the one capture page. It renders the scenario and the take that `LISTVIEW_GIF_SCENARIO` and `LISTVIEW_GIF_TAKE` name, hides Streamlit's header, and ends every run with a hidden run counter that `rerun()` waits on.
- **`capture.py`**: plays one take in Chromium (a 720 × 840 viewport at device scale factor 2) and screenshots the listview's box plus 12 px.
- **`make_gif.py`**: scales the frames by 0.5, builds one 256-colour palette over all of them, and writes a looping GIF.
- **`generate.py`**: the command line. It starts one Streamlit server per take, and either builds GIFs or records frames.
- **`compare.py`**: compares two recordings frame by frame and writes an HTML report.

## Scenarios

| Scenario | Shows | Output |
|---|---|---|
| `hero` | live search, multi-select, select-all, collapsing a group | `assets/listview-demo.gif` |
| `keyboard` | single selection by keyboard, with a key badge | `assets/listview-keyboard.gif` |
| `add-options` | `accept_new_options` | `assets/listview-add-options.gif` |
| `markdown` | Markdown in the widget label and the help tooltip | `assets/listview-markdown.gif` |
| `layout` | four layout presets on one list | `assets/listview-layout.gif` |
| `themes` | light, dark and the demo's Databricks Brand and Snowflake Brand themes, one server each; needs the network for their Google Fonts | `assets/listview-themes.gif` |
| `large-list` | 100,000 options with a pinned search | `assets/listview-large-list.gif` |
| `jump-to-default` | the list scrolls its default into view; a radio picks the default, and its key change remounts the list | `assets/listview-jump-to-default.gif` |
| `dark` | `hero` and `markdown` under the dark base theme | recording only |
| `sidebar` | the listview in `st.sidebar` | recording only |
| `limits` | selection cap, disabled rows and widget, empty list, label visibility | recording only |

## Regenerate the GIFs

Prereqs, once: Node 24 or later, and from the repo root:

```sh
npm --prefix streamlit_listview/frontend ci
npm --prefix streamlit_listview/frontend run build
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel playwright install chromium
```

Then:

```sh
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py                       # the hero
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --scenario keyboard   # one gallery GIF
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --gallery             # every gallery GIF
```

Options: `--scenario NAME` (repeatable), `--gallery`, `--out` (one scenario only), `--port` (`0` picks a free port), `--scale` (`0.5`), `--colors` (`256`), and `--keep-frames`, which keeps the PNG frames under `build/gif-frames/<scenario>/`. `--out`, `--scale`, `--colors` and `--keep-frames` shape a GIF, so `--record` refuses them. On one machine the output is byte-identical from run to run.

## Compare before and after a change

```sh
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --all --record bench-results/visual/before
# change the widget, then: npm --prefix streamlit_listview/frontend run build
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --all --record bench-results/visual/after
uv run --extra devel python scripts/gif/compare.py bench-results/visual/before bench-results/visual/after
```

`--record DIR` writes each scenario's frames and `frames.json` to `DIR/<scenario>/`, and `meta.json` last, so a directory without it holds no complete recording. It refuses a directory that holds a recording unless `--overwrite` is given; `--overwrite` without `--record` is a usage error. `compare.py` pairs frames by scenario, take and step name, prints the frames that differ and a count per status, and writes `report.html` into the second recording (`--report` picks another path). The report shows before, after, and the changed pixels in red. `--threshold N` ignores channel differences up to N. Exit codes: 0 every frame is the same, 1 a frame differs, 2 invalid input.

Compare only recordings from one machine: fonts and the Chromium version change pixels, and the report warns when the two recordings name different Chromium versions or platforms. A difference is not a failure; an intended change reports too, and a person judges it.

## Add a scenario

1. Write `scenarios/<name>.py` (the file name uses underscores, the scenario name hyphens) with `page(take)`, `play(stage)` and `SCENARIO = Scenario(...)`. Import `listview` inside `page()`, never at the top of the module: importing `streamlit_listview` declares the component, which works only inside a Streamlit server, and `generate.py` imports the whole catalogue in a plain process. `test_generate_imports_outside_a_streamlit_server` fails on a top-level import.
   - `Scenario` takes `name`, `title` (the README caption), `gallery`, `page`, `play`, and optionally `takes`, `page_config` (extra `st.set_page_config` arguments, without `page_title` or `layout`) and `gif_name` (only the hero keeps an older file name).
   - Each `Take` is one server run: `name` (passed to `page(take)` and readable as `stage.take`), `server_args` (extra `streamlit run` flags, such as `--theme.base dark`) and `clip_top` (CSS pixels the frame reaches above the listview, for the help popover). A gallery scenario's GIF keeps the first take's frame size: a later take with a smaller widget shows a little more of the page below it, and one with a larger widget stops the run, so put the take with the largest widget first.
   - Build a large dataset inside a cached function, not at import: every take's server and `generate.py` import the whole catalogue.
2. Add it to `SCENARIOS` in `scenarios/__init__.py`, gallery scenarios before test scenarios, and to the lists at the top of `tests/test_gif_scenarios.py`.
3. Wrap every action that reaches Python in `with stage.rerun():`, and give every frame a step name that is unique within its take.
4. Record the scenario twice and compare the two recordings. They must be identical; a difference means a step does not wait for its state.
5. For a gallery scenario, generate the GIF, keep it at or below 150 KB, and add it to the README's *Features in action* table.
