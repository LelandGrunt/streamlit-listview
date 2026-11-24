# e2e/test_sidebar_theme.py
"""The widget paints the right surfaces in st.sidebar.

Streamlit gives the sidebar a theme of its own. A custom theme trades the main
body's --st-background-color and --st-secondary-background-color there;
Streamlit 1.67's built-in themes give the sidebar a pair of its own (light
#f8f8f7 and #f1f0ee). Streamlit paints its open selectbox menu from the first
token in the main body and from the second in the sidebar, so a widget that
consumed either token raw would paint the wrong surface in one container.

This is the only place the stylesheet is actually executed — the unit suite can
assert what the sheet SAYS (src/__tests__/listview-css.test.ts) but not what a
browser resolves it to, and the sidebar theme comes entirely from outside this
repo. Every expectation below is therefore a comparison between two elements
measured on the same page, never a hardcoded hex: the point is that the widget
tracks whatever Streamlit's theme resolves to. Only the default themes run
here, in light; no test boots a custom [theme.sidebar].
"""

import io
from collections import Counter
from pathlib import Path
from typing import cast

from PIL import Image
from playwright.sync_api import Page, expect

APP_FILE = Path(__file__).with_name("app_sidebar_theme.py")


def _rgb(page: Page, selector: str, *, sidebar: bool) -> list[float]:
    """The resolved background of the first `selector` in one container.

    Returned as a list of plain RGB channel floats (0-255) because the computed
    value's SYNTAX varies: a straight var() resolves to "rgb(...)" while a
    color-mix() can come back as "color(srgb 0.85 0.86 0.88)". Comparing the
    strings would make the group-band assertions fail on formatting rather than
    on color. Compare two `_rgb` results against each other, never against a
    literal tuple — `page.evaluate` unmarshals the JS array as a list.
    """
    container = "stSidebar" if sidebar else "stMain"
    return cast(
        list[float],
        page.evaluate(
            """([container, selector]) => {
            const scope = document.querySelector(`[data-testid="${container}"]`);
            // Named explicitly: a collapsed sidebar (Streamlit hides it below a
            // viewport-width threshold) would otherwise surface as a null
            // dereference inside this string, which reads as a colour bug.
            if (!scope) throw new Error(`container ${container} is not rendered`);
            const host = scope.querySelector('[data-testid="stBidiComponentIsolated"]');
            // Streamlit's own widgets live in the light DOM; ours live in the
            // component's shadow root, so look in both.
            const el = scope.querySelector(selector)
                    ?? (host && host.shadowRoot.querySelector(selector));
            if (!el) throw new Error(`no ${selector} in ${container}`);
            const raw = getComputedStyle(el).backgroundColor;
            const nums = raw.match(/[\\d.]+/g).map(Number);
            // "color(srgb r g b)" is 0-1 per channel; rgb()/rgba() is 0-255.
            return raw.startsWith("color(") ? nums.slice(0, 3).map((n) => n * 255)
                                            : nums.slice(0, 3);
        }""",
            [container, selector],
        ),
    )


# Streamlit fills its selectbox control from --st-secondary-background-color in
# BOTH containers, so this locator resolves to the swapped value in the sidebar
# without the test having to know which hex that is.
SELECTBOX = '[data-testid="stSelectbox"] .react-aria-ComboBox > div'
BODY = ".listview-body"
GROUP = ".listview-group-header"
SEARCH = ".listview-search__input"
FOOTER = ".listview-footer"
ADD_FIELD = ".listview-new-option__input"


def _dataframe_header_rgb(page: Page, *, sidebar: bool) -> list[float]:
    """The fill of the st.dataframe header in one container, read from pixels.

    The grid draws on a canvas, so no computed style carries the header colour.
    The strip lies in the top part of the header row, above the column labels,
    and inside the frame's border and rounded corners; its most common colour is
    the fill.
    """
    container = "stSidebar" if sidebar else "stMain"
    grid = page.get_by_test_id(container).get_by_test_id("stDataFrame")
    expect(grid.locator("canvas").first).to_be_visible()
    image = Image.open(io.BytesIO(grid.screenshot())).convert("RGB")
    width = image.width
    strip = [
        image.getpixel((x, y))
        for y in range(4, 9)
        for x in range(width // 10, width - width // 10)
    ]
    fill = Counter(strip).most_common(1)[0][0]
    return [float(channel) for channel in cast(tuple[int, int, int], fill)]


def _near(a: list[float], b: list[float]) -> bool:
    # The canvas and the CSS engine may round a colour a unit apart.
    return all(abs(x - y) <= 2 for x, y in zip(a, b, strict=True))


def test_sidebar_list_surface_matches_the_sidebar_selectbox(page: Page):
    # THE requirement: in the sidebar the rows sit on the same fill Streamlit
    # gives its own widgets there. Before the un-swap the list came out on
    # --st-background-color (#f0f2f6 light) while the selectbox was on #ffffff,
    # so these differed by exactly the swap.
    assert _rgb(page, BODY, sidebar=True) == _rgb(page, SELECTBOX, sidebar=True)


def test_the_search_field_is_an_inset_that_never_matches_its_list(page: Page):
    # The search field is filled like st.text_input: an INSET on the list
    # surface, painted from the other background token. The sidebar paints the
    # list from the other token too, so an inset that did not swap with its
    # ground would land on the list's own colour there and vanish. Swapped as a
    # pair, it contrasts in both containers.
    for sidebar in (True, False):
        assert _rgb(page, SEARCH, sidebar=sidebar) != _rgb(page, BODY, sidebar=sidebar)


def test_the_group_band_is_the_dataframe_header_in_both_containers(page: Page):
    # The band copies the st.dataframe header, which each container resolves
    # from its own theme. It must also differ from the rows it labels; in the
    # built-in light sidebar the header (#f3f3f2) sits on rows painted like the
    # sidebar menu (#f1f0ee), a step lighter than them.
    for sidebar in (True, False):
        group = _rgb(page, GROUP, sidebar=sidebar)
        assert _near(group, _dataframe_header_rgb(page, sidebar=sidebar))
        assert group != _rgb(page, BODY, sidebar=sidebar)


def _open_menu_rgb(page: Page, *, sidebar: bool) -> list[float]:
    """The resolved background of the open st.selectbox menu in one container."""
    container = "stSidebar" if sidebar else "stMain"
    page.get_by_test_id(container).get_by_test_id("stSelectbox").locator(
        "input"
    ).click()
    menu = page.get_by_test_id("stSelectboxVirtualDropdown")
    expect(menu).to_have_count(1)
    rgb = cast(
        list[float],
        menu.evaluate(
            """(el) => getComputedStyle(el).backgroundColor
                .match(/[\\d.]+/g).map(Number).slice(0, 3)"""
        ),
    )
    page.keyboard.press("Escape")
    expect(menu).to_have_count(0)
    return rgb


def test_the_list_surface_is_the_open_menu_in_both_containers(page: Page):
    # The listview is an always-open st.selectbox menu, so its rows sit on the
    # surface that menu paints where it opens. Streamlit paints the menu from
    # --st-background-color in the main body and from
    # --st-secondary-background-color in the sidebar (StyledPopover). Under the
    # classic swap both resolve to one colour; Streamlit 1.67's built-in sidebar
    # gives the sidebar a surface pair of its own, and the two menus differ.
    for sidebar in (True, False):
        assert _rgb(page, BODY, sidebar=sidebar) == _open_menu_rgb(
            page, sidebar=sidebar
        )


def test_the_add_field_footer_paints_the_list_surface_in_both_containers(page: Page):
    # The footer is part of the list's frame, like the pinned header: it paints
    # the list surface, so the sidebar swap moves it with the body, and its field
    # stays an inset that never matches it.
    for sidebar in (True, False):
        footer = _rgb(page, FOOTER, sidebar=sidebar)
        assert footer == _rgb(page, BODY, sidebar=sidebar)
        assert _rgb(page, ADD_FIELD, sidebar=sidebar) != footer
