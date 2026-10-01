# e2e/demo/test_demo_empty_pickers.py
import re

import pytest
from playwright.sync_api import Page, expect

# The config pickers whose "nothing chosen" is a listview parameter left at None:
# (section pill, selectbox label, an option to pick, what the generated code
# shows for it). The single-mode Default picker follows the same rule and is
# covered in test_demo_formatting.py.
PICKERS = [
    ("Sorting", "Sort", "items", 'sort="items"'),
    ("Formatting", "Label formatting", "UPPERCASE", "format_func=fmt_upper"),
]


def wait_for_run(page: Page) -> None:
    """Wait until the rerun the last click requested has finished.

    Streamlit flips stApp's data-test-script-state on the click itself, so the
    short delay only covers the event reaching the app.
    """
    page.wait_for_timeout(100)
    expect(
        page.locator('[data-testid="stApp"][data-test-script-state="notRunning"]')
    ).to_have_count(1, timeout=15000)


@pytest.mark.parametrize(
    "section, label, option, snippet", PICKERS, ids=[p[0] for p in PICKERS]
)
def test_none_is_the_pickers_empty_state(
    page: Page, section: str, label: str, option: str, snippet: str
):
    """An empty field means the parameter is None — shown as the "— none —"
    placeholder and reached through the field's clear x, never a None entry
    among the options. A None option misrendered: on the next rerun Streamlit
    gave it a clear x of its own, which emptied the field to "Choose an option"
    while the value stayed None."""
    selectbox = page.locator(f'[data-testid="stSelectbox"]:has-text("{label}")')
    field = selectbox.locator("input")
    clear = selectbox.get_by_role("button", name=re.compile("clear", re.IGNORECASE))
    code = page.get_by_test_id("stCode").filter(has_text="selected = listview(")
    dropdown = page.get_by_test_id("stSelectboxVirtualDropdown")

    def open_section(name: str) -> None:
        page.get_by_role("radio", name=name, exact=True).click()
        wait_for_run(page)

    def pick() -> None:
        selectbox.locator('[role="combobox"]').click()
        dropdown.get_by_role("option", name=option, exact=True).click()
        wait_for_run(page)

    def expect_empty() -> None:
        expect(field).to_have_value("")
        expect(field).to_have_attribute("placeholder", "— none —")
        expect(clear).to_have_count(0)
        expect(code).not_to_contain_text(snippet)

    def expect_chosen() -> None:
        expect(field).to_have_value(option)
        expect(clear).to_have_count(1)
        expect(code).to_contain_text(snippet)

    open_section(section)
    expect_empty()

    # "— none —" is the placeholder, not something to pick.
    selectbox.locator('[role="combobox"]').click()
    expect(dropdown.get_by_role("option", name=option, exact=True)).to_be_visible()
    expect(dropdown.get_by_role("option", name="— none —")).to_have_count(0)
    page.keyboard.press("Escape")
    pick()
    expect_chosen()

    # The x goes back to None, and the field reads "— none —" again.
    clear.click()
    wait_for_run(page)
    expect_empty()

    # Both states survive leaving the section, which drops the widget's key:
    # it re-seeds from the persisted config, and a chosen value stays clearable.
    open_section("Basic")
    open_section(section)
    expect_empty()

    pick()
    open_section("Basic")
    open_section(section)
    expect_chosen()
    expect(page.get_by_test_id("stException")).to_have_count(0)


@pytest.mark.parametrize(
    "section, label, option, snippet", PICKERS, ids=[p[0] for p in PICKERS]
)
def test_a_chosen_value_survives_quick_section_switches(
    page: Page, section: str, label: str, option: str, snippet: str
):
    """Leave and re-open the section without waiting for the first rerun.

    With index=None only the key tells a remounted field its value, and only a
    key assigned in that run reaches the browser. Seeded once (setdefault), the
    one push was lost to a quick switch: the field came back empty while the
    config kept the value — and the next rerun read the empty field back.
    """
    selectbox = page.locator(f'[data-testid="stSelectbox"]:has-text("{label}")')
    code = page.get_by_test_id("stCode").filter(has_text="selected = listview(")

    page.get_by_role("radio", name=section, exact=True).click()
    wait_for_run(page)
    selectbox.locator('[role="combobox"]').click()
    page.get_by_test_id("stSelectboxVirtualDropdown").get_by_role(
        "option", name=option, exact=True
    ).click()
    wait_for_run(page)
    expect(code).to_contain_text(snippet)

    for _ in range(3):
        page.get_by_role("radio", name="Basic", exact=True).click()
        page.get_by_role("radio", name=section, exact=True).click()
        wait_for_run(page)
        expect(selectbox.locator("input")).to_have_value(option)
        expect(code).to_contain_text(snippet)
