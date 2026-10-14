# e2e/test_on_change.py
"""The README's recipe tells a correction of the selection from user input.

A keyed listview writes a correction back like a click, so its ``on_change``
cannot tell the two apart. The run that changes the parameters, though,
already returns the corrected value, so the correction's own rerun returns
that value again, while a click returns a new one. The recipe compares the
two; the harness runs it straight from the README.
"""

from pathlib import Path

from playwright.sync_api import Page, expect

from e2e.conftest import echo, stext

# The harness e2e/conftest.py serves for this module, with its listview
# awaited before each test.
APP_FILE = Path(__file__).with_name("app_on_change.py")


def _option(page: Page, option_id: str):
    return page.get_by_test_id(f"stListviewOption-{option_id}")


def _runs(page: Page) -> int:
    return int(stext(page, "runs").inner_text().split("=")[1])


def test_a_correction_is_not_counted_as_user_input(page: Page):
    _option(page, "Apple").click()
    expect(stext(page, "user_changes")).to_have_text("user_changes=1")
    _option(page, "Banana").click()
    expect(stext(page, "user_changes")).to_have_text("user_changes=2")
    expect(echo(page, "fruit")).to_have_text("fruit_echo=['Apple', 'Banana']")

    # The cap drops Banana. Two reruns: the toggle's, which already returns
    # ['Apple'], and the write-back's, which calls on_change. The recipe counts
    # neither.
    runs = _runs(page)
    page.get_by_text("One fruit only").click()
    expect(stext(page, "runs")).to_have_text(f"runs={runs + 2}")
    expect(echo(page, "fruit")).to_have_text("fruit_echo=['Apple']")
    expect(stext(page, "user_changes")).to_have_text("user_changes=2")

    # The same change made by a click counts: ['Apple', 'Banana'] to ['Apple'].
    page.get_by_text("One fruit only").click()
    expect(stext(page, "runs")).to_have_text(f"runs={runs + 3}")
    _option(page, "Banana").click()
    expect(stext(page, "user_changes")).to_have_text("user_changes=3")
    _option(page, "Banana").click()
    expect(stext(page, "user_changes")).to_have_text("user_changes=4")
    expect(echo(page, "fruit")).to_have_text("fruit_echo=['Apple']")


def test_esc_calls_on_change_only_when_it_removes_a_row(page: Page):
    _option(page, "Apple").click()
    expect(stext(page, "user_changes")).to_have_text("user_changes=1")

    page.get_by_role("listbox").focus()
    page.keyboard.press("Escape")
    expect(echo(page, "fruit")).to_have_text("fruit_echo=[]")
    expect(stext(page, "user_changes")).to_have_text("user_changes=2")

    # Nothing left to clear: no write-back, so no rerun at all. The focus check
    # keeps the assertion honest: a listbox that lost its focus on the rerun
    # would leave `runs` unchanged for the wrong reason.
    expect(page.get_by_role("listbox")).to_be_focused()
    runs = _runs(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(1500)
    expect(stext(page, "runs")).to_have_text(f"runs={runs}")
