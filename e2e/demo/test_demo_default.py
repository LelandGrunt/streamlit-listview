# e2e/demo/test_demo_default.py
from playwright.sync_api import Page, expect

# The config panel's Default picker: the one st.selectbox whose label mentions
# "Default". The combobox trigger and the filter input live inside it.
DEFAULT_SELECTBOX = '[data-testid="stSelectbox"]:has-text("Default")'


def pick_default(page: Page, option_label: str, *, filter_first: bool = False) -> None:
    """Open the Default selectbox and pick ``option_label`` from the dropdown.

    ``filter_first`` types the label into the combobox before picking — needed
    for the Large dataset, whose 1,000-id dropdown is virtualized, so the
    target option may not exist in the DOM until filtered.
    """
    page.locator(f'{DEFAULT_SELECTBOX} [role="combobox"]').click()
    if filter_first:
        page.locator(f"{DEFAULT_SELECTBOX} input").fill(option_label)
    page.get_by_test_id("stSelectboxVirtualDropdown").get_by_role(
        "option", name=option_label, exact=True
    ).click()


def test_setting_a_default_pre_selects_it_and_shows_the_result(page: Page):
    """Choosing a Default in the config must pre-select that option AND surface
    it as the result — not leave the panel on "Nothing selected yet.".

    `default` is a mount-time parameter, so the demo must remount the widget (by
    folding it into the key) when it changes. A keyed v2 component otherwise
    updates only the *displayed* selection and keeps returning its old committed
    value, desyncing the result panel from the highlighted row.
    """
    # Pick a Default in single mode (the demo's default mode). The selectbox
    # lists option ids, so the entry is "berlin" (vs the list's "Berlin").
    pick_default(page, "berlin")

    listview = page.get_by_test_id("stListview").first
    # The row is pre-selected ...
    expect(
        listview.get_by_test_id("stListviewOption-berlin")
    ).to_have_attribute("aria-selected", "true", timeout=10000)
    # ... and the result panel reflects it instead of staying empty.
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)
    expect(page.get_by_text("Nothing selected yet.")).to_have_count(0)


def test_reset_with_a_default_configured_explains_the_re_seed(page: Page):
    """With a Default set, Reset re-seeds the list to it (not empty). The demo
    must say so, otherwise the lingering selection looks like Reset failed."""
    # Configure a Default in single mode, then confirm it took effect.
    pick_default(page, "berlin")
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)

    # Reset: the list re-seeds to berlin and an explanation appears.
    page.get_by_role("button", name="Reset selection").click()
    expect(
        page.get_by_text("re-seeded the list to the configured")
    ).to_be_visible(timeout=10000)
    # The row stays selected (re-seeded to the Default), as the message explains.
    expect(
        page.get_by_test_id("stListview").first.get_by_test_id(
            "stListviewOption-berlin"
        )
    ).to_have_attribute("aria-selected", "true", timeout=10000)


def test_default_picker_is_available_for_the_large_source(page: Page):
    """The Default picker must render for the Large generated dataset too — it
    was previously gated off there (replaced by a "disabled" caption). Switching
    the source to Large should still surface the Default selectbox, and choosing
    a generated id must pre-select that row in the live list."""
    # Switch to the Large dataset via the Data section of the pills switcher.
    page.get_by_role("radio", name="Data", exact=True).click()
    page.get_by_role("radio", name="Large", exact=True).click()
    # The Default picker lives in the Basic section — switch back to it. This also
    # exercises the off-screen state path: the picker must list the Large ids.
    page.get_by_role("radio", name="Basic", exact=True).click()

    # The Default selectbox renders instead of the old disabling caption.
    default_combo = page.locator(f'{DEFAULT_SELECTBOX} [role="combobox"]')
    expect(default_combo).to_be_visible(timeout=10000)
    expect(
        page.get_by_text("Default picker is disabled for the large dataset")
    ).to_have_count(0)

    # The picker lists generated ids; type to filter the (1,000-id) list, then
    # pick a non-first id to prove the default actually drives the selection.
    pick_default(page, "item-00042", filter_first=True)

    listview = page.get_by_test_id("stListview").first
    expect(
        listview.get_by_test_id("stListviewOption-item-00042")
    ).to_have_attribute("aria-selected", "true", timeout=15000)
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)
    expect(page.get_by_text("Nothing selected yet.")).to_have_count(0)


def test_sample_defaults_preset_loads_a_multi_value_default(page: Page):
    """The multi-mode 'Use sample defaults' button loads several pre-selected
    values at once (a list default), and Reset re-seeds to that list."""
    # Switch to multi mode, then one-click the sample-defaults preset.
    page.get_by_role("radio", name="multi", exact=True).click()
    page.get_by_role("button", name="Use sample defaults").click()

    # The live list mounts with three options pre-selected (a list default).
    expect(page.get_by_text("3 selected")).to_be_visible(timeout=10000)
    expect(
        page.get_by_test_id("stListview").first.get_by_test_id(
            "stListviewOption-berlin"
        )
    ).to_have_attribute("aria-selected", "true", timeout=10000)

    # Reset re-seeds to the configured list default and explains why.
    page.get_by_role("button", name="Reset selection").click()
    expect(
        page.get_by_text("re-seeded the list to the configured")
    ).to_be_visible(timeout=10000)
    expect(page.get_by_text("3 selected")).to_be_visible(timeout=10000)
