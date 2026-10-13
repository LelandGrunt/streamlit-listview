"""The first-render wait of the GIF capture (scripts/gif/capture.py).

A scenario may start from a list without a visible row: an empty list, or one
whose groups all start collapsed. The capture must still find the listview
and record its first frame.
"""

import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from e2e.e2e_utils import StreamlitRunner

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "gif"))

import capture

APP_FILE = Path(__file__).parent / "app_gif_capture.py"


@pytest.fixture(autouse=True)
def go_to_app():
    """Each test opens the state it needs (overrides conftest)."""


@pytest.mark.parametrize("state", ["empty", "collapsed"])
def test_first_render_accepts_a_list_without_a_visible_row(
    page: Page, app: StreamlitRunner, state
):
    page.goto(f"{app.server_url}?state={state}", wait_until="domcontentloaded")
    capture.first_render(page)
    assert page.locator('[data-testid^="stListviewOption-"]:visible').count() == 0
    assert page.get_by_test_id("stListview").bounding_box() is not None


def test_first_render_names_a_listview_that_never_renders(
    page: Page, app: StreamlitRunner, monkeypatch
):
    monkeypatch.setattr(capture, "FIRST_RENDER_TIMEOUT_MS", 3_000)
    page.goto(f"{app.server_url}?state=none", wait_until="domcontentloaded")
    # Playwright's call log names the locator the wait gave up on.
    with pytest.raises(PlaywrightTimeoutError, match=r'get_by_test_id\("stListview"\)'):
        capture.first_render(page)
