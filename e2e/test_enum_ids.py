# e2e/test_enum_ids.py
"""A click on a row whose id subclasses str or int returns the original option.

Regression: the wrapper keyed rows by Python str(), while the frontend keys
them by the value JSON carries. A `class Color(str, Enum)` id is "Color.RED"
in Python and "red" in the browser, so a click highlighted the row while
listview() returned None.
"""

from pathlib import Path

from playwright.sync_api import Page, expect

from e2e.conftest import echo

# The harness e2e/conftest.py serves for this module, with its listviews
# awaited before each test.
APP_FILE = Path(__file__).with_name("app_enum_ids.py")


def test_a_click_returns_the_original_str_enum_option(page: Page):
    row = page.get_by_test_id("stListviewOption-red")
    row.click()
    expect(row).to_have_attribute("aria-selected", "true")
    expect(echo(page, "color")).to_have_text(
        "color_echo={'id': <Color.RED: 'red'>, 'label': 'Red'}"
    )


def test_a_click_returns_the_original_int_enum_option(page: Page):
    row = page.get_by_test_id("stListviewOption-1")
    row.click()
    expect(row).to_have_attribute("aria-selected", "true")
    expect(echo(page, "prio")).to_have_text("prio_echo=[<Prio.HIGH: 1>]")
