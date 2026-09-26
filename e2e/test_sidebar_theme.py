# e2e/test_sidebar_theme.py
"""The widget paints the right surfaces in st.sidebar.

Streamlit's sidebar ThemeProvider swaps --st-background-color with
--st-secondary-background-color and changes no other color. Consumed raw that
inverts the widget there: rows land on the group-header surface and the headers
on the row surface, so the list stops matching the st.selectbox beside it.

This is the only place the stylesheet is actually executed — the unit suite can
assert what the sheet SAYS (src/__tests__/listview-css.test.ts) but not what a
browser resolves it to, and the swap happens entirely outside this repo. Every
expectation below is therefore a comparison between two elements measured on
the same page, never a hardcoded hex: the point is that the widget tracks
whatever Streamlit's theme resolves to, including a custom [theme.sidebar].

LIGHT THEME ONLY (this module deliberately sets no EXTRA_ARGS). The brightness
assertion below encodes "the group band is DARKER than the rows", which is a
light-theme fact: the band is Streamlit's bgMix, the midpoint of the two
background tokens, so under a dark theme it is correctly LIGHTER than the rows
(#1a1c24 on #0e1117). Adding `EXTRA_ARGS = ["--theme.base", "dark"]` here
would fail it against a widget that is behaving exactly as designed — flip
the comparison, don't "fix" the stylesheet.
"""
from pathlib import Path

from playwright.sync_api import Page

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
    return page.evaluate(
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
    )


# Streamlit fills its selectbox control from --st-secondary-background-color in
# BOTH containers, so this locator resolves to the swapped value in the sidebar
# without the test having to know which hex that is.
SELECTBOX = '[data-testid="stSelectbox"] .react-aria-ComboBox > div'
BODY = ".listview-body"
GROUP = ".listview-group-header"
SEARCH = ".listview-search__input"


def _luma(rgb: list[float]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_sidebar_list_surface_matches_the_sidebar_selectbox(page: Page):
    # THE requirement: in the sidebar the rows sit on the same fill Streamlit
    # gives its own widgets there. Before the un-swap the list came out on
    # --st-background-color (#f0f2f6 light) while the selectbox was on #ffffff,
    # so these differed by exactly the swap.
    assert _rgb(page, BODY, sidebar=True) == _rgb(page, SELECTBOX, sidebar=True)


def test_the_search_field_is_an_inset_that_never_matches_its_list(page: Page):
    # The search field is filled like st.text_input: an INSET on the list
    # surface, painted from the other background token. The sidebar swaps the
    # tokens, so an inset that did not swap with its ground would land on the
    # list's own colour there and vanish. Swapped as a pair, it contrasts in both
    # containers and keeps one colour across them, like the list itself.
    for sidebar in (True, False):
        assert _rgb(page, SEARCH, sidebar=sidebar) != _rgb(page, BODY, sidebar=sidebar)
    assert _rgb(page, SEARCH, sidebar=True) == _rgb(page, SEARCH, sidebar=False)


def test_sidebar_group_header_is_a_darker_band_than_the_rows(page: Page):
    # The headers must read as a band ON the list, not as holes in it. The bug
    # this pins is the inversion: pre-fix the sidebar group header was #ffffff
    # against #f0f2f6 rows, i.e. LIGHTER than the content it labels.
    rows = _rgb(page, BODY, sidebar=True)
    group = _rgb(page, GROUP, sidebar=True)
    assert group != rows
    assert _luma(group) < _luma(rows)


def test_the_list_looks_the_same_in_both_containers(page: Page):
    # Streamlit's own dropdown menu paints the app-level background wherever it
    # opens, and the listview is an always-open menu. Equality across containers
    # is the invariant the swap used to break; it is also what keeps a widget
    # moved into the sidebar from changing color under the user. The group band
    # is Streamlit's bgMix, the midpoint of the two swapped tokens — symmetric,
    # so the swap cannot move it either.
    assert _rgb(page, BODY, sidebar=True) == _rgb(page, BODY, sidebar=False)
    assert _rgb(page, GROUP, sidebar=True) == _rgb(page, GROUP, sidebar=False)
