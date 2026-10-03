# e2e/perf/report.py
"""Summarise or compare browser-tier benchmark results (JSONL from e2e/perf/test_bench.py).

    python -m e2e.perf.report bench-results/branch.jsonl
        medians (with low/high and rep count) per cell, scenario and metric
    python -m e2e.perf.report bench-results/main.jsonl bench-results/branch.jsonl [--markdown]
        B against A: both medians, the delta and the delta in percent

Pure functions, so e2e/perf/test_report.py covers them without a browser. A
record that lacks a scenario (ungrouped reps have no group_*; a rep that failed
mid-way has only what it reached) simply contributes nothing to that key, and
two files that only partly overlap are compared on the intersection with the
rest counted in a footer — never a KeyError at the end of a 15-minute run.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

Key = tuple[int, bool, str, str]  # (n, grouped, scenario, metric)

META = frozenset({"n", "grouped", "throttle", "rep", "branch", "started"})


@dataclass(frozen=True)
class Stats:
    median: float
    low: float
    high: float
    count: int


@dataclass(frozen=True)
class Row:
    key: Key
    a: Stats | None
    b: Stats | None

    @property
    def delta(self) -> float | None:
        if self.a is None or self.b is None:
            return None
        return self.b.median - self.a.median

    @property
    def pct(self) -> float | None:
        delta = self.delta
        if delta is None or self.a is None or self.a.median == 0:
            return None
        return 100.0 * delta / self.a.median


def load(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def flatten(record: dict) -> dict[tuple[str, str], float]:
    """(scenario, metric) -> value for every numeric measurement in one record.

    Top-level numbers (dom_nodes, heap_mb) get the empty metric name.
    """
    out: dict[tuple[str, str], float] = {}
    for scenario, value in record.items():
        if scenario in META:
            continue
        if isinstance(value, dict):
            for metric, v in value.items():
                if _number(v):
                    out[(scenario, metric)] = float(v)
        elif _number(value):
            out[(scenario, "")] = float(value)
    return out


def summarize(records: Iterable[dict]) -> dict[Key, Stats]:
    samples: dict[Key, list[float]] = {}
    for record in records:
        for (scenario, metric), value in flatten(record).items():
            key: Key = (int(record["n"]), bool(record["grouped"]), scenario, metric)
            samples.setdefault(key, []).append(value)
    return {
        key: Stats(statistics.median(values), min(values), max(values), len(values))
        for key, values in samples.items()
    }


def compare(a: dict[Key, Stats], b: dict[Key, Stats]) -> list[Row]:
    return [Row(key, a.get(key), b.get(key)) for key in sorted(set(a) | set(b))]


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:,.1f}"


def _shape(grouped: bool) -> str:
    return "grouped" if grouped else "ungrouped"


def _table(header: list[str], rows: list[list[str]], markdown: bool) -> str:
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(header)]

    def line(cells: list[str]) -> str:
        padded = [c.ljust(w) for c, w in zip(cells, widths)]
        return "| " + " | ".join(padded) + " |" if markdown else "  ".join(padded).rstrip()

    lines = [line(header)]
    if markdown:
        lines.append("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    lines.extend(line(r) for r in rows)
    return "\n".join(lines)


def render_summary(stats: dict[Key, Stats], markdown: bool) -> str:
    header = ["n", "shape", "scenario", "metric", "median", "low", "high", "reps"]
    rows = [
        [str(n), _shape(g), s, m, _fmt(st.median), _fmt(st.low), _fmt(st.high), str(st.count)]
        for (n, g, s, m), st in sorted(stats.items())
    ]
    return _table(header, rows, markdown)


def render_compare(rows: list[Row], markdown: bool) -> str:
    header = ["n", "shape", "scenario", "metric", "A median", "A range", "B median", "B range", "Δ", "Δ %"]
    body = []
    for row in rows:
        n, g, s, m = row.key
        a_range = "—" if row.a is None else f"{_fmt(row.a.low)}..{_fmt(row.a.high)}"
        b_range = "—" if row.b is None else f"{_fmt(row.b.low)}..{_fmt(row.b.high)}"
        body.append(
            [
                str(n),
                _shape(g),
                s,
                m,
                _fmt(row.a.median if row.a else None),
                a_range,
                _fmt(row.b.median if row.b else None),
                b_range,
                _fmt(row.delta),
                "—" if row.pct is None else f"{row.pct:+.0f}%",
            ]
        )
    text = _table(header, body, markdown)
    only_a = sum(1 for r in rows if r.b is None)
    only_b = sum(1 for r in rows if r.a is None)
    if only_a or only_b:
        text += f"\n\n{only_a} measurement(s) only in A, {only_b} only in B."
    return text


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="python -m e2e.perf.report",
        description="Summarise one browser-tier results file, or compare a second against it.",
    )
    parser.add_argument("a", type=Path, help="results file (JSONL); the baseline when two are given")
    parser.add_argument("b", type=Path, nargs="?", help="second results file, compared against the first")
    parser.add_argument("--markdown", action="store_true", help="emit a Markdown table")
    args = parser.parse_args(argv)
    stats_a = summarize(load(args.a))
    if args.b is None:
        print(render_summary(stats_a, args.markdown))
    else:
        print(render_compare(compare(stats_a, summarize(load(args.b))), args.markdown))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
