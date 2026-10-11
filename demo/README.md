# Listview Demo

An interactive playground and API reference for the `listview` component.

The [hosted demo](https://st-listview-demo.streamlit.app/) runs the latest
release from PyPI, which `demo/requirements.txt` pins. The command below runs
the demo of your checkout instead, with the package built from its sources.

## Run

From the repository root:

```sh
uv run streamlit run demo/app.py
```

`uv run` syncs the project first. On the first run it creates the environment,
installs the package, and compiles the frontend into
`streamlit_listview/frontend/build/`, a generated, git-ignored artifact. The
compile step needs Node.js ≥ 24 and npm.

## What the demo shows

The **Demo** tab is a live playground. Its **Configuration** panel groups the
parameters into ten sections, which a row of pills switches between: Basic,
Data, Appearance, Layout, Behavior, Search, Groups, Sorting, Formatting and
Theme. Every parameter but `args`, `kwargs` and `key` has a control:
`format_func` offers five presets, and `on_change` shows a toast and counts the
changes. The generated code updates as you change settings.

The **Data source** control in the **Data** section offers four datasets:
**Built-in cities**, **Custom** (options you paste), **Empty**, and **Large**, a
generated dataset of up to 100,000 items in groups of 100.

The Large dataset shows the listview's cost at scale. The listview creates
every row, but the browser lays out and paints only the rows near the visible
frame. At 100,000 items, measured in Chromium on a laptop with a Core Ultra 7
155H, the list appears in about 1.1 seconds, scrolling runs at 60 frames per
second, and the app settles about 0.5 seconds after a click. Firefox before 125
and Safari before 18 lay out every row. Each click, and each settings change
that alters the listview, resends all options: 6.75 MB, which
`demo/.streamlit/config.toml` compresses to 0.48 MB on the network by turning
on `server.enableWebsocketCompression`.

The **API reference** tab documents the full signature, the parameters, the
return value, and the examples in `demo/examples/`. Each example also runs on
its own:

```sh
uv run streamlit run demo/examples/single.py
```

## Theme switcher

The **Theme** section re-themes the app with any `config_theme_<name>.toml` in
`demo/.streamlit/`. The picker lists each file under its `DisplayName` from
`demo/.streamlit/config_themes.json`, or under its bare name when the JSON has
no entry for it. A new theme file needs an entry there all the same:
`tests/test_demo.py` checks that `config_themes.json` names exactly the shipped
files.

The switcher showcases the demo; it is not part of the listview API. The
listview has no theme parameter, so the generated code stays the same while the
widget's style follows whatever theme Streamlit is configured with. A theme
that defines both `[theme.light]` and `[theme.dark]` lets the viewer switch
between the two under **⋮ → Settings**.

Streamlit has no per-session theme, so the switch applies to the **whole
server**: every open session picks it up on its next rerun, including other
visitors of a hosted demo. The theme falls back to the Streamlit default on the
first rerun 24 hours after the last switch, and on every server restart, since
it lives in memory only. While a theme file is applied, a line under the title
names it, so every visitor sees which theme is on, whoever picked it.

To hide the switcher on one deployment, set `LISTVIEW_DEMO_THEME_SWITCHER` to
`0`, `false`, `off` or `no`, in any letter case; unset, the switcher is on.
Locally, in a POSIX shell:

```sh
LISTVIEW_DEMO_THEME_SWITCHER=0 uv run streamlit run demo/app.py
```

In PowerShell, where the variable then stays set for the session:

```powershell
$env:LISTVIEW_DEMO_THEME_SWITCHER = "0"; uv run streamlit run demo/app.py
```

On Streamlit Community Cloud, add it under the app's **Settings → Secrets** as
a root-level key. Streamlit copies root-level strings and numbers into the
environment, but not booleans, so quote the value:

```toml
LISTVIEW_DEMO_THEME_SWITCHER = "0"
```

An unquoted `false` is a TOML boolean: Streamlit leaves it out of the
environment, and the switcher stays on.

The app reads the variable on every rerun. When the switcher goes off, a theme
still applied falls back to the default on the next rerun.

## Rebuilding the frontend

`uv run` reinstalls the package only when `pyproject.toml` changes, so it does
not pick up edits under `streamlit_listview/frontend/src/`. After such an edit,
rebuild from `streamlit_listview/frontend` and restart Streamlit:

```sh
npm run build
```

The first `uv run` already installed the frontend's dependencies. Run `npm ci`
first only in a checkout without `streamlit_listview/frontend/node_modules`.

> **Note:** a *stale* bundle is the one quiet failure — it registers fine and
> lacks whatever was added after it was built. A *missing* bundle fails loudly
> at registration instead. `LISTVIEW_SKIP_NPM_BUILD=1` skips the install's
> automatic npm build and verifies the existing bundle rather than compiling one.

## Requirements

- Python ≥ 3.10 and Streamlit ≥ 1.56. The demo uses the `required` parameter of
  `st.pills` and `st.segmented_control`, which Streamlit 1.56 added; the
  package itself needs only Streamlit ≥ 1.51. The demo imports pandas and toml,
  which Streamlit depends on, so it needs no other Python packages.
- Node.js ≥ 24 (LTS) and npm, to compile the frontend on the first `uv run`
- [uv](https://docs.astral.sh/uv/)
