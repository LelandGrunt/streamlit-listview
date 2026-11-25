# e2e/test_features.py
from pathlib import Path
from typing import Any

import pytest
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
    "newopt_int": "Add a number",
    "selectall": "Bulk select",
    "sorted": "Sorted",
    "groupednew": "Grouped adds",
    "narrow_inflow": "Narrow in-flow",
    "narrow_pinned": "Narrow pinned",
    "narrow_selectall": "Narrow pinned with Select all",
    "wide_selectall": "Wide pinned with Select all",
}


def _list(page: Page, instance: str):
    """The instance's listbox, or its tree when its groups are collapsible."""
    name = _INSTANCE_NAME[instance]
    return page.get_by_role("listbox", name=name, exact=True).or_(
        page.get_by_role("tree", name=name, exact=True)
    )


def _root(page: Page, instance: str):
    """The instance's stListview root (the tests reach parts outside the
    listbox — search field, list body), found via its uniquely named list."""
    return page.get_by_test_id("stListview").filter(has=_list(page, instance))


def _header(root, group: str):
    """A group's clickable header."""
    return root.get_by_test_id("stListviewGroup").filter(has_text=group)


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


def _search_layout(root) -> dict[str, Any]:
    """The boxes of the search field and the Select all toggle, measured once
    the stylesheet applies: before it arrives the field is no flex container,
    and an unstyled input fits a narrow frame, so a measurement taken then
    would pass even with a broken layout."""
    expect(root.locator(".listview-search")).to_have_css("display", "flex")
    return root.get_by_test_id("stListviewSearch").evaluate(
        """input => {
            const part = input.closest('.listview-header, .listview-body');
            const box = input.getBoundingClientRect();
            const style = getComputedStyle(input);
            const toggle = part.querySelector('.listview-select-all');
            const t = toggle && toggle.getBoundingClientRect();
            return {
                frame: part.getBoundingClientRect().right,
                part_height: part.getBoundingClientRect().height,
                input: {right: box.right, bottom: box.bottom},
                // the width the typed text gets: the box minus its border and
                // the room the padding keeps for the glyph and the clear
                // button. Not clientWidth: Firefox's leaves an input's padding
                // out, Chromium's keeps it in.
                text_room: box.width
                    - parseFloat(style.borderLeftWidth)
                    - parseFloat(style.borderRightWidth)
                    - parseFloat(style.paddingLeft)
                    - parseFloat(style.paddingRight),
                toggle: t && {left: t.left, top: t.top, right: t.right},
            };
        }"""
    )


@pytest.mark.parametrize(
    "instance", ["narrow_inflow", "narrow_pinned", "narrow_selectall"]
)
def test_the_search_field_fits_a_narrow_frame(page: Page, instance: str):
    # The harness puts each list in a 180 px container, narrower than the
    # search input's intrinsic width. The field and the Select all toggle must
    # shrink into the part of the frame that holds them, the pinned header or
    # the scroll body, and the field must keep room for text. A pinned field
    # once kept about 230 px and ran out past the frame's right border.
    layout = _search_layout(_root(page, instance))
    controls = [layout["input"]] + ([layout["toggle"]] if layout["toggle"] else [])
    assert len(controls) == (2 if instance == "narrow_selectall" else 1)
    assert all(c["right"] <= layout["frame"] for c in controls), layout
    assert layout["text_room"] >= 48, layout  # 3rem


@pytest.mark.parametrize(
    ("instance", "wrapped"),
    [("narrow_selectall", True), ("wide_selectall", False)],
)
def test_the_select_all_toggle_moves_below_a_narrow_search_field(
    page: Page, instance: str, wrapped: bool
):
    # Beside the toggle, a 180 px frame leaves the field no room for text, so
    # the toggle takes its own line below the field there; a 300 px frame keeps
    # both on one line. The frame's width alone decides: the wider label that a
    # click brings, "Deselect all", must not move the toggle to another line,
    # or the list would shift under the pointer.
    root = _root(page, instance)
    toggle = root.get_by_test_id("stListviewSelectAllToggle")
    # Measure both layouts at one scroll position. Firefox rounds a box's
    # height by the box's place on the page, so the click that scrolled the
    # toggle into view changed part_height by 0.00002 px.
    toggle.scroll_into_view_if_needed()
    before = _search_layout(root)
    toggle.click()
    expect(toggle).to_have_text("Deselect all")
    after = _search_layout(root)

    assert after["part_height"] == before["part_height"], (before, after)
    for layout in (before, after):
        field, tog = layout["input"], layout["toggle"]
        below = tog["top"] >= field["bottom"]
        assert below == wrapped, layout
        # on one line the input ends where the toggle starts, never under it
        assert below or field["right"] <= tog["left"], layout
        assert tog["right"] <= layout["frame"], layout
        assert layout["text_room"] >= 48, layout  # 3rem


def test_collapsible_group_toggles(page: Page):
    root = _root(page, "collapsible")
    # Fish starts collapsed (collapsed_groups=["Fish"]) -> its items hidden
    expect(root.get_by_text("Salmon")).to_have_count(0)
    # expand it
    _header(root, "Fish").click()
    expect(root.get_by_text("Salmon")).to_be_visible()
    # collapse Fruit; its treeitem carries the state
    _header(root, "Fruit").click()
    expect(root.get_by_text("Apple")).to_have_count(0)
    expect(root.get_by_role("treeitem", name="Fruit")).to_have_attribute(
        "aria-expanded", "false"
    )


def test_the_keyboard_opens_and_closes_a_group(page: Page):
    # Collapsible groups make the list a tree: the headers are nodes of the
    # arrow-key order, ArrowLeft closes a group, ArrowRight opens it and steps
    # into its rows. The tree is one Tab stop; no header is a button.
    root = _root(page, "collapsible")
    tree = _list(page, "collapsible")
    expect(tree.get_by_role("button")).to_have_count(0)
    tree.focus()
    page.keyboard.press("ArrowDown")
    fruit = root.get_by_role("treeitem", name="Fruit")
    expect(tree).to_have_attribute(
        "aria-activedescendant", fruit.get_attribute("id") or ""
    )
    page.keyboard.press("ArrowLeft")
    expect(fruit).to_have_attribute("aria-expanded", "false")
    expect(root.get_by_text("Apple")).to_have_count(0)
    page.keyboard.press("ArrowRight")
    expect(fruit).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowRight")
    expect(tree).to_have_attribute("aria-activedescendant", "listview-opt-apple")
    page.keyboard.press("Enter")
    expect(root.get_by_test_id("stListviewOption-apple")).to_have_attribute(
        "aria-selected", "true"
    )
    # Fish starts closed: Enter on its header opens it
    page.keyboard.press("End")
    expect(root.get_by_role("treeitem", name="Fish")).to_have_attribute(
        "aria-expanded", "false"
    )
    page.keyboard.press("Enter")
    expect(root.get_by_text("Salmon")).to_be_visible()


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
    # Dict options: the new entry comes back as a dict, like every other option.
    expect(echo(page, "newopt")).to_contain_text("{'id': 'Mango', 'label': 'Mango'}")


def test_accept_new_options_with_int_options_returns_an_int(page: Page):
    root = _root(page, "newopt_int")
    inp = root.get_by_test_id("stListviewNewOption")
    inp.fill("42")
    inp.press("Enter")
    expect(root.get_by_test_id("stListviewOption-42")).to_have_attribute(
        "aria-selected", "true"
    )
    # An int, like every other option — not the string "42".
    expect(echo(page, "newopt_int")).to_contain_text("newopt_int_echo=[42]")


def test_accept_new_options_with_int_options_refuses_text_with_a_hint(page: Page):
    root = _root(page, "newopt_int")
    inp = root.get_by_test_id("stListviewNewOption")
    inp.fill("abc")
    inp.press("Enter")
    expect(root.get_by_test_id("stListviewNewOptionHint")).to_have_text(
        "Enter a whole number"
    )
    expect(inp).to_have_value("abc")
    expect(inp).to_have_attribute("aria-invalid", "true")
    expect(echo(page, "newopt_int")).to_contain_text("newopt_int_echo=[]")
    # The hint sits in the footer below the 100 px scroll frame, so it shows
    # without the frame having to scroll.
    expect(
        root.locator(".listview-footer").get_by_test_id("stListviewNewOptionHint")
    ).to_be_visible()
    assert root.locator(".listview-body").evaluate("el => el.scrollTop") == 0


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
    expected = [
        "Salmon",
        "Tuna",
        "Apple",
        "Banana",
        "Cherry",
        "Carrot",
        "Onion",
        "Potato",
    ]
    expect(rows).to_have_count(len(expected))
    for i, label in enumerate(expected):
        expect(rows.nth(i)).to_contain_text(label)


def test_rows_without_a_group_render_last_under_their_own_header(page: Page):
    root = _root(page, "groupednew")
    headers = root.get_by_test_id("stListviewGroup")
    expect(headers).to_have_count(4)
    expect(headers.nth(3)).to_contain_text("Other")
    rows = root.locator("[data-testid^='stListviewOption-']")
    expect(rows.last).to_contain_text("Misc")
    expect(
        root.get_by_role("group", name="Other").get_by_test_id("stListviewOption-misc")
    ).to_have_count(1)


def test_the_add_field_stays_in_place_while_the_list_scrolls(page: Page):
    root = _root(page, "groupednew")
    field = root.get_by_test_id("stListviewNewOption")
    expect(
        root.locator(".listview-footer").get_by_test_id("stListviewNewOption")
    ).to_have_count(1)
    expect(
        root.locator(".listview-body").get_by_test_id("stListviewNewOption")
    ).to_have_count(0)
    before = field.bounding_box()
    body = root.locator(".listview-body")
    body.evaluate("el => el.scrollTo(0, el.scrollHeight)")
    # the frame overflows, so the list really did scroll
    assert body.evaluate("el => el.scrollTop") > 0
    # scrolling the list moves the rows, not the field
    assert field.bounding_box() == before


def test_an_added_entry_scrolls_into_view_under_other(page: Page):
    root = _root(page, "groupednew")
    body = root.locator(".listview-body")
    body.evaluate("el => el.scrollTo(0, 0)")
    inp = root.get_by_test_id("stListviewNewOption")
    inp.fill("Mango")
    inp.press("Enter")
    # Polled: the scroll runs in a frame after the commit that renders the row.
    page.wait_for_function(
        """(body) => {
            const row = body.querySelector('[data-testid="stListviewOption-Mango"]');
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
    expect(
        root.get_by_role("group", name="Other").get_by_test_id("stListviewOption-Mango")
    ).to_have_count(1)


def test_footer_seam_stays_a_divider_while_the_frame_lights(page: Page):
    # The footer mirrors the pinned header: focus paints the control's outline
    # in the primary color, and the seam between body and footer keeps its
    # resting color as the only line there.
    root = _root(page, "groupednew")
    footer, body = root.locator(".listview-footer"), root.locator(".listview-body")
    rest = footer.evaluate("el => getComputedStyle(el).borderBottomColor")

    root.get_by_test_id("stListviewNewOption").click()
    page.wait_for_timeout(300)  # the frame's border-color transition (0.15s)

    lit = footer.evaluate(
        "el => { const s = getComputedStyle(el); return [s.borderBottomColor, s.borderLeftColor]; }"
    )
    edges = body.evaluate(
        """el => { const s = getComputedStyle(el);
            return { left: s.borderLeftColor, top: s.borderTopColor, bottomWidth: s.borderBottomWidth }; }"""
    )
    seam = footer.evaluate("el => getComputedStyle(el, '::before').backgroundColor")
    assert lit[0] != rest and lit == [lit[0], lit[0]]
    assert edges["left"] == lit[0] and edges["top"] == lit[0]
    assert seam == rest
    assert edges["bottomWidth"] == "0px"
