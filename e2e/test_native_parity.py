# e2e/test_native_parity.py
"""The listview paints what the native widget it mirrors paints.

The list is an always-open st.selectbox menu, so each of its states has a
Streamlit reference rendered on the same page (e2e/app_native_parity.py):

    row hover             the open selectbox menu's option highlight
    selected row          an active st.pills
    search field          st.text_input
    focused frame         a focused st.selectbox

Every expectation compares two elements measured on the same page, never a
hardcoded hex, so the module is theme-agnostic: test_native_parity_dark.py
re-collects it under the dark theme, where the highlight formula takes its
other branch (Streamlit lightens bgMix there instead of darkening it).
"""
import re
from pathlib import Path

from playwright.sync_api import Locator, Page, expect

APP_FILE = Path(__file__).with_name("app_native_parity.py")

# Computed colours arrive in whatever syntax produced them — rgb()/rgba() for a
# plain var(), "color(srgb r g b / a)" (0-1 channels) for color-mix() or a
# relative colour — so they are normalised to [r, g, b, a] with 0-255 channels
# before any comparison. Strings would fail on formatting rather than colour.
_STYLE = r"""(el, pseudo) => {
  const parse = (raw) => {
    const n = raw.match(/[\d.]+/g).map(Number);
    const rgb = raw.startsWith('color(') ? n.slice(0, 3).map((v) => v * 255) : n.slice(0, 3);
    return [...rgb, n.length > 3 ? n[3] : 1];
  };
  const s = getComputedStyle(el, pseudo);
  return {
    bg: parse(s.backgroundColor),
    fg: parse(s.color),
    border: parse(s.borderTopColor),
    ring: s.boxShadow,
    outline: s.outlineStyle,
    widths: [s.borderTopWidth, s.borderLeftWidth, s.borderBottomWidth],
  };
}"""

# The highlight is REPRODUCED from Streamlit's theme formula in CSS (relative
# colour syntax) rather than read from a token, so it may land a unit or two off
# Streamlit's own JS rounding. Anything beyond that is a different colour.
_CHANNEL_TOLERANCE = 3
_ALPHA_TOLERANCE = 0.02


def _style(locator: Locator, pseudo: str | None = None) -> dict:
    return locator.evaluate(_STYLE, pseudo)


def _close(a: list[float], b: list[float]) -> bool:
    return (
        all(abs(x - y) <= _CHANNEL_TOLERANCE for x, y in zip(a[:3], b[:3]))
        and abs(a[3] - b[3]) <= _ALPHA_TOLERANCE
    )


def _row(page: Page, option_id: str) -> Locator:
    return page.get_by_test_id(f"stListviewOption-{option_id}")


def _listbox(page: Page) -> Locator:
    return page.get_by_role("listbox", name="Parity list")


def _body(page: Page) -> Locator:
    return page.locator(".listview-body")


def _settle(page: Page) -> None:
    # Both the listview frame (border-color 0.15s) and the menu highlight
    # (background 50ms) transition; reading mid-transition compares a blend.
    page.wait_for_timeout(300)


def test_row_hover_is_the_selectbox_menus_highlight(page: Page):
    page.get_by_test_id("stSelectbox").locator("input").click()
    menu = page.get_by_test_id("stSelectboxVirtualDropdown")
    menu.get_by_role("option", name="Carrot").hover()
    highlight = menu.locator('[role="option"][data-hovered] [data-item-hl]')
    expect(highlight).to_have_count(1)
    _settle(page)
    native = _style(highlight)["bg"]
    page.keyboard.press("Escape")
    expect(menu).to_have_count(0)

    _row(page, "carrot").hover()
    _settle(page)
    assert _close(_style(_row(page, "carrot"), "::before")["bg"], native)


def test_a_selected_row_looks_like_an_active_pill(page: Page):
    active = _style(page.get_by_test_id("stButtonGroup").locator("button", has_text="Banana"))
    row = _row(page, "banana")
    expect(row).to_have_attribute("aria-selected", "true")
    assert _close(_style(row, "::before")["bg"], active["bg"])
    assert _close(_style(row)["fg"], active["fg"])


def test_the_search_field_is_filled_like_st_text_input(page: Page):
    native = _style(page.get_by_test_id("stTextInputRootElement"))
    search = _style(page.get_by_test_id("stListviewSearch"))
    assert _close(search["bg"], native["bg"])
    # ...and, like the native field, its 1px edge is its own fill colour.
    assert _close(native["border"], native["bg"])
    assert _close(search["border"], search["bg"])


def test_a_click_below_the_last_row_focuses_the_list(page: Page):
    # The reference: the frame colour of a focused st.selectbox.
    page.get_by_test_id("stSelectbox").locator("input").click()
    _settle(page)
    focused = _style(page.get_by_test_id("stSelectbox").locator(".react-aria-ComboBox > div"))["border"]
    page.keyboard.press("Escape")
    page.mouse.click(5, 360)  # page margin: moves focus nowhere
    _settle(page)

    # The list sits below the references, partly under the fold at the default
    # viewport; mouse.click takes viewport coordinates and does not scroll.
    _body(page).scroll_into_view_if_needed()
    body = _body(page).bounding_box()
    rows = _listbox(page).bounding_box()
    below = rows["y"] + rows["height"]
    # The harness list is shorter than its height; without that gap this test
    # would click a row and prove nothing.
    assert body["y"] + body["height"] - below > 40
    x, y = body["x"] + body["width"] / 2, (below + body["y"] + body["height"]) / 2
    # ...and the point really is the frame's own empty space, not a child.
    hit = page.evaluate(
        """([x, y]) => document.querySelector('[data-testid="stBidiComponentIsolated"]')
            .shadowRoot.elementFromPoint(x, y)?.className""",
        [x, y],
    )
    assert hit == "listview-body"
    page.mouse.click(x, y)
    _settle(page)
    assert _listbox(page).evaluate("(el) => el.matches(':focus')")
    assert _close(_style(_body(page))["border"], focused)


def test_hovering_or_scrolling_the_list_leaves_its_frame_alone(page: Page):
    # Streamlit colours an input's frame for FOCUS only; hover and wheel scroll
    # leave every native field's frame untouched, and so must the list.
    rest = _style(_body(page))["border"]
    _body(page).hover()
    page.mouse.wheel(0, 120)
    _settle(page)
    assert _close(_style(_body(page))["border"], rest)


def test_a_clicked_row_carries_no_focus_ring(page: Page):
    row = _row(page, "apple")
    row.click()
    # the click DID move the active descendant — the ring is what must not follow
    expect(row).to_have_class(re.compile(r"\blistview-item--focused\b"))
    assert _style(row, "::before")["ring"] == "none"
    assert _style(row)["outline"] == "none"


def test_keyboard_focus_rings_the_row_not_the_listbox(page: Page):
    page.get_by_test_id("stListviewSearch").click()
    page.keyboard.press("Tab")
    assert _listbox(page).evaluate("(el) => el.matches(':focus-visible')")
    page.keyboard.press("ArrowDown")
    focused = page.locator(".listview-item--focused")
    expect(focused).to_have_count(1)
    assert _style(focused, "::before")["ring"] != "none"
    # the browser's own outline would draw a second, unthemed hairline
    assert _style(_listbox(page))["outline"] == "none"


def test_collapsible_group_headers_draw_no_button_border(page: Page):
    headers = page.locator("button.listview-group-header")
    expect(headers).to_have_count(2)
    for header in headers.all():
        assert _style(header)["widths"] == ["0px", "0px", "1px"]
