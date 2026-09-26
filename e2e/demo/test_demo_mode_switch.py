# e2e/demo/test_demo_mode_switch.py
from playwright.sync_api import Page, expect


def test_switching_multi_to_single_with_select_all_does_not_error(page: Page):
    """Regression: with the section switcher, the multi-only reset of
    select_all / max_selections runs in render_demo's post-dispatch
    reconciliation (using THIS run's selection_mode). Earlier it lived in a
    pre-dispatch block that read the *previous* run's mode, so toggling
    multi -> single while select_all was on fed the live call
    select_all=True with selection_mode="single" -> ValueError -> st.error.

    Steps: enable multi (Basic) -> enable Select all (Behavior) -> back to
    Basic -> switch to single. The widget must keep rendering with no error.
    """
    # Basic is the default section. Switch the selection mode to multi.
    page.get_by_role("radio", name="multi", exact=True).click()

    # Select all lives in the Behavior section (multi only) — open it and enable.
    page.get_by_role("radio", name="Behavior", exact=True).click()
    page.get_by_text("Select all toggle", exact=True).click()

    # Back to Basic, switch the mode to single — the path that used to raise.
    page.get_by_role("radio", name="Basic", exact=True).click()
    page.get_by_role("radio", name="single", exact=True).click()

    # No Streamlit exception and no surfaced listview ValueError anywhere.
    expect(page.get_by_test_id("stException")).to_have_count(0)
    expect(page.get_by_text("listview raised")).to_have_count(0)
    # The live component still renders (it was not st.stop()-ed).
    expect(page.get_by_test_id("stListview").first).to_be_visible(timeout=10000)
