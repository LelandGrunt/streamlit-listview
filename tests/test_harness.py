"""Drift guards for the quality harness (HARNESS.md).

Most tests pin a setting that decides where a check runs: a hook that scans
the history needs the whole history, a hook that needs the network or its own
browser stays in pre-commit's manual stage, out of every commit, CI run and
push, and a release tag reaches PyPI only after CI's jobs pass. The last tests
recount HARNESS.md's inventory and compare the count with the three places
that summarize it, so a status changed in one place cannot pass unnoticed.
"""

import re
from collections import Counter
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
PRE_COMMIT = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
WORKFLOWS = ROOT / ".github" / "workflows"
CI = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
RELEASE = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
HARNESS = (ROOT / "HARNESS.md").read_text(encoding="utf-8")


def hook_blocks() -> list[str]:
    """.pre-commit-config.yaml cut at every hook and every repo: a block holds
    one hook and ends before the next repo's header."""
    return cast(list[str], re.split(r"(?m)^(?=\s*- (?:id|repo): )", PRE_COMMIT))


def hook_block(hook: str) -> str:
    """The lines of one hook in .pre-commit-config.yaml, found by id or alias."""
    for block in hook_blocks():
        if re.search(rf"(?m)^\s+(?:- id|alias): {re.escape(hook)}$", block):
            return block
    raise AssertionError(f".pre-commit-config.yaml has no hook {hook}")


def job_block(job: str, workflow: str = CI) -> str:
    """The lines of one job in a workflow, ci.yml by default, up to the next
    job. A comment above the next job counts toward this one."""
    match = re.search(rf"(?ms)^  {re.escape(job)}:\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow)
    if match is None:
        raise AssertionError(f"the workflow has no job {job}")
    return cast(str, match.group(1))


def test_a_hook_block_ends_before_the_next_repo():
    # The last hook of a repo is followed by the next repo's header and
    # comments; a setting named there must not count for the hook.
    assert "- repo:" not in hook_block("markdown-link-check")


def test_the_lint_job_checks_out_the_whole_history():
    # gitleaks-history scans the history of HEAD; a shallow clone holds one
    # commit, so the scan would pass without looking.
    assert "fetch-depth: 0" in job_block("lint")


def test_gitleaks_scans_the_staged_changes_and_the_history():
    # Both hooks share the id gitleaks; the staged one is the block without an
    # alias, and it runs as shipped (`gitleaks git --staged`).
    staged = [
        block
        for block in hook_blocks()
        if re.search(r"(?m)^\s+- id: gitleaks$", block) and "alias:" not in block
    ]
    assert len(staged) == 1
    assert "entry:" not in staged[0]
    history = hook_block("gitleaks-history")
    assert "entry: gitleaks git --redact --verbose --log-opts=HEAD" in history
    assert "always_run: true" in history


MANUAL_HOOKS = ["markdown-link-check", "mermaid", "e2e-browsers"]


def test_the_network_and_browser_hooks_run_only_by_hand():
    # A manual hook stays out of every commit, CI's lint job and the push gate:
    # its result depends on other websites, or it needs its own browser.
    for hook in MANUAL_HOOKS:
        assert "stages: [manual]" in hook_block(hook), hook


def test_a_release_tag_reaches_pypi_only_after_cis_jobs():
    # ci.yml does not run on a tag, and main reaches GitHub only after PyPI;
    # without these lines a tag pushed with --no-verify would publish without
    # the hooks, the audits and the browser suite.
    assert re.search(r"(?m)^  workflow_call:$", CI)
    assert "uses: ./.github/workflows/ci.yml" in job_block("ci", RELEASE)
    assert "needs: [build, ci]" in job_block("publish-to-pypi", RELEASE)


def test_the_push_gate_job_checks_main_only():
    # release.yml calls ci.yml on the tag's push, which `check tag` covers;
    # `check main` there would fail while PyPI lacks the version.
    condition = "if: github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert condition in job_block("push-gate")


def between(text: str, start: str, end: str) -> str:
    """The part of `text` after `start`, up to the next `end`."""
    _, found, rest = text.partition(start)
    assert found, f"HARNESS.md lost {start!r}"
    return rest.partition(end)[0]


def inventory() -> list[list[tuple[str, str, str]]]:
    """(layer, class, status) of each row of HARNESS.md's inventory, one list
    per category, in the document's order."""
    section = between(HARNESS, "\n## Harness inventory\n", "\n## Coverage\n")
    categories = re.split(r"(?m)^### \d\. .*$", section)[1:]
    row = r"(?m)^\| ([^|]+?) \| (🟢|🟡|🔴) \| (✅|◐|✗|—) \|"
    return [
        cast(list[tuple[str, str, str]], re.findall(row, category))
        for category in categories
    ]


def test_the_mindmap_shows_each_applicable_layer_in_its_category():
    block = between(HARNESS, "```mermaid\nmindmap\n", "```")
    shown = [
        sorted(re.findall(r"(?m)^      (✅|◐|✗) ", category))
        for category in re.split(r"(?m)^    \S.*$", block)[1:]
    ]
    applicable = [
        sorted(status for _, _, status in category if status != "—")
        for category in inventory()
    ]
    # The Harness Inventory has nine categories.
    assert len(applicable) == 9
    assert shown == applicable


def test_the_pie_chart_and_the_summary_count_the_inventory():
    counts = Counter(status for category in inventory() for _, _, status in category)
    pie = re.findall(
        r'(?m)^    "([^"]+)" : (\d+)$', between(HARNESS, "pie showData", "```")
    )
    assert {label: int(number) for label, number in pie} == {
        "Automated gate": counts["✅"],
        "Partial, manual or outside the repository": counts["◐"],
        "Gap": counts["✗"],
        "Not applicable": counts["—"],
    }
    summary = re.search(
        r"Of the (\d+) layers, (\d+) do not apply.*?Of the (\d+) that apply, "
        r"(\d+) run as automated gates and (\d+) more are in place in part; "
        r"(\d+) are gaps",
        HARNESS,
        re.DOTALL,
    )
    assert summary is not None
    total = counts.total()
    applicable = total - counts["—"]
    expected = [total, counts["—"], applicable, counts["✅"], counts["◐"], counts["✗"]]
    assert [int(number) for number in summary.groups()] == expected


def test_every_applicable_extrinsic_layer_has_a_check():
    # Gaps and next steps says so, and the Harness Inventory asks every 🟢 layer
    # from risk tier 1 on: a 🟢 gap breaks the project's own minimum.
    gaps = [
        layer
        for category in inventory()
        for layer, kind, status in category
        if kind == "🟢" and status == "✗"
    ]
    assert gaps == []
