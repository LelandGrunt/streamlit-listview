"""settle() and the row locator of the GIF scenarios (scripts/gif/stage.py).

settle() is page JavaScript, so it needs a browser, not a Streamlit server. A
stub page stands in for the listview: a host element whose shadow root holds
the empty `.listview-root` scaffold, into which the test renders
`[data-testid="stListview"]` when it wants. A key-change remount leaves the
page in that state for about one frame after its script run has ended.
"""

import sys
from pathlib import Path
from typing import Any, cast

import pytest
from playwright.sync_api import Error, Page

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "gif"))

import stage
from stage import Stage, Take, settle

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


# After `delayMs`, replaces the host with a new one whose listview changes on
# each of the next `busyFrames` animation frames, then sets window.__busyDone.
# A remount can replace the host while settle() watches the old one.
REPLACE_JS = """([delayMs, busyFrames]) => {
  setTimeout(() => {
    // Here, not above: the old host's last tick may still set it to true.
    window.__busyDone = false;
    const host = document.createElement("div");
    host.attachShadow({ mode: "open" }).innerHTML =
      '<div class="listview-root"><div data-testid="stListview"></div></div>';
    document.getElementById("host").replaceWith(host);
    const listview = host.shadowRoot.querySelector('[data-testid="stListview"]');
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


def _replace_while_settling(page: Page, busy_frames: int) -> None:
    """Mount the old host, then replace it 50 ms later.

    The first animation frame of a fresh page arrives about a second late.
    Waited out here, with the fonts settle() awaits, it lets settle() find
    the old host at once, and 50 ms falls inside the old host's QUIET_FRAMES
    window.
    """
    page.evaluate(MOUNT_JS, [0, 0])
    page.evaluate(
        """async () => {
          await document.fonts.ready;
          for (let i = 0; i < 3; i++) {
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
        }"""
    )
    page.evaluate(REPLACE_JS, [50, busy_frames])


def test_settle_waits_for_a_replacement_host_to_go_quiet(page: Page):
    """The old host goes quiet the moment it leaves the page; settle() must
    follow the listview to its new host."""
    _replace_while_settling(page, 30)
    settle(page)
    assert page.evaluate("window.__busyDone") is True


def test_settle_names_a_replacement_host_that_never_goes_quiet(page: Page, monkeypatch):
    monkeypatch.setattr(stage, "SETTLE_TIMEOUT_MS", 500)
    _replace_while_settling(page, 100_000)
    with pytest.raises(Error, match="settle: the listview did not go quiet in 500 ms"):
        settle(page)


def test_settle_names_fonts_that_never_load(page: Page, monkeypatch):
    """document.fonts.ready waits for every font the page loads; a request
    that never answers must count against the same timeout."""
    monkeypatch.setattr(stage, "SETTLE_TIMEOUT_MS", 500)
    page.route("http://fonts.invalid/**", lambda route: None)
    page.evaluate(MOUNT_JS, [0, 0])
    page.evaluate(
        """() => {
          const font = new FontFace("Stalled", "url(http://fonts.invalid/x.woff2)");
          document.fonts.add(font);
          font.load().catch(() => {});
        }"""
    )
    with pytest.raises(Error, match="settle: the fonts did not load in 500 ms"):
        settle(page)


# Renders one row per test id into the scaffold, as ListItem does.
ROWS_JS = """(testIds) => {
  const scaffold = document.getElementById("host").shadowRoot
    .querySelector(".listview-root");
  for (const testId of testIds) {
    const row = document.createElement("div");
    row.setAttribute("data-testid", testId);
    scaffold.appendChild(row);
  }
}"""

# Ids the component accepts whose test ids a quoted CSS selector cannot hold.
ROW_IDS: list[str | int] = [
    'quo"te',
    "back\\slash",
    "line\nbreak",
    "with space",
    "Zürich",
    "0",
    42,
]


@pytest.mark.parametrize("item_id", ROW_IDS)
def test_opt_finds_the_row_of_any_accepted_id(page: Page, item_id):
    page.evaluate(ROWS_JS, [f"stListviewOption-{i}" for i in ROW_IDS])
    clip = cast(Any, {"x": 0, "y": 0, "width": 1, "height": 1})
    rows = Stage(page, Take(), Path(), [], clip).opt(item_id)
    assert rows.count() == 1
    assert rows.get_attribute("data-testid") == f"stListviewOption-{item_id}"
