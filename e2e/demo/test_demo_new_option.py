# e2e/demo/test_demo_new_option.py
import re

from playwright.sync_api import Page, expect


def test_single_mode_new_option_renders_without_json_error(page: Page):
    """Regression for the st.json bare-string crash.

    The demo defaults to single selection mode. Adding a new option there makes
    listview() return the typed string (e.g. "Atlantis"). Passing a bare string
    to st.json() makes Streamlit's frontend JSON.parse() it, which throws
    "JSON.parse: unexpected character at line 1 column 1". The result panel must
    render the scalar without that error.
    """
    # Enable accept_new_options (single selection mode is the demo default).
    # The native checkbox input is visually hidden behind the BaseWeb switch, so
    # click the associated label text, which Streamlit toggles respond to.
    # Accept new options lives in the Behavior section of the pills switcher.
    page.get_by_role("radio", name="Behavior", exact=True).click()
    page.get_by_text("Accept new options", exact=True).click()

    # The new-option input now appears inside the listview component.
    new_option = page.get_by_test_id("stListviewNewOption")
    expect(new_option).to_be_visible(timeout=10000)
    new_option.fill("Atlantis")
    new_option.press("Enter")

    # The result panel reports the selection ...
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)
    # ... and no JSON parse error is rendered anywhere on the page.
    expect(page.get_by_test_id("stException")).to_have_count(0)
    expect(
        page.get_by_text(re.compile(r"JSON\.parse|Parse Error", re.IGNORECASE))
    ).to_have_count(0)
    # The typed value is surfaced (synthetic row + result panel).
    expect(page.get_by_text("Atlantis").first).to_be_visible()


def test_added_option_persists_after_picking_another_single_mode(page: Page):
    """An added option must stay in the list as a re-selectable row after a
    different option is picked (single mode replaces the selection)."""
    # Accept new options lives in the Behavior section of the pills switcher.
    page.get_by_role("radio", name="Behavior", exact=True).click()
    page.get_by_text("Accept new options", exact=True).click()

    new_option = page.get_by_test_id("stListviewNewOption")
    expect(new_option).to_be_visible(timeout=10000)
    new_option.fill("Atlantis")
    new_option.press("Enter")

    listview = page.get_by_test_id("stListview").first
    atlantis = listview.get_by_test_id("stListviewOption-Atlantis")
    # Added and selected.
    expect(atlantis).to_have_attribute("aria-selected", "true", timeout=10000)

    # Pick a different existing option; single mode replaces the selection.
    listview.get_by_test_id("stListviewOption-berlin").click()

    # Atlantis must remain in the list, now unselected and still selectable.
    expect(atlantis).to_have_attribute("aria-selected", "false")
    atlantis.click()
    expect(atlantis).to_have_attribute("aria-selected", "true")
