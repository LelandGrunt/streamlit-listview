"""settle() of the GIF scenarios (scripts/gif/stage.py) in Chromium.

settle() is page JavaScript, so it needs a browser, not a Streamlit server. A
stub page stands in for the listview: a host element whose shadow root holds
the empty `.listview-root` scaffold, into which the test renders
`[data-testid="stListview"]` when it wants. A key-change remount leaves the
page in that state for about one frame after its script run has ended.
"""

import sys
from pathlib import Path

import pytest
from playwright.sync_api import Error, Page

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "gif"))

import stage
from stage import settle

# A host with an open shadow root that holds only the scaffold, as the V2
# renderer leaves it before React's first render.
HOST_JS = """() => {
  const host = document.createElement("div");
  host.id = "host";
  host.attachShadow({ mode: "open" }).innerHTML =
    '<div class="listview-root"></div>';
  document.body.appendChild(host);
}"""

# Renders the listview into the scaffold after `delayMs`. Then it changes the
# listview on each of the next `busyFrames` animation frames and sets
# window.__busyDone after the last change.
MOUNT_JS = """([delayMs, busyFrames]) => {
  window.__busyDone = false;
  setTimeout(() => {
    const root = document.getElementById("host").shadowRoot;
    const listview = document.createElement("div");
    listview.dataset.testid = "stListview";
    root.querySelector(".listview-root").appendChild(listview);
    let left = busyFrames;
    const tick = () => {
      if (left === 0) {
        window.__busyDone = true;
        return;
      }
      left -= 1;
      listview.textContent = String(left);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, delayMs);
}"""


@pytest.fixture(autouse=True)
def go_to_app(page: Page):
    """No Streamlit server: settle() is page JavaScript (overrides conftest)."""
    page.set_content("<html><body></body></html>")
    page.evaluate(HOST_JS)


def test_settle_waits_for_a_listview_that_renders_late(page: Page):
    page.evaluate(MOUNT_JS, [200, 0])
    settle(page)
    assert page.locator('[data-testid="stListview"]').count() == 1


def test_settle_waits_for_a_late_listview_to_go_quiet(page: Page):
    """A listview found late still gets QUIET_FRAMES frames without a change."""
    page.evaluate(MOUNT_JS, [200, 30])
    settle(page)
    assert page.evaluate("window.__busyDone") is True


def test_settle_names_a_listview_that_never_renders(page: Page, monkeypatch):
    monkeypatch.setattr(stage, "SETTLE_TIMEOUT_MS", 500)
    with pytest.raises(Error, match="settle: no listview on the page after 500 ms"):
        settle(page)


def test_one_timeout_covers_the_wait_for_the_listview_and_for_quiet(
    page: Page, monkeypatch
):
    """A listview that appears late and never goes quiet fails within the one
    SETTLE_TIMEOUT_MS, not after a second timeout of its own."""
    monkeypatch.setattr(stage, "SETTLE_TIMEOUT_MS", 500)
    page.evaluate(MOUNT_JS, [200, 100_000])
    with pytest.raises(Error, match="settle: the listview did not go quiet in 500 ms"):
        settle(page)
    assert page.evaluate("window.__busyDone") is False
