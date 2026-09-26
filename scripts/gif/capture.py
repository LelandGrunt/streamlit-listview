"""Drive the capture page with Playwright and screenshot the component each step.

Importable: ``capture(url, out_dir)`` -> number of frames written.
CLI: ``python capture.py <url> <frames_out_dir>``

Writes ``frame_NNN.png`` files plus ``frames.json`` ([[filename, duration_ms], ...]).
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def capture(url: str, out_dir) -> int:
    """Capture the interaction frames from the running capture page at ``url``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("frame_*.png"):
        old.unlink()
    # Drop any stale manifest first, so an aborted capture can't leave a
    # frames.json pointing at frames that were just deleted (a later make_gif
    # run over a --keep-frames dir would otherwise hit FileNotFoundError).
    (out_dir / "frames.json").unlink(missing_ok=True)

    frames: list[list] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 720, "height": 840}, device_scale_factor=2
        )
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded")

        # Wait for the component (shadow DOM pierced by Playwright's css engine).
        page.locator('[data-testid="stListviewOption-berlin"]').wait_for(
            state="visible", timeout=60000
        )
        page.wait_for_timeout(900)

        root = page.locator('[data-testid="stListview"]').first
        box = root.bounding_box()
        pad = 12
        clip = {
            "x": max(box["x"] - pad, 0),
            "y": max(box["y"] - pad, 0),
            "width": box["width"] + 2 * pad,
            "height": box["height"] + 2 * pad,
        }

        idx = {"i": 0}

        def snap(duration_ms: int) -> None:
            name = f"frame_{idx['i']:03d}.png"
            page.screenshot(path=str(out_dir / name), clip=clip)
            frames.append([name, duration_ms])
            idx["i"] += 1

        search = page.locator('[data-testid="stListviewSearch"]')
        clear = page.locator('[data-testid="stListviewSearchClear"]')
        selectall = page.locator('[data-testid="stListviewSelectAllToggle"]')

        def opt(id_: str):
            return page.locator(f'[data-testid="stListviewOption-{id_}"]')

        def grp(name: str):
            return page.locator('[data-testid="stListviewGroup"]', has_text=name)

        # 1) idle
        snap(1000)

        # 2) live search "ber" (client-side filter, no rerun) -> hold
        search.click()
        for ch in "ber":
            search.press_sequentially(ch, delay=70)
            page.wait_for_timeout(150)
            snap(260)
        snap(1200)

        # clear search
        clear.click()
        page.wait_for_timeout(250)
        snap(1000)

        # 3) multi-select a few (each click triggers a Streamlit rerun)
        for id_ in ["berlin", "paris", "tokyo"]:
            opt(id_).click()
            page.wait_for_timeout(450)
            snap(520)
        snap(1100)

        # 4) Select all -> Deselect all
        selectall.click()
        page.wait_for_timeout(500)
        snap(1400)
        selectall.click()
        page.wait_for_timeout(500)
        snap(900)

        # 5) collapse + expand a group (client-side, no rerun)
        grp("USA").click()
        page.wait_for_timeout(320)
        snap(1100)
        grp("USA").click()
        page.wait_for_timeout(320)
        snap(900)

        # tail hold for a clean loop point
        snap(700)

        (out_dir / "frames.json").write_text(json.dumps(frames))
        browser.close()

    return len(frames)


if __name__ == "__main__":
    n = capture(sys.argv[1], sys.argv[2])
    print(f"captured {n} frames")
