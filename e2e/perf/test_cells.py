# e2e/perf/test_cells.py
"""Unit tests for the browser-tier benchmark's pure helpers. No browser, no server,
so they run under a plain ``pytest e2e/`` (e2e/perf/conftest.py's go_to_app
override takes no page)."""

import json
import sys

import pytest

from e2e.perf import cells

sys.path.insert(0, str(cells.REPO_ROOT / "demo"))
from data import make_large_dataset


def test_parse_subset_returns_everything_when_unset_or_blank():
    assert cells.parse_subset("--perf-sizes", None, cells.SIZES) == list(cells.SIZES)
    assert cells.parse_subset("--perf-sizes", "  ", cells.SIZES) == list(cells.SIZES)


def test_parse_subset_keeps_the_given_order_and_trims():
    assert cells.parse_subset("--perf-sizes", " 50000, 100", cells.SIZES) == [
        50000,
        100,
    ]
    assert cells.parse_subset("--perf-shapes", "ungrouped", cells.SHAPES) == [
        "ungrouped"
    ]


def test_parse_subset_refuses_unknown_or_blank_entries_naming_the_option():
    with pytest.raises(
        ValueError,
        match=r"--perf-sizes: '2000' is not one of 100, 1000, 5000, 10000, 25000, 50000, 100000$",
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


def test_the_disabled_shape_is_grouped_and_listed_last():
    assert cells.SHAPES == ("grouped", "ungrouped", "disabled")
    assert cells.Cell(100, "disabled").grouped is True
    assert cells.Cell(100, "disabled").id == "disabled-n100"


def test_shape_rows_keeps_the_grouped_rows_and_drops_the_group_when_ungrouped():
    rows = make_large_dataset(3)
    assert cells.shape_rows(rows, "grouped") is rows
    assert cells.shape_rows(rows, "ungrouped")[2] == {
        "id": "item-00002",
        "label": "Item 00002",
    }


# The same literals streamlit_listview/frontend/src/bench/fixtures.test.ts pins
# the frontend's makeLargeDataset to.
def test_shape_rows_adds_disabled_to_every_row_true_on_rows_5_15_25():
    rows = make_large_dataset(250)
    out = cells.shape_rows(rows, "disabled")
    assert out[0] == {
        "id": "item-00000",
        "label": "Item 00000",
        "group": "Batch 000",
        "disabled": False,
    }
    assert out[5] == {
        "id": "item-00005",
        "label": "Item 00005",
        "group": "Batch 000",
        "disabled": True,
    }
    assert all(type(row["disabled"]) is bool for row in out)
    disabled = [row["id"] for row in out if row["disabled"]]
    assert len(disabled) == 25
    assert disabled[1] == "item-00015"
    assert disabled[24] == "item-00245"
    assert [{k: v for k, v in row.items() if k != "disabled"} for row in out] == rows
    assert "disabled" not in rows[5]  # the cached grouped rows stay untouched


def test_shape_rows_leaves_every_row_a_scenario_drives_enabled_at_every_size():
    # measure.py clicks, searches for or edits the first, middle and last row.
    for n in cells.SIZES:
        out = cells.shape_rows(make_large_dataset(n), "disabled")
        assert [out[i]["disabled"] for i in (0, 1, n // 2, n - 1)] == [False] * 4


def test_shape_rows_refuses_an_unknown_shape():
    with pytest.raises(ValueError, match=r"'nested' is not one of grouped, "):
        cells.shape_rows([], "nested")


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
