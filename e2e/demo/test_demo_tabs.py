# e2e/demo/test_demo_tabs.py
import pytest
from playwright.sync_api import Page, expect

from e2e.demo.test_demo_empty_pickers import wait_for_run


@pytest.mark.parametrize("mode", ["single", "multi"])
def test_reading_the_api_reference_keeps_the_live_selection(page: Page, mode):
    """A visit to the API reference must not clear the playground.

    The tabs rendered only the open one, so the API run left the live widget
    out, Streamlit dropped its state, and the return to Demo mounted a fresh
    widget with nothing selected.
    """
    page.get_by_role("radio", name=mode, exact=True).click()
    wait_for_run(page)
    listview = page.get_by_test_id("stListview").first
    berlin = listview.get_by_test_id("stListviewOption-berlin")
    berlin.click()
    expect(berlin).to_have_attribute("aria-selected", "true", timeout=10000)
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)
    wait_for_run(page)
    before = berlin.bounding_box()
    assert before is not None

    page.get_by_role("tab", name="API reference").click()
    expect(page.get_by_text("Function signature")).to_be_visible(timeout=10000)
    wait_for_run(page)
    page.get_by_role("tab", name="Demo").click()
    wait_for_run(page)

    expect(berlin).to_have_attribute("aria-selected", "true")
    expect(page.get_by_text("1 selected")).to_be_visible()
    # The rows keep their measured height after the hidden tab is shown again.
    after = berlin.bounding_box()
    assert after is not None
    assert after["height"] == before["height"]
