# e2e/demo/test_demo_custom_data.py
from playwright.sync_api import Page, expect

from e2e.demo.test_demo_default import DEFAULT_SELECTBOX
from e2e.demo.test_demo_empty_pickers import generated_code, wait_for_run


def paste_custom(page: Page, text: str) -> None:
    """Open Data ▸ Custom and commit ``text`` as the pasted options."""
    page.get_by_role("radio", name="Data", exact=True).click()
    page.get_by_role("radio", name="Custom", exact=True).click()
    wait_for_run(page)
    options = page.get_by_role("textbox", name="Options")
    options.fill(text)
    options.press("Control+Enter")
    wait_for_run(page)


def test_a_malformed_group_shows_the_listview_error(page: Page):
    """A pasted list group used to crash the demo with a TypeError traceback
    while it derived the Group pickers, before listview() could reject the
    option with its own message. The message shows, the config panel keeps
    working, and corrected data renders the widget again."""
    paste_custom(page, '[{"id": "x", "label": "X", "group": []}]')

    expect(page.get_by_text("listview raised:")).to_be_visible(timeout=10000)
    expect(page.get_by_text("'group' must be a str")).to_be_visible()
    expect(page.get_by_test_id("stException")).to_have_count(0)

    page.get_by_role("radio", name="Groups", exact=True).click()
    wait_for_run(page)
    page.get_by_role("radio", name="Basic", exact=True).click()
    wait_for_run(page)
    expect(page.get_by_test_id("stException")).to_have_count(0)

    paste_custom(page, '[{"id": "x", "label": "X", "group": "G"}]')
    expect(
        page.get_by_test_id("stListview").first.get_by_test_id("stListviewOption-x")
    ).to_be_visible(timeout=10000)
    expect(page.get_by_text("listview raised:")).to_have_count(0)


def test_an_empty_string_default_reaches_the_generated_code(page: Page):
    """The empty string is a valid id, so it is a valid single-mode default.
    The generated code dropped it like an empty placeholder, and the copied
    call started with nothing selected."""
    paste_custom(
        page,
        '[{"id": "", "label": "Empty id"}, {"id": "a", "label": "Alternate"}]',
    )
    page.get_by_role("radio", name="Basic", exact=True).click()
    wait_for_run(page)
    page.locator(f'{DEFAULT_SELECTBOX} [role="combobox"]').click()
    # The ids are "" and "a"; the empty one is the first entry.
    page.get_by_test_id("stSelectboxVirtualDropdown").get_by_role(
        "option"
    ).first.click()
    wait_for_run(page)

    listview = page.get_by_test_id("stListview").first
    expect(listview.get_by_role("option", name="Empty id")).to_have_attribute(
        "aria-selected", "true", timeout=10000
    )
    expect(page.get_by_text("1 selected")).to_be_visible()
    code = generated_code(page)
    expect(code).to_contain_text('default="",')
