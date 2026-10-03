# e2e/perf/test_cells.py
"""Unit tests for the browser-tier benchmark's pure helpers. No browser, no server,
so they run under a plain ``pytest e2e/`` (e2e/perf/conftest.py's go_to_app
override takes no page)."""
import json

import pytest

from e2e.perf import cells


def test_parse_subset_returns_everything_when_unset_or_blank():
    assert cells.parse_subset("--perf-sizes", None, cells.SIZES) == list(cells.SIZES)
    assert cells.parse_subset("--perf-sizes", "  ", cells.SIZES) == list(cells.SIZES)


def test_parse_subset_keeps_the_given_order_and_trims():
    assert cells.parse_subset("--perf-sizes", " 50000, 100", cells.SIZES) == [50000, 100]
    assert cells.parse_subset("--perf-shapes", "ungrouped", cells.SHAPES) == ["ungrouped"]


def test_parse_subset_refuses_unknown_or_blank_entries_naming_the_option():
    with pytest.raises(
        ValueError,
        match=r"--perf-sizes: '2000' is not one of 100, 1000, 5000, 10000, 25000, 50000",
    ):
        cells.parse_subset("--perf-sizes", "100,2000", cells.SIZES)
    with pytest.raises(ValueError, match=r"--perf-sizes: '' is not one of"):
        cells.parse_subset("--perf-sizes", "100,,5000", cells.SIZES)


def test_cells_are_shape_major_with_stable_ids():
    out = cells.cells([100, 1000], ["grouped", "ungrouped"])
    assert [c.id for c in out] == [
        "grouped-n100",
        "grouped-n1000",
        "ungrouped-n100",
        "ungrouped-n1000",
    ]
    assert out[0].grouped is True
    assert out[2].grouped is False


def test_require_bundle_passes_with_a_built_bundle(tmp_path):
    build = cells.bundle_dir(tmp_path)
    build.mkdir(parents=True)
    (build / "index-abc123.js").write_text("", encoding="utf-8")
    cells.require_bundle(tmp_path)  # must not raise


def test_require_bundle_refuses_a_checkout_without_a_bundle(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cells.require_bundle(tmp_path)
    message = str(exc.value)
    assert str(cells.bundle_dir(tmp_path)) in message
    assert "npm run build" in message


def test_require_run_from_passes_for_the_checkout_root(tmp_path):
    cells.require_run_from(tmp_path, tmp_path)  # must not raise


def test_require_run_from_refuses_another_directory_naming_both(tmp_path):
    root = tmp_path / "checkout"
    elsewhere = tmp_path / "elsewhere"
    root.mkdir()
    elsewhere.mkdir()
    with pytest.raises(SystemExit) as exc:
        cells.require_run_from(root, elsewhere)
    message = str(exc.value)
    assert str(root) in message
    assert str(elsewhere) in message
    assert "working directory" in message


def test_describe_checkout_names_this_repo_and_tolerates_a_non_repo(tmp_path):
    assert cells.describe_checkout(cells.REPO_ROOT) not in ("", "unknown")
    assert cells.describe_checkout(tmp_path) == "unknown"


def test_append_record_creates_the_directory_and_appends_one_line_per_call(tmp_path):
    out = tmp_path / "bench-results" / "x.jsonl"
    cells.append_record(out, {"n": 100, "mount": {"painted_ms": 1.5}})
    cells.append_record(out, {"n": 1000})
    lines = out.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"n": 100, "mount": {"painted_ms": 1.5}},
        {"n": 1000},
    ]
