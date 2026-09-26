# e2e/test_core.py
from pathlib import Path

from playwright.sync_api import Page, expect

from e2e.conftest import echo

# The harness e2e/conftest.py serves for this module, with all its listviews
# awaited before each test.
APP_FILE = Path(__file__).with_name("app.py")

# A deliberately non-default primary color so the theming assertion is unambiguous.
THEME_PRIMARY = "#ff00aa"
EXTRA_ARGS = [f"--theme.primaryColor={THEME_PRIMARY}"]


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# Accessible names of the keyed listviews in app.py: each harness label names
# its listbox via aria-labelledby, so instances are selected by name and a
# listview added to the harness never shifts these.
_INSTANCE_NAME = {
    "single": "Pick one",
    "multi": "Pick several",
    "default": "Pick one (pre-seeded)",
}


def _listview(page: Page, instance: str):
    """Return the listbox container for the single/multi/default instance.

    Selected by accessible name — role=listbox pierces the open shadow DOM.
    exact=True because name= substring-matches by default and "Pick one"
    prefixes "Pick one (pre-seeded)".
    """
    return page.get_by_role("listbox", name=_INSTANCE_NAME[instance], exact=True)


def _option(page: Page, instance: str, option_id: str):
    return _listview(page, instance).get_by_test_id(f"stListviewOption-{option_id}")


def test_single_selection_updates_echoed_value(page: Page):
    """Clicking an option in single mode echoes that option's id back to Python."""
    expect(echo(page, "single")).to_have_text("single_echo=None")

    _option(page, "single", "apple").click()
    expect(_option(page, "single", "apple")).to_have_attribute("aria-selected", "true")
    # Return value is the original dict option, so its repr contains the id.
    expect(echo(page, "single")).to_contain_text("'id': 'apple'")

    # Selecting another option replaces the first (single semantics).
    _option(page, "single", "banana").click()
    expect(_option(page, "single", "apple")).to_have_attribute("aria-selected", "false")
    expect(_option(page, "single", "banana")).to_have_attribute("aria-selected", "true")
    expect(echo(page, "single")).to_contain_text("'id': 'banana'")

    # Clicking the selected option again deselects it -> None.
    _option(page, "single", "banana").click()
    expect(_option(page, "single", "banana")).to_have_attribute("aria-selected", "false")
    expect(echo(page, "single")).to_have_text("single_echo=None")


def test_multi_selection_toggles(page: Page):
    """Multi mode toggles each option independently and echoes a list."""
    expect(echo(page, "multi")).to_have_text("multi_echo=[]")

    _option(page, "multi", "apple").click()
    _option(page, "multi", "carrot").click()
    expect(_option(page, "multi", "apple")).to_have_attribute("aria-selected", "true")
    expect(_option(page, "multi", "carrot")).to_have_attribute("aria-selected", "true")
    expect(_listview(page, "multi").locator('[aria-selected="true"]')).to_have_count(2)
    multi_echo = echo(page, "multi")
    expect(multi_echo).to_contain_text("'id': 'apple'")
    expect(multi_echo).to_contain_text("'id': 'carrot'")

    # Toggling apple off leaves only carrot.
    _option(page, "multi", "apple").click()
    expect(_option(page, "multi", "apple")).to_have_attribute("aria-selected", "false")
    expect(_listview(page, "multi").locator('[aria-selected="true"]')).to_have_count(1)
    multi_echo = echo(page, "multi")
    expect(multi_echo).not_to_contain_text("'id': 'apple'")
    expect(multi_echo).to_contain_text("'id': 'carrot'")


def test_disabled_item_is_inert(page: Page):
    """A disabled option never selects and never changes the echoed value."""
    cherry = _option(page, "single", "cherry")
    expect(cherry).to_have_attribute("aria-disabled", "true")
    expect(echo(page, "single")).to_have_text("single_echo=None")

    cherry.click(force=True)  # force past pointer-events:none if styled that way

    expect(cherry).to_have_attribute("aria-selected", "false")
    expect(echo(page, "single")).to_have_text("single_echo=None")


def test_default_seeded_selection_and_highlight_agree(page: Page):
    """A default= seeded single listview highlights the seeded row on first render
    AND echoes the same option back to Python — the two must agree."""
    # Highlighted row on first render is 'banana' (the seeded default).
    expect(_option(page, "default", "banana")).to_have_attribute(
        "aria-selected", "true"
    )
    # Exactly one row is selected.
    expect(
        _listview(page, "default").locator('[aria-selected="true"]')
    ).to_have_count(1)
    # The Python-echoed return value agrees with the highlighted row.
    expect(echo(page, "default")).to_contain_text("'id': 'banana'")


def test_theme_primary_color_is_applied(page: Page):
    """The configured --theme.primaryColor resolves to --st-primary-color on the component."""
    root = page.get_by_test_id("stListview").first
    value = root.evaluate(
        "el => getComputedStyle(el).getPropertyValue('--st-primary-color').trim()"
    )
    assert value, "--st-primary-color is not set on the listview root"

    # Normalize the resolved color (rgb/hex) and compare to the configured primary.
    r, g, b = _rgb(THEME_PRIMARY)
    normalized = value.replace(" ", "").lower()
    hex_form = "#{:02x}{:02x}{:02x}".format(r, g, b)
    rgb_form = f"rgb({r},{g},{b})"
    assert normalized in (hex_form, rgb_form), (
        f"--st-primary-color={value!r} does not match configured {THEME_PRIMARY!r}"
    )


def test_keyboard_arrowdown_enter_selects(page: Page):
    """Focusing the list (without clicking a row), ArrowDown to the first option,
    Enter selects exactly that option."""
    listbox = _listview(page, "single")
    expect(echo(page, "single")).to_have_text("single_echo=None")

    # Focus the listbox WITHOUT clicking a row (a center click in a 200px list
    # would land on an option and pre-toggle a selection).
    listbox.focus()
    # ArrowDown moves focus onto the first selectable option ('apple'); Enter selects it.
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")

    # Exactly one option is selected, and it is specifically 'apple' — so the test
    # fails loudly if a stray interaction pre-selected a different row.
    selected = listbox.locator('[role="option"][aria-selected="true"]')
    expect(selected).to_have_count(1)
    expect(_option(page, "single", "apple")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(echo(page, "single")).to_contain_text("'id': 'apple'")
