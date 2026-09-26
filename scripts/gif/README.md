# README demo GIF

Scripts that regenerate the hero GIF in the top-level `README.md`
(`assets/listview-demo.gif`).

- **`generate.py`** — the one-command generator: spawns the capture page on a
  free port, waits until it is healthy, captures the frames, assembles the GIF,
  and stops the server. Drives the three modules below.
- **`app.py`** — a minimal Streamlit page rendering one well-configured
  `listview` (multi-select, grouped, searchable, collapsible, select-all) on a
  curated cities dataset. Chrome is hidden so the frame is just the component.
- **`capture.py`** — drives the page with Playwright (shadow-DOM-piercing
  testid locators) and screenshots the component region at each step (idle →
  live search → multi-select → select-all → collapse a group), writing
  `frame_NNN.png` + `frames.json` (per-frame durations). Importable as
  `capture(url, out_dir)`.
- **`make_gif.py`** — assembles the frames into an infinitely-looping GIF with a
  global 256-color palette (no dithering) and per-frame durations. Importable as
  `build_gif(frames_dir, out, scale, colors)`.

## Regenerate

Prereqs (once): Node ≥ 24, and a venv with the package (built frontend bundle)
plus the capture deps. From the repo root:

```sh
uv venv
uv pip install -e ".[devel]" pillow            # builds the bundle via the build backend
uv run --extra devel playwright install chromium
```

Then a single command does everything:

```sh
uv run python scripts/gif/generate.py    # -> assets/listview-demo.gif
```

Options: `--out` (default `assets/listview-demo.gif`), `--port` (`0` = auto-pick
a free port), `--scale` (`0.5`), `--colors` (`256`), `--keep-frames` (keep the
PNGs under `build/gif-frames/`). It uses Streamlit's **default theme**.

The interactions, dataset, and look are intentionally simple — edit `app.py`
(config/dataset) or `capture.py` (interaction sequence) to change them.

### Running the steps individually

`generate.py` orchestrates the modules; you can also run them by hand:

```sh
# Serve the capture page on a spare port (Streamlit default theme).
uv run python -m streamlit run scripts/gif/app.py \
  --server.port 8535 --server.headless true --browser.gatherUsageStats false

# In another shell: capture frames, then assemble the GIF.
uv run python scripts/gif/capture.py http://localhost:8535 build/gif-frames
uv run python scripts/gif/make_gif.py build/gif-frames assets/listview-demo.gif 0.5 256
```
