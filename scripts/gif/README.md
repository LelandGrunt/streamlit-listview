# README GIFs and the visual comparison

Scripts that regenerate the GIFs in the top-level `README.md`, and that record the same scenarios as PNG frames, so that two recordings show what a change did to the widget's look. One more script records the tour of the demo app that opens the README.

## Parts

- **`scenarios/`**: the catalogue. Each scenario module defines one `SCENARIO`: the Streamlit page it renders, the steps that drive it, and its takes. Eight gallery scenarios write a GIF to `assets/`; three test scenarios (`dark`, `sidebar`, `limits`) only record frames. `_cities.py` holds the city list that several scenarios share.
- **`stage.py`**: `Take`, `Scenario`, and the `Stage` helper the steps use. It holds locators for the widget's parts, `rerun()` and `settle()` to wait for a state instead of a fixed time, `snap()` to take a frame, `press()`, which shows a key badge with `badge=True` (`badge(None)` removes it), `scroll_list()` and `park_pointer()`. A key change leaves the page without a listview for about one frame after the script run ends, so `settle()` waits for the listview to appear before it waits for quiet; `e2e/test_gif_settle.py` checks it in Chromium.
- **`app.py`**: the one capture page. It renders the scenario and the take that `LISTVIEW_GIF_SCENARIO` and `LISTVIEW_GIF_TAKE` name (by default `hero` and its first take), hides Streamlit's header, toolbar, main menu and footer, limits the page to 640 px, and ends every run with a hidden run counter that `rerun()` waits on.
- **`capture.py`**: plays one take in Chromium (a 720 × 840 viewport at device scale factor 2) and screenshots the listview's box plus 12 px on each side, and the take's `clip_top` above it.
- **`make_gif.py`**: scales the frames by 0.5, builds one 256-color palette over all of them, and writes a looping GIF. On its own, `python scripts/gif/make_gif.py FRAMES_DIR OUT.gif [SCALE] [COLORS]` rebuilds a GIF from the frames that `--keep-frames` kept, without a new capture.
- **`generate.py`**: the command line. It starts one Streamlit server per take, and either builds GIFs or records frames.
- **`compare.py`**: compares two recordings frame by frame and writes an HTML report.
- **`screencast.py`**: records the README's tour of the demo app with Streamlit's own *Record screen* and turns the video into `assets/listview-tour.gif`. It uses none of the parts above except `generate.py`'s server start; see [Record the tour](#record-the-tour).

## Scenarios

| Scenario | Shows | Output |
|---|---|---|
| `hero` | live search, multi-select, select-all, collapsing a group | `assets/listview-demo.gif`; the README shows the tour instead, but the PyPI pages of released versions link this file |
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

Options:
- `--scenario NAME` (repeatable), `--gallery` (every gallery scenario) or `--all` (every scenario, test scenarios included; needs `--record`) choose the scenarios. They exclude each other; without any of them, the command builds the hero.
- `--out` (one scenario only), `--scale` (`0.5`), `--colors` (`256`) and `--keep-frames`, which keeps the PNG frames under `build/gif-frames/<scenario>/`, shape a GIF, so `--record` refuses them.
- `--record DIR` and `--overwrite` record frames instead of a GIF; see [Compare before and after a change](#compare-before-and-after-a-change).
- `--port` (`0` picks a free port).

On one machine the output is byte-identical from run to run. Pillow comes with Streamlit, so the commands need no `--with pillow`.

`tests/test_readme.py` checks that the README links every gallery GIF but the hero, and the tour before *Features in action*; that it names each GIF's title; and that `assets/` holds exactly the gallery GIFs and the tour. The scenarios find the widget by the `data-testid`s and classes that `streamlit_listview/frontend/CLAUDE.md` lists, and by Streamlit's own `stRadio` (the preset switch) and `stElementContainer` (which hides the run counter). A renamed hook or a removed feature breaks a scenario; fix the scenario in the same change rather than drop a step.

## Record the tour

`screencast.py` starts the demo (`demo/app.py`), opens it in headless Chromium at 1280 × 800, and starts *Record screen* from the app menu. The tour then runs in real time, about 50 seconds: multi-select, search, collapsible groups, sorting, a default far down the list, the Databricks Brand and Snowflake Brand themes, 100,000 options, and the sidebar. Esc stops the recording, and the script saves the video Streamlit offers for download. ffmpeg turns it into a looping GIF of about 3.5 MB, 960 px wide, sampled at 10 frames per second with repeated frames dropped.

ffmpeg is no project dependency. `uv run --with imageio-ffmpeg` adds a copy for one run; without it, the script looks for `ffmpeg` on the PATH and stops before recording if there is none:

```sh
npm --prefix streamlit_listview/frontend run build
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel --with imageio-ffmpeg python scripts/gif/screencast.py
```

Options: `--out` (`assets/listview-tour.gif`), `--width` (`960`, at most 1280), `--fps` (`10`) and `--port` (`0` picks a free port). The video stays in `build/screencast/tour.webm`; a failed tour step leaves `build/screencast/failure.png`.

What is non-obvious:
- **Only this tab is recorded.** A tab capture would otherwise ask which source to record. Chromium runs with `--auto-accept-this-tab-capture`, and a script in the page asks `getDisplayMedia` for the current tab and stops any other source before Streamlit's recorder sees it. Never add `--use-fake-ui-for-media-stream`: it answers with the whole monitor, so the video shows the desktop of whoever runs the script. `TAB_ONLY_JS` in `screencast.py` is that script; `tests/test_gif_screencast.py` pins the launch flags, and `e2e/test_screencast_guard.py` checks the guard in Chromium.
- **The page draws the mouse pointer.** A tab capture shows none, so the script draws an arrow that follows the mouse and a ring at each click.
- **Esc ends the recording**, so the tour never presses it; `Tour.press` refuses the key. A focused select box swallows Esc, so `record()` blurs the focus before the final Esc.
- **The tour drives the demo by its labels and ids.** Renaming one of them breaks the tour; fix `play_tour` in the same change.
  - In `demo/app.py`: the section pills, `multi`, *Collapsible groups*, *Sort* and its option `both`, *Default*, *Theme* with *Streamlit default*, and *Render widget in sidebar*.
  - In `demo/dataset.py`: the *Large* data source. The *Items* slider is found as the first `stSlider` on the page, so no other slider may come before it.
  - In `demo/.streamlit/config_themes.json`: *Databricks Brand* and *Snowflake Brand*.
  - In `demo/data.py`: the rows `berlin`, `munich`, `cologne` and `seattle`, and `item-99999` of the Large dataset.
  - In Streamlit: `stMainMenu`, `stMainMenuItem-recordScreencast`, `stCountdown`, the buttons *Start recording!* and *Save video to disk*, and the app root's `data-test-script-state`.
- **The theme switcher must be on.** With `LISTVIEW_DEMO_THEME_SWITCHER=0`, the demo hides its Theme section, and the tour fails.
- **Each run differs.** The tour runs in real time, so two runs never produce the same GIF, even of an unchanged widget. Regenerate it when the demo or the widget changes visibly, look at the result, and commit it only then.
- **Every version bump needs a new tour.** The demo shows the installed version next to its title, and the tour records it. Record the tour after the bump has reached the editable install (`uv run` re-installs the project once `pyproject.toml` changes), and check the badge in the GIF.
- **The Databricks Brand and Snowflake Brand steps need the network** for their Google Fonts.
- **Why a GIF:** GitHub serves a `.webp` file from the repository as `application/octet-stream`, and PyPI's image proxy passes only `image/*` types, so a WebP would be missing on PyPI.

## Compare before and after a change

```sh
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --all --record bench-results/visual/before
# change the widget, then: npm --prefix streamlit_listview/frontend run build
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/generate.py --all --record bench-results/visual/after
LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel python scripts/gif/compare.py bench-results/visual/before bench-results/visual/after
```

`--record DIR` writes each scenario's frames and `frames.json` to `DIR/<scenario>/`, and `meta.json` last, so a directory without it holds no complete recording. It refuses a directory that holds a recording unless `--overwrite` is given; `--overwrite` without `--record` is a usage error. `compare.py` pairs frames by scenario, take and step name, prints the frames that differ and a count per status, and writes `report.html` into the second recording (`--report` picks another path). The report shows before, after, and the changed pixels in red. `--threshold N` ignores channel differences up to N (0 to 255). Exit codes: 0 every frame is the same; 1 a frame differs or exists in one recording only; 2 invalid input, or a report that cannot be written.

Compare only recordings from one machine: fonts and the Chromium version change pixels, and the report warns when the two recordings name different Chromium versions or platforms. A difference is not a failure; an intended change reports too, and a person judges it.

## Add a scenario

1. Write `scenarios/<name>.py` (the file name uses underscores, the scenario name hyphens) with `page(take)`, `play(stage)` and `SCENARIO = Scenario(...)`. Import `listview` inside `page()`, never at the top of the module: importing `streamlit_listview` declares the component, which works only inside a Streamlit server, and `generate.py` imports the whole catalogue in a plain process. `test_generate_imports_outside_a_streamlit_server` fails on a top-level import.
   - `Scenario` takes `name`, `title` (the README caption), `gallery`, `page`, `play`, and optionally `takes`, `page_config` (extra `st.set_page_config` arguments, without `page_title` or `layout`) and `gif_name` (only the hero keeps an older file name).
   - Each `Take` is one server run: `name` (passed to `page(take)` and readable as `stage.take`), `server_args` (extra `streamlit run` flags, such as `--theme.base dark`) and `clip_top` (CSS pixels the frame reaches above the listview, for the help popover). A gallery scenario's GIF keeps the first take's frame size: a later take with a smaller widget shows a little more of the page below it, and one with a larger widget stops the run, so put the take with the largest widget first.
   - Build a dataset inside a cached function, not at import: every take's server and `generate.py` import the whole catalogue. `tests/test_gif_scenarios.py` checks that no scenario module holds a generated dataset after import.
2. Add it to `SCENARIOS` in `scenarios/__init__.py`, gallery scenarios before test scenarios, and to the lists at the top of `tests/test_gif_scenarios.py`.
3. Wrap every action that reaches Python in `with stage.rerun():`, and give every frame a step name that is unique within its take.
4. Record the scenario twice and compare the two recordings. They must be identical; a difference means a step does not wait for its state.
5. For a gallery scenario, generate the GIF, keep it at or below 150 KB (`tests/test_gif_scenarios.py` checks the size), and add it to the README's *Features in action* table.
