# e2e/demo/test_demo_reset.py
from playwright.sync_api import Page, expect


def test_reset_clears_the_frontend_selection_not_only_the_result(page: Page):
    """Reset must clear the listview's own highlighted rows, not just the result.

    The component keeps its selection in frontend React state, so a reset that
    only pops the Python-side widget value leaves the rows visually selected
    (result panel says "Nothing selected" while Berlin is still highlighted).
    The fix remounts the widget by bumping a nonce in its key.
    """
    listview = page.get_by_test_id("stListview").first
    listview.get_by_test_id("stListviewOption-berlin").click()

    # Selected: row highlighted and result panel reports it.
    expect(
        listview.get_by_test_id("stListviewOption-berlin")
    ).to_have_attribute("aria-selected", "true", timeout=10000)
    expect(page.get_by_text("1 selected")).to_be_visible(timeout=10000)

    # Reset (the button only appears once something is selected).
    page.get_by_role("button", name="Reset selection").click()

    # The result panel clears ...
    expect(page.get_by_text("Nothing selected yet.")).to_be_visible(timeout=10000)
    # ... AND the row in the (remounted) component is no longer highlighted.
    expect(
        page.get_by_test_id("stListview").first.get_by_test_id(
            "stListviewOption-berlin"
        )
    ).to_have_attribute("aria-selected", "false", timeout=10000)
