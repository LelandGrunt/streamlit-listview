# e2e/test_performance.py
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import echo
from e2e.e2e_utils import StreamlitRunner  # the app fixture's type, for annotations
from e2e.perf_dataset import N

# The harness e2e/conftest.py serves for this module.
APP_FILE = Path(__file__).with_name("app_performance.py")

# Derive the ids and search text this module types from the SAME generator, at
# the SAME N, the harness renders — re-spelling make_large_dataset's id format
# as literals here drifts the moment the generator changes. demo/ is not a
# package, so it goes on sys.path first (the import the harness itself does).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
from data import make_large_dataset

_ROWS = make_large_dataset(N)
FIRST_ID = _ROWS[0]["id"]
LAST_ID = _ROWS[-1]["id"]
# The last label's zero-padded number ("Item 04999" -> "04999"): unique among
# the N labels, so searching it narrows the list to exactly one row.
LAST_LABEL_NEEDLE = _ROWS[-1]["label"].split()[-1]
# Generous on purpose: guards against pathological regressions, not micro-timing,
# so it does not flake on a loaded CI box.
RENDER_BUDGET_S = 15.0


@pytest.fixture(autouse=True)
def go_to_app():
    """Opt out of the shared navigation (e2e/conftest.py) by overriding it.

    Every test navigates itself, and the budget test times its own
    ``page.goto`` — pre-navigating would make it measure a second, already-warm
    load instead of the cold render it is there to guard.
    """


def test_large_list_renders_all_rows_within_budget(page: Page, app: StreamlitRunner):
    start = time.perf_counter()
    page.goto(app.server_url)
    root = page.get_by_test_id("stListview").first
    expect(root).to_be_visible(timeout=20000)
    # Non-virtualized: every row is in the DOM. Count them all, because the
    # last row stays in place when a render chunk in the middle goes missing.
    # Assert presence (count), not visibility — most rows sit below the fold.
    rows = root.locator("[data-testid^='stListviewOption-']")
    expect(rows).to_have_count(N, timeout=30000)
    elapsed = time.perf_counter() - start
    assert elapsed < RENDER_BUDGET_S, (
        f"render took {elapsed:.1f}s (budget {RENDER_BUDGET_S}s)"
    )
    # The groups are contiguous batches of the generated rows, so the list
    # renders them in the generator's order.
    rendered = rows.evaluate_all("(rows) => rows.map((row) => row.dataset.testid)")
    assert rendered == [f"stListviewOption-{row['id']}" for row in _ROWS]


def test_large_list_stays_responsive(page: Page, app: StreamlitRunner):
    page.goto(app.server_url)
    root = page.get_by_test_id("stListview").first
    expect(root).to_be_visible(timeout=20000)

    # Search narrows N rows to a single label-unique match (the number of the
    # last item's label).
    root.get_by_test_id("stListviewSearch").fill(LAST_LABEL_NEEDLE)
    options = root.locator("[data-testid^='stListviewOption-']")
    expect(options).to_have_count(1, timeout=10000)
    expect(root.get_by_test_id(f"stListviewOption-{LAST_ID}")).to_be_visible()

    # Clear the search and select the first row; the selection echoes back.
    root.get_by_test_id("stListviewSearch").fill("")
    first = root.get_by_test_id(f"stListviewOption-{FIRST_ID}")
    first.click()
    expect(first).to_have_attribute("aria-selected", "true")
    expect(echo(page, "perf")).to_contain_text(FIRST_ID, timeout=10000)


# Listview wraps each 100-row render chunk in .listview-chunk, which has
# `content-visibility: auto`: a chunk outside the list's scrollport skips style,
# layout and paint, although its rows stay in the DOM.
# checkVisibility({contentVisibilityAuto: true}) is false for a row inside such
# a skipped chunk.
IS_RENDERED_JS = "(row) => row.checkVisibility({ contentVisibilityAuto: true })"
COUNT_SKIPPED_JS = """(listbox) => [...listbox.querySelectorAll('[role="option"]')]
  .filter((row) => !row.checkVisibility({ contentVisibilityAuto: true })).length"""


def _mount(page: Page, app: StreamlitRunner):
    """Open the app and wait until every row is in the DOM; return the root."""
    page.goto(app.server_url)
    root = page.get_by_test_id("stListview").first
    expect(root.get_by_test_id(f"stListviewOption-{LAST_ID}")).to_have_count(
        1, timeout=30000
    )
    return root


def test_rows_outside_the_frame_skip_rendering(page: Page, app: StreamlitRunner):
    root = _mount(page, app)
    first = root.get_by_test_id(f"stListviewOption-{FIRST_ID}")
    last = root.get_by_test_id(f"stListviewOption-{LAST_ID}")
    page.wait_for_function(IS_RENDERED_JS, arg=first.element_handle())
    skipped = root.get_by_role("listbox").evaluate(COUNT_SKIPPED_JS)
    # The 300 px frame shows part of the first chunk; the browser renders at
    # most one more, so at most two chunks of 100 rows are not skipped.
    assert skipped >= N - 2 * 100, f"only {skipped} of {N} rows skipped"
    assert last.evaluate(IS_RENDERED_JS) is False


def test_end_reaches_the_last_row_through_skipped_chunks(
    page: Page, app: StreamlitRunner
):
    root = _mount(page, app)
    listbox = root.get_by_role("listbox")
    last = root.get_by_test_id(f"stListviewOption-{LAST_ID}")
    listbox.focus()
    page.keyboard.press("End")
    expect(listbox).to_have_attribute(
        "aria-activedescendant", f"listview-opt-{LAST_ID}"
    )
    expect(last).to_be_in_viewport()
    page.wait_for_function(IS_RENDERED_JS, arg=last.element_handle())


def test_rows_report_their_place_in_the_whole_list(page: Page, app: StreamlitRunner):
    root = _mount(page, app)
    first = root.get_by_test_id(f"stListviewOption-{FIRST_ID}")
    last = root.get_by_test_id(f"stListviewOption-{LAST_ID}")
    expect(first).to_have_attribute("aria-posinset", "1")
    expect(first).to_have_attribute("aria-setsize", str(N))
    expect(last).to_have_attribute("aria-posinset", str(N))
    # A search narrows the rows, not the set the numbers describe.
    root.get_by_test_id("stListviewSearch").fill(LAST_LABEL_NEEDLE)
    expect(root.locator("[data-testid^='stListviewOption-']")).to_have_count(
        1, timeout=10000
    )
    expect(last).to_have_attribute("aria-posinset", str(N))
    expect(last).to_have_attribute("aria-setsize", str(N))


# The listbox's height as laid out now, skipped chunks at their estimate; and
# its height with every chunk rendered. The second injects a stylesheet into
# the component's shadow root for the one measurement and removes it again.
HEIGHT_JS = "(listbox) => listbox.getBoundingClientRect().height"
RENDERED_HEIGHT_JS = """(listbox) => {
  const root = listbox.getRootNode();
  const all = document.createElement('style');
  all.textContent = '.listview-chunk { content-visibility: visible !important; }';
  (root === document ? document.head : root).appendChild(all);
  const height = listbox.getBoundingClientRect().height;
  all.remove();
  return height;
}"""
# Resolves after n animation frames: useResetChunkHeights keeps a chunk hidden
# for two frames after its rows change.
WAIT_FRAMES_JS = """(n) => new Promise((done) => {
  const step = (left) => (left === 0 ? done() : requestAnimationFrame(() => step(left - 1)));
  step(n);
})"""
# Matches the rows numbered xx77, one in every chunk of 100, and x77x; in the
# last chunk it keeps exactly one row, number N - 23.
NEEDLE_IN_EVERY_CHUNK = "77"
NEEDLE_MATCHES = sum(NEEDLE_IN_EVERY_CHUNK in row["label"] for row in _ROWS)
KEPT_IN_LAST_CHUNK_ID = _ROWS[N - 100 + 77]["id"]


def test_skipped_chunks_estimate_the_rendered_height(page: Page, app: StreamlitRunner):
    root = _mount(page, app)
    first = root.get_by_test_id(f"stListviewOption-{FIRST_ID}")
    page.wait_for_function(IS_RENDERED_JS, arg=first.element_handle())
    listbox = root.get_by_role("listbox")
    # Every skipped chunk is its row count times the measured row height, so
    # the list is as tall as it will be once every chunk has rendered.
    estimated = listbox.evaluate(HEIGHT_JS)
    rendered = listbox.evaluate(RENDERED_HEIGHT_JS)
    assert abs(estimated - rendered) <= 1, f"{estimated=} {rendered=}"


def test_a_search_after_scrolling_leaves_no_gaps(page: Page, app: StreamlitRunner):
    root = _mount(page, app)
    listbox = root.get_by_role("listbox")
    first = root.get_by_test_id(f"stListviewOption-{FIRST_ID}")
    last = root.get_by_test_id(f"stListviewOption-{LAST_ID}")
    kept = root.get_by_test_id(f"stListviewOption-{KEPT_IN_LAST_CHUNK_ID}")
    # Render the last chunk with all of its 100 rows, then leave it again.
    listbox.focus()
    page.keyboard.press("End")
    page.wait_for_function(IS_RENDERED_JS, arg=last.element_handle())
    page.wait_for_timeout(200)
    page.keyboard.press("Home")
    page.wait_for_function(IS_RENDERED_JS, arg=first.element_handle())
    # The search leaves one row in that chunk, which is now far below the
    # frame and skipped: it must take the height of that one row, not the
    # height of the 100 rows the browser remembers from its last render.
    root.get_by_test_id("stListviewSearch").fill(NEEDLE_IN_EVERY_CHUNK)
    expect(root.locator("[data-testid^='stListviewOption-']")).to_have_count(
        NEEDLE_MATCHES, timeout=10000
    )
    page.evaluate(WAIT_FRAMES_JS, 3)
    assert kept.evaluate(IS_RENDERED_JS) is False
    estimated = listbox.evaluate(HEIGHT_JS)
    rendered = listbox.evaluate(RENDERED_HEIGHT_JS)
    assert abs(estimated - rendered) <= 1, f"{estimated=} {rendered=}"
