# e2e/demo/test_demo_formatting.py
import re

from playwright.sync_api import Page, expect

from e2e.demo.test_demo_default import DEFAULT_SELECTBOX, pick_default

# The Formatting section's preset picker: the one st.selectbox whose label
# mentions "Label formatting".
PRESET_SELECTBOX = '[data-testid="stSelectbox"]:has-text("Label formatting")'
INERT_WARNING = "has no effect here"


def pick_preset(page: Page, preset: str) -> None:
    """Open the Formatting section and choose ``preset`` as the format_func."""
    page.get_by_role("radio", name="Formatting", exact=True).click()
    page.locator(f'{PRESET_SELECTBOX} [role="combobox"]').click()
    page.get_by_test_id("stSelectboxVirtualDropdown").get_by_role(
        "option", name=preset, exact=True
    ).click()


def test_inert_preset_warns_and_one_click_loads_label_free_rows(page: Page):
    """Every built-in city carries an explicit `label`, which wins over
    format_func — so a preset picked there changes nothing on screen. The demo
    must say so plainly, and its one-click example must show the preset working."""
    listview = page.get_by_test_id("stListview").first
    expect(page.get_by_text(INERT_WARNING)).to_have_count(0)

    pick_preset(page, "UPPERCASE")

    # The row keeps its explicit label, and the demo explains why.
    expect(listview.get_by_test_id("stListviewOption-berlin")).to_have_text(
        "Berlin", timeout=10000
    )
    expect(page.get_by_text(INERT_WARNING)).to_be_visible(timeout=10000)

    page.get_by_role("button", name="Load an example without labels").click()

    # Label-less rows: the preset now labels every one of them ...
    expect(listview.get_by_test_id("stListviewOption-orders")).to_have_text(
        "ORDERS", timeout=10000
    )
    expect(listview.get_by_test_id("stListviewOption-orders_view")).to_have_text(
        "ORDERS_VIEW"
    )
    # ... so the warning is gone, and the Data section reflects the switch.
    expect(page.get_by_text(INERT_WARNING)).to_have_count(0)
    page.get_by_role("radio", name="Data", exact=True).click()
    expect(page.get_by_role("radio", name="Custom", exact=True)).to_have_attribute(
        "aria-checked", "true"
    )
    expect(page.get_by_role("textbox", name="Options")).to_have_value(
        '[\n  {"id": "orders", "text": "Orders", "type": "Table"},\n'
        '  {"id": "orders_view", "text": "OrdersView", "type": "View"}\n]'
    )


def test_pasted_options_with_labels_also_warn(page: Page):
    """The warning asks listview whether the preset reached any option, so it
    covers pasted data too — not only the sources known to carry labels. With
    the Data section open, the example replaces the paste in the live text area."""
    listview = page.get_by_test_id("stListview").first
    pick_preset(page, "Bullet prefix")
    page.get_by_role("radio", name="Data", exact=True).click()
    page.get_by_role("radio", name="Custom", exact=True).click()
    # The name ends there: the icon's ligature text leads it, and the two
    # sibling buttons ("... with Payload", "... with fields") extend it.
    page.get_by_role("button", name=re.compile(r"Insert example$")).click()

    expect(listview.get_by_test_id("stListviewOption-berlin")).to_have_text(
        "Berlin", timeout=10000
    )
    expect(page.get_by_text(INERT_WARNING)).to_be_visible(timeout=10000)

    page.get_by_role("button", name="Load an example without labels").click()

    expect(listview.get_by_test_id("stListviewOption-orders")).to_have_text(
        "● orders", timeout=10000
    )
    expect(page.get_by_role("textbox", name="Options")).to_have_value(
        re.compile(r'"id": "orders_view"')
    )
    expect(page.get_by_text(INERT_WARNING)).to_have_count(0)


def test_loading_the_example_with_basic_open_drops_the_stale_default(page: Page):
    """The load button sits beside the live widget, so it can swap the options
    while the Basic section — and its single-mode Default picker — is on
    screen. A Default naming a built-in city must not survive into a dataset
    that has no such row: the picker falls back to its "— none —" empty state
    (it used to go blank, because the demo's None option pushed as "no
    selection"), and a Default picked from the example's ids still takes
    effect and can be cleared again."""
    listview = page.get_by_test_id("stListview").first
    default_input = page.locator(f"{DEFAULT_SELECTBOX} input")
    pick_default(page, "berlin")
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)
    pick_preset(page, "UPPERCASE")
    page.get_by_role("radio", name="Basic", exact=True).click()
    expect(default_input).to_have_value("berlin")

    page.get_by_role("button", name="Load an example without labels").click()

    expect(listview.get_by_test_id("stListviewOption-orders")).to_have_text(
        "ORDERS", timeout=10000
    )
    expect(default_input).to_have_value("")
    expect(default_input).to_have_attribute("placeholder", "— none —")
    expect(page.get_by_text("Nothing selected yet.")).to_be_visible()
    expect(page.get_by_test_id("stException")).to_have_count(0)

    pick_default(page, "orders_view")
    expect(
        listview.get_by_test_id("stListviewOption-orders_view")
    ).to_have_attribute("aria-selected", "true", timeout=10000)

    # "No default" is the picker's own clear action now, not a list entry.
    page.locator(DEFAULT_SELECTBOX).get_by_role(
        "button", name=re.compile("clear", re.IGNORECASE)
    ).click()
    expect(default_input).to_have_value("")
    expect(page.get_by_text("Nothing selected yet.")).to_be_visible(timeout=10000)
