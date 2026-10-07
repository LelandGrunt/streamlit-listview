# e2e/demo/test_demo_data_switch.py
import pytest
from playwright.sync_api import Page, expect


def _enable_accept_new_options(page: Page):
    # Accept new options lives in the Behavior section of the pills switcher. The
    # native checkbox sits hidden behind the BaseWeb switch, so click its label.
    page.get_by_role("radio", name="Behavior", exact=True).click()
    page.get_by_text("Accept new options", exact=True).click()
    expect(page.get_by_test_id("stListviewNewOption")).to_be_visible(timeout=10000)


@pytest.mark.parametrize("mode", ["single", "multi"])
def test_switching_the_data_source_drops_the_old_selection(page: Page, mode):
    """A new data source starts with an empty selection.

    With accept_new_options on, the listview keeps a selected id that left the
    options as a new entry. The demo kept one widget key across data sources, so
    a city picked before switching to Empty stayed selected, as a typed row.
    """
    page.get_by_role("radio", name=mode, exact=True).click()
    _enable_accept_new_options(page)

    listview = page.get_by_test_id("stListview").first
    berlin = listview.get_by_test_id("stListviewOption-berlin")
    berlin.click()
    expect(berlin).to_have_attribute("aria-selected", "true", timeout=10000)
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)

    page.get_by_role("radio", name="Data", exact=True).click()
    page.get_by_role("radio", name="Empty", exact=True).click()

    expect(page.get_by_text("Nothing selected yet.")).to_be_visible(timeout=10000)
    expect(
        page.get_by_test_id("stListview").first.get_by_test_id(
            "stListviewOption-berlin"
        )
    ).to_have_count(0)


def test_changing_the_large_size_drops_the_old_selection(page: Page):
    """A new Large size starts with an empty selection, as a new source does."""
    page.get_by_role("radio", name="multi", exact=True).click()
    _enable_accept_new_options(page)
    page.get_by_role("radio", name="Data", exact=True).click()
    page.get_by_role("radio", name="Large", exact=True).click()

    listview = page.get_by_test_id("stListview").first
    row = listview.get_by_test_id("stListviewOption-item-00500")
    row.click()
    expect(row).to_have_attribute("aria-selected", "true", timeout=10000)
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)

    # 1,000 -> 500 -> 100 items: item-00500 is no longer an option.
    page.get_by_role("slider").focus()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")

    expect(page.get_by_text("Nothing selected yet.")).to_be_visible(timeout=10000)
    expect(
        page.get_by_test_id("stListview").first.get_by_test_id(
            "stListviewOption-item-00500"
        )
    ).to_have_count(0)
