# e2e/demo/test_demo_theme.py
"""The Theme section re-themes the whole server, and the listview follows.

The theme is process-global (demo/themes.py) — the one piece of demo state that
is NOT per browser session — so this module must not share the demo server the
other e2e/demo modules boot: a theme left applied would leak into every module
after it. EXTRA_ENV keys a server of its own (see ``_servers`` in
e2e/conftest.py), and each test still puts the default back,
because the tests in here do share that server.

Every color is resolved by the browser on both sides of a comparison — the
theme file's hex and the listview's ``--st-*`` value run through the same probe —
so the assertions never depend on how a color happens to be spelled.
"""
import json
from pathlib import Path

import pytest
import toml
from playwright.sync_api import Page, expect

from e2e.e2e_utils import StreamlitRunner

ROOT = Path(__file__).parent.parent.parent.absolute()
THEME = "snowflake_brand"
THEMES_DIR = ROOT / "demo" / ".streamlit"
THEME_FILE = THEMES_DIR / f"config_theme_{THEME}.toml"
# The picker lists a theme under its DisplayName from config_themes.json.
THEME_LABEL = {
    entry["Name"]: entry["DisplayName"]
    for entry in json.loads(
        (THEMES_DIR / "config_themes.json").read_text(encoding="utf-8")
    )["Themes"]
}[THEME]
# Playwright's browser reports a light OS scheme, so the light variant renders.
THEME_PRIMARY = toml.load(THEME_FILE)["theme"]["light"]["primaryColor"]

# Pins the switcher on, whatever the calling shell exported (the runner hands
# the server this process's whole environment), and keys a server of its own.
EXTRA_ENV = {"LISTVIEW_DEMO_THEME_SWITCHER": "1"}

# The live listview's root in the main column (the demo renders exactly one
# there), or null mid-rerun while it is being re-rendered.
_ROOT = """(() => {
    const host = document.querySelector(
        '[data-testid="stMain"] [data-testid="stBidiComponentIsolated"]'
    );
    return host?.shadowRoot?.querySelector('[data-testid="stListview"]') ?? null;
})()"""

# Resolve a CSS color by painting a probe inside `parent` — inside the
# listview's tree that includes the `var(--st-*)` values it inherits.
_PAINT = """(parent, color) => {
    const probe = document.createElement("span");
    parent.appendChild(probe);
    probe.style.color = color;
    const resolved = getComputedStyle(probe).color;
    probe.remove();
    return resolved;
}"""

# The listview's primary color as rgb(), or null while it is not rendered.
_PRIMARY = f"""() => {{
    const root = {_ROOT};
    return root ? ({_PAINT})(root, "var(--st-primary-color)") : null;
}}"""


def wait_for_run(page: Page) -> None:
    """Wait until the rerun the last click requested has finished.

    Streamlit flips stApp's data-test-script-state on the click itself, so the
    short delay only covers the event reaching the app.
    """
    page.wait_for_timeout(100)
    expect(
        page.locator('[data-testid="stApp"][data-test-script-state="notRunning"]')
    ).to_have_count(1, timeout=15000)


def picker(page: Page):
    return page.locator('[data-testid="stSelectbox"]:has-text("Theme")')


def open_theme_section(page: Page) -> None:
    page.get_by_role("radio", name="Theme", exact=True).click()
    wait_for_run(page)


def pick_theme(page: Page, name: str) -> None:
    picker(page).locator('[role="combobox"]').click()
    page.get_by_test_id("stSelectboxVirtualDropdown").get_by_role(
        "option", name=name, exact=True
    ).click()
    wait_for_run(page)


def primary(page: Page) -> str:
    return page.evaluate(_PRIMARY)


def rgb(page: Page, color: str) -> str:
    """A literal CSS color as the browser spells it (rgb())."""
    return page.evaluate(f"(color) => ({_PAINT})(document.body, color)", color)


def font(page: Page) -> str:
    return page.evaluate(f"getComputedStyle({_ROOT}).fontFamily")


def expect_primary(page: Page, color: str) -> None:
    """Wait until the listview's primary resolves to *color* (any CSS spelling).

    The theme reaches the browser with the rerun after the switch, so poll
    rather than read once.
    """
    page.wait_for_function(
        f"(want) => ({_PRIMARY})() === want", arg=rgb(page, color), timeout=15000
    )


@pytest.fixture(autouse=True)
def back_to_the_default(page: Page, app: StreamlitRunner):
    """Leave the shared server on the Streamlit default, pass or fail."""
    yield
    page.goto(app.server_url)
    expect(page.get_by_test_id("stListview").first).to_be_visible(timeout=20000)
    open_theme_section(page)
    if picker(page).locator("input").input_value() != "Streamlit default":
        pick_theme(page, "Streamlit default")


def test_switching_the_theme_rethemes_the_listview(page: Page):
    default_primary = primary(page)
    assert default_primary != rgb(page, THEME_PRIMARY), (
        "sanity: the theme must change the primary color, or this proves nothing"
    )

    code = page.get_by_test_id("stCode").filter(has_text="selected = listview(")
    snippet = code.inner_text()
    # The switcher is a showcase, not a listview parameter, and says so in
    # either state.
    note = page.get_by_text("not part of the listview API")

    open_theme_section(page)
    # The default is an entry of its own, not an empty field: a None option
    # would render as "nothing chosen" (see test_demo_empty_pickers.py).
    expect(picker(page).locator("input")).to_have_value("Streamlit default")
    expect(note).to_be_visible()
    pick_theme(page, THEME_LABEL)

    # The listview takes no theme parameter: it inherits the --st-* variables.
    expect_primary(page, THEME_PRIMARY)
    assert "Lato" in font(page)
    # ...and the section shows the file that did it, plus when it expires.
    expect(page.get_by_test_id("stCode").filter(has_text=THEME_PRIMARY)).to_be_visible()
    expect(page.get_by_text("Falls back to")).to_be_visible()
    expect(note).to_be_visible()
    # The theme re-styles the widget without touching the call that renders it.
    expect(code).to_have_text(snippet)

    pick_theme(page, "Streamlit default")

    expect(picker(page).locator("input")).to_have_value("Streamlit default")
    expect_primary(page, default_primary)
    assert "Lato" not in font(page)


def test_the_picker_shows_the_server_theme_to_other_sessions(page: Page, app: StreamlitRunner):
    """A second tab is a second Streamlit session: it renders the theme the
    first one picked, and its picker says so instead of "Streamlit default"."""
    open_theme_section(page)
    pick_theme(page, THEME_LABEL)

    other = page.context.new_page()
    try:
        other.goto(app.server_url)
        expect(other.get_by_test_id("stListview").first).to_be_visible(timeout=20000)
        expect_primary(other, THEME_PRIMARY)
        open_theme_section(other)
        expect(picker(other).locator("input")).to_have_value(THEME_LABEL)
    finally:
        other.close()
