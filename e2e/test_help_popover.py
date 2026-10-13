# e2e/test_help_popover.py
"""The help popover in a browser, and a label that is all code.

jsdom moves no real focus and lays nothing out, so the unit tests stub both;
these tests check the two things only a browser decides: that Tab carries the
focus from the trigger onto a link in the help, and that long help stays
inside the viewport and scrolls.
"""

from pathlib import Path

import pytest
from playwright.sync_api import Locator, Page, expect

from e2e.test_accessibility import _assert_accessible

APP_FILE = Path(__file__).with_name("app_help.py")

# Playwright's WebKit, like Safari by default, leaves links out of the Tab
# order: on a plain page, Tab from a button skips a link to the next button.
# The focus then leaves the help, which closes, as it should.
_LINKS_TABBABLE = pytest.mark.skip_browser("webkit")


def _listview(page: Page, name: str) -> Locator:
    """The stListview root of the instance whose listbox carries `name`."""
    return page.get_by_test_id("stListview").filter(
        has=page.get_by_role("listbox", name=name, exact=True)
    )


def _focus_trigger(page: Page, root: Locator) -> None:
    """Focus the help trigger with the pointer parked away from it."""
    page.mouse.move(640, 700)
    root.locator(".listview-help-trigger").focus()


def _assert_inside_viewport(page: Page, popover: Locator) -> None:
    box = popover.bounding_box()
    viewport = page.viewport_size
    assert box is not None and viewport is not None
    assert box["x"] >= 0, box
    assert box["y"] >= 0, box
    assert box["x"] + box["width"] <= viewport["width"], (box, viewport)
    assert box["y"] + box["height"] <= viewport["height"], (box, viewport)


@_LINKS_TABBABLE
def test_tab_from_the_trigger_reaches_a_link_in_the_help(page: Page):
    root = _listview(page, "Linked")
    _focus_trigger(page, root)
    page.keyboard.press("Tab")
    expect(root.locator(".listview-help-popover a")).to_be_focused()
    # Leaving the help closes it, and the focus goes on to the list.
    page.keyboard.press("Tab")
    expect(root.locator(".listview-help-popover")).to_have_count(0)
    expect(root.get_by_role("listbox")).to_be_focused()


@_LINKS_TABBABLE
def test_escape_on_a_link_in_the_help_returns_the_focus_to_the_trigger(page: Page):
    root = _listview(page, "Linked")
    _focus_trigger(page, root)
    page.keyboard.press("Tab")
    page.keyboard.press("Escape")
    expect(root.locator(".listview-help-popover")).to_have_count(0)
    expect(root.locator(".listview-help-trigger")).to_be_focused()


def test_long_help_near_the_top_opens_below_and_scrolls(page: Page):
    root = _listview(page, "Long")
    _focus_trigger(page, root)
    popover = root.locator(".listview-help-popover")
    expect(popover).to_have_attribute("data-placement", "below")
    _assert_inside_viewport(page, popover)
    # The last paragraph is reachable inside the popover...
    body = root.locator(".listview-help-popover__body")
    body.evaluate("(el) => { el.scrollTop = el.scrollHeight; }")
    expect(body.get_by_text("Paragraph 30.")).to_be_in_viewport()
    # ...and so is the body for the keyboard, which scrolls it.
    page.keyboard.press("Tab")
    expect(body).to_be_focused()


def test_the_popover_stays_inside_a_smaller_viewport(page: Page):
    root = _listview(page, "Long")
    _focus_trigger(page, root)
    popover = root.locator(".listview-help-popover")
    expect(popover).to_have_count(1)
    page.set_viewport_size({"width": 700, "height": 400})
    page.wait_for_timeout(200)
    _assert_inside_viewport(page, popover)


def test_the_pointer_crosses_the_gap_into_a_popover_below(page: Page):
    root = _listview(page, "Long")
    trigger = root.locator(".listview-help-trigger")
    trigger.hover()
    popover = root.locator(".listview-help-popover")
    expect(popover).to_have_attribute("data-placement", "below")
    trigger_box = trigger.bounding_box()
    popover_box = popover.bounding_box()
    assert trigger_box is not None and popover_box is not None
    page.mouse.move(
        trigger_box["x"] + trigger_box["width"] / 2,
        popover_box["y"] + 20,
        steps=10,
    )
    expect(popover).to_have_count(1)


def test_long_help_in_the_sidebar_stays_inside_the_viewport(page: Page):
    root = _listview(page, "Sidebar long")
    _focus_trigger(page, root)
    popover = root.locator(".listview-help-popover")
    expect(popover).to_have_count(1)
    _assert_inside_viewport(page, popover)


def test_a_code_label_names_the_listbox_by_its_text(page: Page):
    # The label renders "*" in a code chip; the name must say the same.
    expect(page.get_by_role("listbox", name="*", exact=True)).to_have_count(1)


def test_a_code_label_passes_the_accessibility_scan(page: Page):
    # Without a name, axe-core reports aria-input-field-name (serious).
    root = _listview(page, "*")
    expect(root).to_have_count(1)
    _assert_accessible(page, root)
