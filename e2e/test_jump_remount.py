# e2e/test_jump_remount.py
"""A key-change remount scrolls a far default into the middle of the frame.

Regression: the remounted instance's stylesheet applies after its first commit,
so the first row was measured unstyled (25.6 px instead of 35.4 px). On the
first frame with the stylesheet the browser skips every render chunk, so the
ResizeObserver never reported the styled row, and the skipped chunks above
`item-00987` kept the unstyled estimate. The jump then left the default row
800 px below the frame. With a stylesheet that arrives late, the jump ran while
the body could not scroll yet, and the list stayed at its top.
"""

import re
from pathlib import Path

from playwright.sync_api import Page, Route, expect

# The harness e2e/conftest.py serves for this module, with its listview
# awaited before each test.
APP_FILE = Path(__file__).with_name("app_jump_remount.py")

FAR_DEFAULT = "item-00987"
# The component's stylesheet (index-[hash].css), not Streamlit's own.
COMPONENT_CSS = re.compile(r"streamlit_listview\.listview/index-[^/]*\.css")

# True once the row lies centered in the list body, the published row height
# matches the first row, and the scroll range is the rendered list's. The
# tolerances absorb subpixel row heights.
_CENTERED_JS = """
(row) => {
  const body = row.closest(".listview-body");
  const listbox = row.closest('[role="listbox"]');
  const first = listbox.querySelector('[role="option"]');
  const frame = body.getBoundingClientRect();
  const box = row.getBoundingClientRect();
  const center = box.top + box.height / 2 - (frame.top + frame.height / 2);
  const published = parseFloat(
    listbox.style.getPropertyValue("--listview-row-height"),
  );
  return (
    Math.abs(center) <= 2 &&
    Math.abs(published - first.getBoundingClientRect().height) < 0.01
  );
}
"""


def _remount_to(page: Page, default: str) -> None:
    page.get_by_test_id("stRadio").get_by_text(default, exact=True).click()
    row = page.get_by_test_id(f"stListviewOption-{default}")
    expect(row).to_have_attribute("aria-selected", "true")
    page.wait_for_function(_CENTERED_JS, arg=row.element_handle(), timeout=10_000)


def test_remount_centers_a_far_default(page: Page):
    _remount_to(page, FAR_DEFAULT)


def test_remount_centers_a_far_default_when_the_stylesheet_is_late(page: Page):
    # The remount fetches the stylesheet again; hold it for 400 ms, a slow
    # connection's delay, so the first frames after the remount are unstyled.
    def late(route: Route) -> None:
        page.wait_for_timeout(400)
        route.continue_()

    page.route(COMPONENT_CSS, late)
    _remount_to(page, FAR_DEFAULT)


def test_remount_back_to_a_near_default(page: Page):
    # The return trip: from the far default back to a row in the first chunk.
    _remount_to(page, FAR_DEFAULT)
    _remount_to(page, "item-00042")
