"""The capture guard of the README tour (scripts/gif/screencast.py) in Chromium.

The guard decides what the recording shows: a capture of anything but the tab
would put the desktop of whoever runs the script into a committed GIF. A stub
stands in for the browser's getDisplayMedia, so no capture really starts.
"""

import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "gif"))

from screencast import TAB_ONLY_JS

# A getDisplayMedia that records the constraints it gets and returns one track
# reporting ``surface``; installed before the guard, which wraps it.
STUB_JS = """(surface) => {
  window.__stopped = 0;
  MediaDevices.prototype.getDisplayMedia = async function (constraints) {
    window.__constraints = constraints;
    const track = {
      getSettings: () => ({ displaySurface: surface }),
      stop: () => { window.__stopped++; },
    };
    // A stream without a video track reports no surface at all.
    const tracks = surface === "none" ? [] : [track];
    return { getVideoTracks: () => tracks, getTracks: () => tracks };
  };
}"""

CAPTURE_JS = """async () => {
  let error = null;
  try {
    await navigator.mediaDevices.getDisplayMedia({ video: true });
  } catch (e) {
    error = e.message;
  }
  return {
    error,
    stopped: window.__stopped,
    surface: window.__tourSurface,
    constraints: window.__constraints,
  };
}"""


@pytest.fixture(autouse=True)
def go_to_app():
    """No Streamlit server: the guard is page JavaScript (overrides conftest)."""


def _capture(page: Page, surface: str) -> dict:
    # MediaDevices exists only in a secure context, so the page gets an https
    # address; the route answers it, nothing goes to the network.
    page.route(
        "https://screencast.test/",
        lambda route: route.fulfill(body="<html></html>", content_type="text/html"),
    )
    page.goto("https://screencast.test/")
    page.evaluate(STUB_JS, surface)
    page.add_script_tag(content=TAB_ONLY_JS)
    return page.evaluate(CAPTURE_JS)


@pytest.mark.parametrize(
    ("surface", "reported"),
    [("monitor", "monitor"), ("window", "window"), ("none", "undefined")],
)
def test_the_guard_stops_a_capture_that_is_not_the_tab(page: Page, surface, reported):
    result = _capture(page, surface)
    assert result["error"] == (
        f"capture refused: the source is {reported}, not this tab"
    )
    assert result["stopped"] == (0 if surface == "none" else 1)
    assert result["surface"] == surface


def test_the_guard_asks_for_the_current_tab_and_passes_it_on(page: Page):
    result = _capture(page, "browser")
    assert result["error"] is None
    assert result["stopped"] == 0
    assert result["constraints"] == {
        "video": True,
        "preferCurrentTab": True,
        "selfBrowserSurface": "include",
        "surfaceSwitching": "exclude",
        "monitorTypeSurfaces": "exclude",
    }
