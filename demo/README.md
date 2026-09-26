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
