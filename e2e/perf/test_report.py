# e2e/perf/test_report.py
"""Unit tests for the results report. Synthetic records; no browser, no server."""
import json
import os
import subprocess
import sys
from pathlib import Path

from e2e.perf import report
from e2e.perf.report import Stats


def rec(n=100, grouped=True, rep=0, **scenarios):
    return {
        "n": n,
        "grouped": grouped,
        "throttle": 1,
        "rep": rep,
        "branch": "abc",
        "started": "t",
        **scenarios,
    }


def test_flatten_nests_scenario_metrics_and_keeps_top_level_scalars():
    r = rec(mount={"painted_ms": 12.5, "ws_bytes": 3000}, dom_nodes=410, heap_mb=5.5)
    assert report.flatten(r) == {
        ("mount", "painted_ms"): 12.5,
        ("mount", "ws_bytes"): 3000.0,
        ("dom_nodes", ""): 410.0,
        ("heap_mb", ""): 5.5,
    }


def test_flatten_ignores_metadata_and_booleans():
    assert report.flatten(rec()) == {}
    assert report.flatten(rec(mount={"ok": True})) == {}


def test_summarize_takes_median_low_high_and_count_per_cell_scenario_metric():
    records = [rec(rep=i, mount={"painted_ms": v}) for i, v in enumerate([30.0, 10.0, 20.0])]
    assert report.summarize(records) == {
        (100, True, "mount", "painted_ms"): Stats(median=20.0, low=10.0, high=30.0, count=3)
    }


def test_summarize_tolerates_records_that_lack_a_scenario():
    # An ungrouped rep has no group_* scenario; a rep that crashed after mount
    # has nothing else. Neither may raise, and counts differ per key.
    records = [
        rec(grouped=False, mount={"painted_ms": 1.0}),
        rec(grouped=False, rep=1, mount={"painted_ms": 3.0}, scroll={"p95_ms": 9.0}),
    ]
    stats = report.summarize(records)
    assert stats[(100, False, "mount", "painted_ms")].count == 2
    assert stats[(100, False, "scroll", "p95_ms")] == Stats(9.0, 9.0, 9.0, 1)
    assert (100, False, "group_collapse", "painted_ms") not in stats


def test_compare_pairs_keys_and_marks_a_missing_side():
    a = {
        (100, True, "mount", "painted_ms"): Stats(20.0, 18.0, 22.0, 3),
        (50000, True, "mount", "painted_ms"): Stats(4000.0, 3900.0, 4100.0, 3),
    }
    b = {
        (100, True, "mount", "painted_ms"): Stats(15.0, 14.0, 16.0, 3),
        (100, False, "mount", "painted_ms"): Stats(14.0, 14.0, 14.0, 1),
    }
    rows = report.compare(a, b)
    assert [r.key for r in rows] == [
        (100, False, "mount", "painted_ms"),
        (100, True, "mount", "painted_ms"),
        (50000, True, "mount", "painted_ms"),
    ]
    both = rows[1]
    assert both.delta == -5.0
    assert both.pct == -25.0
    assert rows[0].a is None and rows[0].delta is None and rows[0].pct is None
    assert rows[2].b is None


def test_render_compare_markdown_has_a_header_separator_and_dashes_for_missing():
    rows = report.compare(
        {(100, True, "mount", "painted_ms"): Stats(20.0, 18.0, 22.0, 3)},
        {(100, False, "mount", "painted_ms"): Stats(14.0, 14.0, 14.0, 1)},
    )
    text = report.render_compare(rows, markdown=True)
    lines = text.splitlines()
    assert lines[0].startswith("| n ")
    assert set(lines[1]) <= set("|- ")
    assert "—" in lines[2] and "—" in lines[3]
    # Row 1 (ungrouped) has no A side, row 2 (grouped) has A range of 18.0..22.0
    assert "18.0..22.0" in text
    assert text.rstrip().endswith("1 measurement(s) only in A, 1 only in B.")


def test_render_summary_plain_lists_median_low_high_and_reps():
    text = report.render_summary(
        {(1000, False, "scroll", "p95_ms"): Stats(24.5, 20.0, 31.0, 3)}, markdown=False
    )
    header, row = text.splitlines()
    assert header.split() == ["n", "shape", "scenario", "metric", "median", "low", "high", "reps"]
    assert row.split() == ["1000", "ungrouped", "scroll", "p95_ms", "24.5", "20.0", "31.0", "3"]


def test_report_compare_with_cp1252_stdout(tmp_path):
    """Regression: report must not die with UnicodeEncodeError when piped with cp1252 stdout."""
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(json.dumps(rec(mount={"painted_ms": 20.0})) + "\n", encoding="utf-8")
    b.write_text(json.dumps(rec(mount={"painted_ms": 10.0})) + "\n", encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    result = subprocess.run(
        [sys.executable, "-m", "e2e.perf.report", str(a), str(b), "--markdown"],
        capture_output=True,
        cwd=repo_root,
        env=env,
    )
    assert result.returncode == 0, f"stderr: {result.stderr.decode('utf-8', errors='replace')}"
    output = result.stdout.decode("utf-8")
    assert "Δ" in output, "Delta symbol should be in output"


def test_main_summarises_one_file_and_compares_two(tmp_path, capsys):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(json.dumps(rec(mount={"painted_ms": 20.0})) + "\n\n", encoding="utf-8")
    b.write_text(json.dumps(rec(mount={"painted_ms": 10.0})) + "\n", encoding="utf-8")
    assert report.main([str(a)]) == 0
    assert "20.0" in capsys.readouterr().out
    assert report.main([str(a), str(b), "--markdown"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("| n ")
    assert "-50%" in out
