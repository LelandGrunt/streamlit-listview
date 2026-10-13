"""Play one take of one GIF scenario in Chromium and screenshot its frames.

Importable: ``capture(url, out_dir, scenario, take, frames, clip_size=None)``.
generate.py starts the take's server and calls it; see scripts/gif/README.md.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

from stage import Scenario, Stage, Take, clip_for, settle

DEVICE_SCALE_FACTOR = 2
# The first run may serve a cold component bundle and, for large-list, 100,000
# options.
FIRST_RENDER_TIMEOUT_MS = 90_000


class CaptureError(RuntimeError):
    """A take failed; the message names the scenario, the take and the last step."""


@dataclass(frozen=True)
class CaptureResult:
    """The frame size of a take, and the Chromium version that played it."""

    clip_size: tuple[float, float]
    chromium: str


def first_render(page: Page) -> None:
    """Wait until the capture page has rendered its first run and gone quiet.

    It waits for the run counter, then for the listview's frame, never for a
    row: an empty list, or one whose groups all start collapsed, shows none.
    A step that needs a row waits for it itself.
    """
    page.locator(".gif-run").wait_for(state="attached", timeout=FIRST_RENDER_TIMEOUT_MS)
    page.get_by_test_id("stListview").first.wait_for(
        state="visible", timeout=FIRST_RENDER_TIMEOUT_MS
    )
    settle(page)


def capture(
    url: str,
    out_dir: Path,
    scenario: Scenario,
    take: Take,
    frames: list[dict[str, Any]],
    clip_size: tuple[float, float] | None = None,
) -> CaptureResult:
    """Play ``take`` of ``scenario`` against the capture page at ``url``.

    Writes frame_NNN.png files to ``out_dir`` and appends their entries to
    ``frames``. With ``clip_size`` (an earlier take's) the frame keeps that size,
    because a GIF needs frames of one size: a smaller widget shows more of the
    page below it, and a larger one raises, because the frame would cut it off.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(
                viewport={"width": 720, "height": 840},
                device_scale_factor=DEVICE_SCALE_FACTOR,
            )
            page.goto(url, wait_until="domcontentloaded")
            first_render(page)
            box = page.locator('[data-testid="stListview"]').first.bounding_box()
            if box is None:
                raise CaptureError(
                    f"scenario {scenario.name!r}, take {take.name!r}: "
                    "the listview has no box"
                )
            try:
                clip = clip_for(box, top=take.clip_top, size=clip_size)
            except ValueError as exc:
                raise CaptureError(
                    f"scenario {scenario.name!r}, take {take.name!r}: {exc}"
                ) from exc
            size = (clip["width"], clip["height"])
            stage = Stage(page, take, out_dir, frames, clip)
            try:
                scenario.play(stage)
            except Exception as exc:
                raise CaptureError(
                    f"scenario {scenario.name!r}, take {take.name!r}, "
                    f"after step {stage.last_step!r}: {exc}"
                ) from exc
            return CaptureResult(size, browser.version)
        finally:
            browser.close()
