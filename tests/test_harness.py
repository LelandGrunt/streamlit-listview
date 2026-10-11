"""Drift guards for the quality harness (HARNESS.md).

Each test pins a setting that decides where a check runs: a hook that scans
the history needs the whole history, and a hook that needs the network or its
own browser stays in pre-commit's manual stage, out of every commit, CI run
and push.
"""

import re
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
PRE_COMMIT = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


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


def job_block(job: str) -> str:
    """The lines of one job in ci.yml, up to the next job."""
    match = re.search(rf"(?ms)^  {re.escape(job)}:\n(.*?)(?=^  [\w-]+:\n|\Z)", CI)
    if match is None:
        raise AssertionError(f"ci.yml has no job {job}")
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
