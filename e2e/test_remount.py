# e2e/test_remount.py
"""A keyed widget's selection survives a container move (sidebar <-> main).

Moving a keyed listview between st.sidebar and the main body keeps the
Python-side widget state (keyed element ids drop the container) but remounts
the frontend. The remounted frontend must re-seed from the persisted selection
(data["state_selection"]) rather than from `default=`: before that channel
existed, the rows re-seeded from `default` while listview() kept returning the
old value — desynced rows, and the next click silently overwrote the value.
"""
from pathlib import Path

from playwright.sync_api import Page, expect

from e2e.conftest import echo, stext

# The harness e2e/conftest.py serves for this module, with its listview
# awaited before each test.
APP_FILE = Path(__file__).with_name("app_remount.py")


def _option(page: Page, option_id: str):
    return page.get_by_test_id(f"stListviewOption-{option_id}")


def _toggle_placement(page: Page) -> None:
    page.get_by_text("Render in sidebar").click()


def test_selection_survives_container_move(page: Page):
    # First render: `default="apple"` seeds both the highlighted row and the
    # returned value; no on_change has fired.
    expect(_option(page, "apple")).to_have_attribute("aria-selected", "true")
    expect(echo(page, "remount")).to_contain_text("'id': 'apple'")
    expect(stext(page, "change_count")).to_have_text("change_count=0")

    # A real user selection: banana replaces apple, on_change fires once.
    _option(page, "banana").click()
    expect(_option(page, "banana")).to_have_attribute("aria-selected", "true")
    expect(echo(page, "remount")).to_contain_text("'id': 'banana'")
    expect(stext(page, "change_count")).to_have_text("change_count=1")

    # Move the widget into the sidebar: the frontend remounts, the Python-side
    # state survives. Await the move itself first, so the assertions below
    # cannot race the rerun and pass against the pre-move DOM.
    _toggle_placement(page)
    expect(
        page.get_by_test_id("stSidebar").get_by_role("listbox")
    ).to_have_count(1)

    # The remount re-seeded from the persisted selection, NOT from default=:
    # banana (the user's pick) is still the one selected row, the echoed value
    # is unchanged, and no on_change fired for a change no user made.
    expect(_option(page, "banana")).to_have_attribute("aria-selected", "true")
    expect(_option(page, "apple")).to_have_attribute("aria-selected", "false")
    expect(echo(page, "remount")).to_contain_text("'id': 'banana'")
    expect(stext(page, "change_count")).to_have_text("change_count=1")

    # And back to the main body: the reverse move preserves it just the same.
    _toggle_placement(page)
    expect(
        page.get_by_test_id("stSidebar").get_by_role("listbox")
    ).to_have_count(0)
    expect(page.get_by_role("listbox")).to_have_count(1)
    expect(_option(page, "banana")).to_have_attribute("aria-selected", "true")
    expect(echo(page, "remount")).to_contain_text("'id': 'banana'")
    expect(stext(page, "change_count")).to_have_text("change_count=1")

    # The widget still takes input after the moves: the next click replaces the
    # selection instead of resurrecting a stale value.
    _option(page, "carrot").click()
    expect(_option(page, "carrot")).to_have_attribute("aria-selected", "true")
    expect(echo(page, "remount")).to_contain_text("'id': 'carrot'")
    expect(stext(page, "change_count")).to_have_text("change_count=2")
