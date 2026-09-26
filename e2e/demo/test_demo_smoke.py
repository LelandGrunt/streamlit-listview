# e2e/demo/test_demo_smoke.py
from playwright.sync_api import Page, expect


def test_demo_boots_and_renders_listview(page: Page):
    # The Demo tab is active on load, so its listview must render.
    expect(page.get_by_test_id("stListview").first).to_be_visible(timeout=20000)
    # No Streamlit exception block anywhere on the page.
    expect(page.get_by_test_id("stException")).to_have_count(0)
