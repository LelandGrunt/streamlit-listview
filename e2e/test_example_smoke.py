# e2e/test_example_smoke.py
from pathlib import Path

from playwright.sync_api import Page, expect

# The README's example, served by e2e/conftest.py. It is registered there with
# no expected instance count on purpose: asserting the count is this test's job.
APP_FILE = Path(__file__).parents[1] / "example.py"


def test_example_boots_and_renders_listviews(page: Page):
    # The demo must render several listview instances without a Python exception.
    expect(page.get_by_test_id("stListview").first).to_be_visible(timeout=20000)
    # example.py calls listview() six times, all unconditionally at module level.
    # Assert via to_have_count, which polls: a bare `assert count() >= 5` right
    # after the *first* instance turns visible races Streamlit still streaming
    # the remaining elements in, and intermittently saw only three of them.
    expect(page.get_by_test_id("stListview")).to_have_count(6, timeout=20000)
    # No Streamlit exception block on the page.
    expect(page.get_by_test_id("stException")).to_have_count(0)
