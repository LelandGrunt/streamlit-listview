# e2e/test_accessibility.py
"""The listview passes axe-core's WCAG 2.1 A and AA rules in each of its states.

axe-core, an exact-pinned devDependency of the frontend, runs inside the page.
The locator reaches the listview inside its shadow root, and axe.run() takes
that element as its context, so the scan covers the widget and not Streamlit's
page. The color-contrast rule is the contrast check. test_accessibility_dark.py
re-collects the module under the dark theme.
"""

import re
from pathlib import Path
from typing import Any, cast

import pytest
from playwright.sync_api import Locator, Page, expect

APP_FILE = Path(__file__).with_name("app_native_parity.py")
AXE = (
    Path(__file__).parents[1]
    / "streamlit_listview"
    / "frontend"
    / "node_modules"
    / "axe-core"
    / "axe.min.js"
)

# axe reports a target inside a shadow root as [[host, inner]]; join(" ") turns
# the inner pair into "host,inner", so a comma in the keys below marks the
# shadow boundary.
_RUN = """async (element) => {
  const result = await axe.run(element, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
  });
  return {
    passes: result.passes.length,
    violations: result.violations.flatMap((rule) =>
      rule.nodes.map((node) => ({
        rule: rule.id,
        impact: rule.impact,
        help: rule.help,
        url: rule.helpUrl,
        target: node.target.join(" "),
      })),
    ),
  };
}"""

# Findings the widget inherits from Streamlit's theme instead of causing them:
# (rule, target) -> the reason the widget cannot fix it. Matched exactly, so a
# new element with the same rule still fails.
INHERITED: dict[tuple[str, str], str] = {}

# Defects of the widget itself that a separate change fixes: (rule, target) ->
# the reason. Matched exactly, like INHERITED; every other rule still runs on
# these elements.
KNOWN_DEFECTS: dict[tuple[str, str], str] = {}


def _violations(page: Page, root: Locator | None = None) -> list[dict[str, Any]]:
    """Every violation axe-core reports inside the listview, exceptions included.

    `root` is the listview's stListview element; by default the page's only one.
    """
    if not AXE.exists():
        pytest.fail(f"{AXE} is missing. Run npm ci in streamlit_listview/frontend.")
    page.add_script_tag(path=str(AXE))
    widget = page.get_by_test_id("stListview") if root is None else root
    result = cast(dict[str, Any], widget.evaluate(_RUN))
    # An empty context reports no violations either, so zero violations prove
    # something only when the scan checked the widget.
    assert result["passes"] > 0, "axe-core checked nothing inside the listview"
    return cast(list[dict[str, Any]], result["violations"])


def _scan(page: Page, root: Locator | None = None) -> list[dict[str, Any]]:
    excepted = INHERITED.keys() | KNOWN_DEFECTS.keys()
    return [
        v for v in _violations(page, root) if (v["rule"], v["target"]) not in excepted
    ]


def _assert_accessible(page: Page, root: Locator | None = None) -> None:
    violations = _scan(page, root)
    report = "\n".join(
        f"{v['rule']} ({v['impact']}) at {v['target']}: {v['help']} ({v['url']})"
        for v in violations
    )
    assert not violations, f"axe-core reports WCAG violations:\n{report}"


def _settle(page: Page) -> None:
    # Rows (50 ms) and the frame (0.15 s) transition their colors; a scan in
    # the middle of a transition measures a blend.
    page.wait_for_timeout(300)


def test_the_initial_state_is_accessible(page: Page):
    # banana is selected by default, and cherry is disabled.
    _assert_accessible(page)


def test_a_newly_selected_row_is_accessible(page: Page):
    row = page.get_by_test_id("stListviewOption-apple")
    row.click()
    expect(row).to_have_attribute("aria-selected", "true")
    _settle(page)
    _assert_accessible(page)


def test_keyboard_focus_on_a_row_is_accessible(page: Page):
    # The harness's groups are collapsible, so the list is a tree, and the
    # first ArrowDown lands on the Fruit header.
    page.get_by_role("tree", name="Parity list").focus()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    expect(page.locator(".listview-item--focused")).to_have_count(1)
    _settle(page)
    _assert_accessible(page)


def test_keyboard_focus_on_a_group_header_is_accessible(page: Page):
    page.get_by_role("tree", name="Parity list").focus()
    page.keyboard.press("ArrowDown")
    expect(page.locator(".listview-group-header--focused")).to_have_count(1)
    _settle(page)
    _assert_accessible(page)


def test_a_search_with_hits_is_accessible(page: Page):
    page.get_by_test_id("stListviewSearch").fill("an")
    expect(page.get_by_test_id("stListviewOption-apple")).to_have_count(0)
    _assert_accessible(page)


def test_a_search_without_hits_is_accessible(page: Page):
    page.get_by_test_id("stListviewSearch").fill("zzz")
    expect(page.get_by_test_id(re.compile(r"^stListviewOption-"))).to_have_count(0)
    _assert_accessible(page)


def test_every_known_defect_still_shows(page: Page):
    # A fixed defect drops out of the scan, and then its entry goes, as a lint
    # suppression goes when its finding does (CLAUDE.md). INHERITED stays out
    # of this check: a finding Streamlit's theme causes can show under one
    # theme only.
    seen = {(v["rule"], v["target"]) for v in _violations(page)}
    fixed = sorted(KNOWN_DEFECTS.keys() - seen)
    assert not fixed, f"no longer reported; remove from KNOWN_DEFECTS: {fixed}"


def test_a_collapsed_group_is_accessible(page: Page):
    page.get_by_test_id("stListviewGroup").first.click()
    # the group's treeitem carries the state; the header is hidden from the tree
    expect(page.get_by_role("treeitem", name="Fruit")).to_have_attribute(
        "aria-expanded", "false"
    )
    _settle(page)
    _assert_accessible(page)
