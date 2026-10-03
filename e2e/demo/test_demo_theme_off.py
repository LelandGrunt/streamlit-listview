# e2e/demo/test_demo_theme_off.py
"""A deployment can switch the Theme picker off (LISTVIEW_DEMO_THEME_SWITCHER).

Off means gone: no Theme pill, so no picker and no callback that could re-theme
the server. The variable is read by the server process, so this module boots a
server of its own through EXTRA_ENV (see ``_servers`` in e2e/conftest.py).
"""
from playwright.sync_api import Page, expect

EXTRA_ENV = {"LISTVIEW_DEMO_THEME_SWITCHER": "0"}


def test_the_theme_section_is_gone_when_switched_off(page: Page):
    sections = page.get_by_role("radiogroup", name="Configuration section")
    # The other sections are untouched; only Theme drops out.
    expect(sections.get_by_role("radio", name="Formatting", exact=True)).to_be_visible()
    expect(sections.get_by_role("radio", name="Theme", exact=True)).to_have_count(0)
