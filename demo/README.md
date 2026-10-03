# Listview Demo

An interactive playground and API reference for the `listview` component.

## Run

From the repository root:

```sh
uv run streamlit run demo/app.py
```

`uv run` syncs the project first, so this one command also creates the
environment, installs the package, and compiles the frontend into
`streamlit_listview/frontend/build/` — a generated, git-ignored artifact.

The **Demo** tab is a live playground: every parameter is a control, and the
generated code updates as you change settings. The **Data source** control
switches between the built-in city dataset, your own pasted options, an empty
list, or a **Large** generated dataset (up to 10,000 items) that shows render and
scroll performance at scale. The **API reference** tab documents the full
signature, parameters, return value, and runnable examples (`demo/examples/`).

## Theme switcher

The **Theme** section re-themes the app with any `config_theme_<name>.toml` in
`demo/.streamlit/`; drop a new file there and it shows up in the picker, under
its `DisplayName` from `demo/.streamlit/config_themes.json` (or its bare name
without an entry there). It is a
showcase of the demo, not part of the listview API: the listview has no theme
parameter, so the generated code stays the same while the widget's style adapts
to whatever theme Streamlit is configured with.
A theme that defines `[theme.light]` and `[theme.dark]` switches between the two
in the app menu (**⋮**).

Streamlit has no per-session theme, so the switch applies to the **whole
server**: every open session picks it up on its next rerun, including other
visitors of a hosted demo. It falls back to the Streamlit default 24 hours after
the last switch, and on every server restart, since it lives in memory only.

To hide the switcher on one deployment, set `LISTVIEW_DEMO_THEME_SWITCHER` to
`0` (`false`, `off` and `no` work too); unset, it is on. Locally:

```sh
LISTVIEW_DEMO_THEME_SWITCHER=0 uv run streamlit run demo/app.py
```

On Streamlit Community Cloud, add it under the app's **Settings → Secrets** as a
root-level key; Streamlit copies root-level secrets into the environment:

```toml
LISTVIEW_DEMO_THEME_SWITCHER = "0"
```

The app reads the variable on every rerun, and a theme still applied when the
switch goes off falls back to the default at once.

## Rebuilding the frontend

Edits under `streamlit_listview/frontend/src/` do not go through the install, so
rebuild from `streamlit_listview/frontend` and restart Streamlit:

```sh
npm ci            # once, on a clean clone
npm run build
```

> **Note:** a *stale* bundle is the one quiet failure — it registers fine and
> simply lacks whatever was added after it was built. A *missing* bundle fails
> loudly at registration instead. `LISTVIEW_SKIP_NPM_BUILD=1` skips the install's
> automatic npm build and verifies the existing bundle rather than compiling one.

## Requirements

- Python ≥ 3.10, Streamlit ≥ 1.51 — no extra Python dependencies (Streamlit
  bundles pandas)
- Node.js ≥ 24 (LTS) — only to build the frontend
- [uv](https://docs.astral.sh/uv/)
