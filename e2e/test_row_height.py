# e2e/test_row_height.py
"""A rerun that changes the row height resizes the render chunks the browser skips.

Regression: a keyed list of 1,000 grouped rows, scrolled to its bottom, got
`item_height=50` on a rerun. The published row height (`--listview-row-height`
on the listbox) stayed at 35.39 px while every row was 50 px, so the nine
skipped chunks kept their old estimate and the list was 37,205 px tall instead
of 50,354 px. The ResizeObserver on the first row reported nothing, because the
browser does not lay out a row inside a skipped chunk, and the first row was
the same element as before the rerun, so no commit measured it again. Only
scrolling back to the top, which rendered the first row's chunk, corrected it.
The same held for `content_font_size` and `show_grid_lines`.
"""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

# The harness e2e/conftest.py serves for this module, with its listview
# awaited before each test.
APP_FILE = Path(__file__).with_name("app_row_height.py")

FIRST_ID = "item-00000"
LAST_ID = "item-00999"

# Rows inside a render chunk the browser skips (content-visibility: auto) are
# not laid out; checkVisibility({contentVisibilityAuto: true}) is false for them.
IS_RENDERED_JS = "(row) => row.checkVisibility({ contentVisibilityAuto: true })"
ROW_HEIGHT_JS = "(row) => row.getBoundingClientRect().height"
# True once the published row height is the first row's height.
PUBLISHED_JS = """(listbox) => {
  const first = listbox.querySelector('[role="option"]');
  const published = parseFloat(
    listbox.style.getPropertyValue("--listview-row-height"),
  );
  return Math.abs(published - first.getBoundingClientRect().height) < 0.01;
}"""
# The listbox's height as laid out now, skipped chunks at their estimate; and
# its height with every chunk rendered (a stylesheet injected into the
# component's shadow root for the one measurement).
HEIGHT_JS = "(listbox) => listbox.getBoundingClientRect().height"
RENDERED_HEIGHT_JS = """(listbox) => {
  const all = document.createElement("style");
  all.textContent = ".listview-chunk { content-visibility: visible !important; }";
  listbox.getRootNode().appendChild(all);
  const height = listbox.getBoundingClientRect().height;
  all.remove();
  return height;
}"""
# Resolves after n animation frames.
WAIT_FRAMES_JS = """(n) => new Promise((done) => {
  const step = (left) => (left === 0 ? done() : requestAnimationFrame(() => step(left - 1)));
  step(n);
})"""


def _scroll_to_the_bottom(page: Page) -> None:
    """Scroll until the last row renders and the first row's chunk is skipped."""
    root = page.get_by_test_id("stListview")
    last = root.get_by_test_id(f"stListviewOption-{LAST_ID}")
    expect(last).to_have_count(1)
    root.get_by_role("listbox").focus()
    page.keyboard.press("End")
    page.wait_for_function(IS_RENDERED_JS, arg=last.element_handle())
    first = root.get_by_test_id(f"stListviewOption-{FIRST_ID}")
    assert first.evaluate(IS_RENDERED_JS) is False


def _change_the_row_height(page: Page, control: str) -> None:
    """Flip one layout control and wait until the rows have the new height."""
    first = page.get_by_test_id(f"stListviewOption-{FIRST_ID}")
    before = first.evaluate(ROW_HEIGHT_JS)
    page.get_by_text(control, exact=True).click()
    page.wait_for_function(
        "([row, before]) => Math.abs(row.getBoundingClientRect().height - before) > 0.5",
        arg=[first.element_handle(), before],
    )


@pytest.mark.parametrize(
    "control",
    [
        pytest.param("50", id="item_height"),
        pytest.param("24", id="content_font_size"),
        pytest.param("show_grid_lines", id="show_grid_lines"),
    ],
)
def test_a_rerun_that_changes_the_row_height_resizes_the_skipped_chunks(
    page: Page, control: str
):
    _scroll_to_the_bottom(page)
    _change_the_row_height(page, control)
    listbox = page.get_by_role("listbox")
    # The published height follows the rows although the first row's chunk is
    # skipped, ...
    page.wait_for_function(PUBLISHED_JS, arg=listbox.element_handle(), timeout=5_000)
    # ... and every skipped chunk takes the new estimate: the list is as tall
    # as it will be once every chunk has rendered. The browser applies the
    # estimate at its next rendering update.
    page.evaluate(WAIT_FRAMES_JS, 4)
    estimated = listbox.evaluate(HEIGHT_JS)
    rendered = listbox.evaluate(RENDERED_HEIGHT_JS)
    assert abs(estimated - rendered) <= 1, f"{estimated=} {rendered=}"
