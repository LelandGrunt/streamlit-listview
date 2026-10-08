# Demo (`demo/`)

These rules extend the root `CLAUDE.md`. `demo/README.md` describes the playground for its users.

## The widget key
- **`app.py` folds the dataset, `collapsed_groups`, `default` and a reset nonce into `widget_key`.** A keyed widget keeps its state across parameter changes, so only a new key makes a changed `default` or `collapsed_groups` take effect (root `CLAUDE.md`, *Invariants that span both languages*).
- **The dataset enters the key through `dataset.dataset_identity`:** the data source, plus the size for Large. A selection kept across a source switch would keep every old id as a new entry under `accept_new_options`. Edits to the Custom options text stay out of the key, so they show the in-place reconciliation.

## Presets and generated code
- **Each preset in `data.py` inlines its own dict unwrap.** `codegen` emits only `inspect.getsource(func)`, so a preset that calls a shared helper would raise `NameError` in the snippet a user copies out. That is no licence to copy the label precedence rule into the demo; it lives in `streamlit_listview/_options.py` only.
- **The demo spots an inert preset by counting the calls `listview` makes through `data.FormatProbe`,** never by inspecting the options. A preset is inert when every option carries its own label, so nothing on screen changes.
- **`SECTIONS` in `app.py` stays a literal,** because `tests/test_demo.py` reads it through the AST.

## The theme switcher (`themes.py`)
The Theme section overlays a `demo/.streamlit/config_theme_<name>.toml` onto Streamlit's live config. The component needs nothing for it: `useColorScheme` and the inherited `--st-*` variables follow a live theme change.
- **A switch is process-global.** Streamlit has no per-session theme: every rerun builds its theme from the global config, so a switch reaches every session on its next rerun, the hosted demo's other visitors included. The UI says so. The switch goes through the internal `streamlit.config.set_option` (the public `st.set_option` refuses theme options), and only `themes.py` calls it.
- **The picker mirrors `SERVER_THEME.active`, never session state.** `render_theme` writes the server's theme into the widget key before rendering, and only `on_change` switches. A picker driven by its own session state would show a stale pick, and applying it again would undo another session's switch.
- **A switch reaches the browser one rerun late.** Streamlit sends a run's theme before the widget callbacks run, and `st.rerun()` inside a callback does nothing. So `_switch_theme` sets a flag, and the top of `app.py` reruns. The 24-hour expiry (`THEME_TTL`) is checked the same way on each rerun; a timer thread would change nothing that anyone sees before their next rerun.
- **Each switch restores the boot config first.** A snapshot of every `theme.*` option, taken at the first switch, keeps `config.toml` and the CLI flags, so an option that only the previous theme set never leaks into the next one.
- **"Streamlit default" is a string option, not `None`:** a selectbox renders a `None` value as an empty field. The Sort and Formatting pickers avoid the same trap.
- **`LISTVIEW_DEMO_THEME_SWITCHER=0`** (or `false`, `off`, `no`) turns the picker off for one deployment; unset means on, so local runs and the e2e suite need no setup. On Community Cloud it is a root-level secret, which Streamlit copies into `os.environ` at server start. When it is off, `render_demo` filters out the Theme pill, `_switch_theme` refuses to switch, and `expire(enabled=False)` drops a still-applied theme on the next rerun.
- **`_switch_theme` ignores names outside `THEMES`:** callbacks see the raw client value before the selectbox validates it.
- **The theme files decide which themes exist; `config_themes.json` only names them.** `discover_themes` globs the `.toml` files, and `theme_labels` maps each `Name` to its `DisplayName`, so a file without an entry appears under its bare name.
- **Tests:** `tests/test_demo.py` pins every theme file to real Streamlit option keys, because a typo only logs a warning and drops the color. It builds each theme as Streamlit does, because a rejected value (such as a Google Fonts URL that names two families) raises on every rerun, and it checks that `config_themes.json` names exactly the shipped files. `e2e/demo/test_demo_theme.py` and `test_demo_theme_off.py` boot their own servers through the conftest's `EXTRA_ENV`, because a theme left applied would leak into the other demo modules, which share one server.

## Deployment
- **`requirements.txt` pins the released `streamlit-listview` version** that Streamlit Community Cloud and the Codespaces dev container install; the `release` skill bumps it. It sits next to `app.py` so that Community Cloud picks it before the root `uv.lock`, which would build the repo and needs npm.
- **The title's version badge reads the installed distribution** (`importlib.metadata.version`), so the README tour shows the version it was recorded with.

## The README tour depends on the labels
`scripts/gif/screencast.py` drives the demo by the labels that `scripts/gif/README.md` lists under *Record the tour*: the section pills, the selection mode, the feature toggles and the sliders. Renaming one of them breaks the tour; fix `play_tour` in the same change.
