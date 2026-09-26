# e2e/test_features.py
from pathlib import Path

from playwright.sync_api import Page, expect

from e2e.conftest import echo, stext

# The harness e2e/conftest.py serves for this module.
APP_FILE = Path(__file__).with_name("app_features.py")

# Accessible names of the keyed listviews in app_features.py: each harness
# label names its listbox via aria-labelledby, so instances are selected by
# name and a listview added to the harness never shifts these.
_INSTANCE_NAME = {
    "search": "Search me",
    "pinned": "Pinned search",
    "collapsible": "Collapse me",
    "jump": "Jump",
    "newopt": "Add your own",
    "selectall": "Bulk select",
    "sorted": "Sorted",
}


def _root(page: Page, instance: str):
    """The instance's stListview root (the tests reach parts outside the
    listbox — search field, list body), found via its uniquely named listbox."""
    return page.get_by_test_id("stListview").filter(
        has=page.get_by_role("listbox", name=_INSTANCE_NAME[instance], exact=True)
    )


def test_search_filters_items(page: Page):
    root = _root(page, "search")
    root.get_by_test_id("stListviewSearch").fill("car")
    expect(root.get_by_text("Carrot")).to_be_visible()
    expect(root.get_by_text("Apple")).to_have_count(0)


def test_pinned_search_stays_visible_while_scrolling(page: Page):
    root = _root(page, "pinned")
    search = root.get_by_test_id("stListviewSearch")
    expect(search).to_be_visible()
    # scroll the body; the pinned field is outside the scroll frame, still visible
    root.locator(".listview-body").evaluate("el => el.scrollTo(0, el.scrollHeight)")
    expect(search).to_be_visible()


def test_pinned_header_seam_stays_a_divider_while_the_frame_lights(page: Page):
    # The pinned header and the scroll body are ONE control drawn as two boxes.
    # Focus paints that control's outline in the primary color — and the seam
    # between the boxes used to be the body's top border, so it lit up with the
    # outline: a primary line straight through the middle of the control. The
    # seam must keep its resting divider color, and it must be the only line
    # there: a body top border left in place would light up right under it.
    root = _root(page, "pinned")
    header, body = root.locator(".listview-header"), root.locator(".listview-body")
    rest = header.evaluate("el => getComputedStyle(el).borderTopColor")

    root.get_by_test_id("stListviewSearch").click()
    page.wait_for_timeout(300)  # the frame's border-color transition (0.15s)

    lit = header.evaluate(
        "el => { const s = getComputedStyle(el); return [s.borderTopColor, s.borderLeftColor]; }"
    )
    edges = body.evaluate(
        """el => { const s = getComputedStyle(el);
            return { left: s.borderLeftColor, bottom: s.borderBottomColor, topWidth: s.borderTopWidth }; }"""
    )
    seam = header.evaluate("el => getComputedStyle(el, '::after').backgroundColor")
    # the outline lit up around both boxes...
    assert lit[0] != rest and lit == [lit[0], lit[0]]
    assert edges["left"] == lit[0] and edges["bottom"] == lit[0]
    # ...while the seam kept the resting divider color, as the only line there
    assert seam == rest
    assert edges["topWidth"] == "0px"


def test_collapsible_group_toggles(page: Page):
    root = _root(page, "collapsible")
    # Fish starts collapsed (collapsed_groups=["Fish"]) -> its items hidden
    expect(root.get_by_text("Salmon")).to_have_count(0)
    # expand it
    root.get_by_role("button", name="Fish").click()
    expect(root.get_by_text("Salmon")).to_be_visible()
    # collapse Fruit
    root.get_by_role("button", name="Fruit").click()
    expect(root.get_by_text("Apple")).to_have_count(0)


def test_search_overrides_collapse(page: Page):
    root = _root(page, "collapsible")
    # Salmon is in the collapsed Fish group; searching for it reveals the item
    # even though the group is collapsed.
    root.get_by_test_id("stListviewSearch").fill("salmon")
    expect(root.get_by_text("Salmon")).to_be_visible()


def test_jump_scrolls_default_into_view(page: Page):
    root = _root(page, "jump")
    # "tuna" is the last item in a short (140px) list, so reaching it proves the
    # jump scrolled. It scrolls THE LIST BODY ONLY (container-relative scrollTop
    # math) — Element.scrollIntoView would also scroll every scrollable ancestor
    # and yank the host page away from whatever the user was reading — so the
    # proof is a non-zero body scrollTop plus the row lying inside the body's
    # frame, NOT to_be_in_viewport(): this listview is the 4th of 7 on the page
    # and stays below the fold. Polled, because the jump runs in a rAF after the
    # first commit; the tolerance absorbs subpixel row heights.
    body = root.locator(".listview-body")
    page.wait_for_function(
        """(body) => {
            const row = body.querySelector('[data-testid="stListviewOption-tuna"]');
            if (!row) return false;
            const frame = body.getBoundingClientRect();
            const box = row.getBoundingClientRect();
            return (
                body.scrollTop > 0 &&
                box.top >= frame.top - 1 &&
                box.bottom <= frame.bottom + 1
            );
        }""",
        arg=body.element_handle(),
    )


def test_accept_new_options_adds_and_selects(page: Page):
    root = _root(page, "newopt")
    inp = root.get_by_test_id("stListviewNewOption")
    inp.fill("Mango")
    inp.press("Enter")
    expect(root.get_by_text("Mango")).to_be_visible()
    expect(echo(page, "newopt")).to_contain_text("Mango")


def test_select_all_selects_all_visible_and_flips_label(page: Page):
    root = _root(page, "selectall")
    toggle = root.get_by_test_id("stListviewSelectAllToggle")
    expect(toggle).to_have_text("Select all")
    toggle.click()
    # every matching row becomes selected
    expect(root.get_by_test_id("stListviewOption-apple")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(root.get_by_test_id("stListviewOption-banana")).to_have_attribute(
        "aria-selected", "true"
    )
    # label flips to Deselect all
    expect(toggle).to_have_text("Deselect all")
    # committed once: the echoed selection now lists the ids ...
    expect(echo(page, "selectall")).to_contain_text("'apple'")
    expect(echo(page, "selectall")).to_contain_text("'banana'")
    # ... and exactly one rerun fired for the single click (spec §10).
    expect(stext(page, "selectall_runs")).to_have_text("selectall_runs=1")


def test_select_all_with_search_scopes_to_matches(page: Page):
    root = _root(page, "selectall")
    search = root.get_by_test_id("stListviewSearch")
    search.fill("Apple")  # filters to only id apple
    root.get_by_test_id("stListviewSelectAllToggle").click()
    # the echo carries apple only (the single visible match)
    expect(echo(page, "selectall")).to_contain_text("'apple'")
    expect(echo(page, "selectall")).not_to_contain_text("'banana'")
    # clear search: previously out-of-scope rows are revealed and still unselected
    search.fill("")
    expect(root.get_by_test_id("stListviewOption-banana")).to_have_attribute(
        "aria-selected", "false"
    )


def test_deselect_all_preserves_out_of_view_selection(page: Page):
    root = _root(page, "selectall")
    # select everything first
    toggle = root.get_by_test_id("stListviewSelectAllToggle")
    toggle.click()
    expect(toggle).to_have_text("Deselect all")
    # filter to a single match, then Deselect all only that match
    search = root.get_by_test_id("stListviewSearch")
    search.fill("Apple")
    root.get_by_test_id("stListviewSelectAllToggle").click()
    # the out-of-view id (banana) is preserved in the echoed selection
    expect(echo(page, "selectall")).to_contain_text("'banana'")


def test_sort_orders_groups_and_items(page: Page):
    root = _root(page, "sorted")
    rows = root.locator("[data-testid^='stListviewOption-']")
    # OPTIONS groups Fruit/Vegetable/Fish with out-of-order items; sort="both"
    # ascending => groups Fish, Fruit, Vegetable; items sorted within each.
    expected = ["Salmon", "Tuna", "Apple", "Banana", "Cherry", "Carrot", "Onion", "Potato"]
    expect(rows).to_have_count(len(expected))
    for i, label in enumerate(expected):
        expect(rows.nth(i)).to_contain_text(label)
