# e2e/perf/cells.py
"""Pure helpers for the browser-tier performance benchmark (e2e/perf).

The matrix (sizes × shapes), option parsing, the working-directory and bundle
guards, the checkout description and the JSONL writer. Pure, so e2e/perf/test_cells.py covers them
without a browser or a server.

The benchmark measures the checkout it runs from (REPO_ROOT): Streamlit
registers a V2 component's assets from the INSTALLED distribution when the
server starts, before any app script runs, so no script-level switch can point
it at another checkout's bundle. A baseline is benchmarked by copying e2e/perf/
into it and running there.
"""
from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

SIZES: tuple[int, ...] = (100, 1_000, 5_000, 10_000, 25_000, 50_000)
SHAPES: tuple[str, ...] = ("grouped", "ungrouped")
REPO_ROOT = Path(__file__).resolve().parents[2]

T = TypeVar("T")


def parse_subset(name: str, raw: str | None, allowed: Sequence[T]) -> list[T]:
    """The subset a comma-separated option names, or all of ``allowed`` when unset/blank.

    An unknown or blank entry raises, naming the option: a typo must not shrink
    the matrix silently — a run that quietly skipped 50k would be read as "no
    regression at 50k".
    """
    if raw is None or not raw.strip():
        return list(allowed)
    out: list[T] = []
    for entry in raw.split(","):
        text = entry.strip()
        match = next((value for value in allowed if str(value) == text), None)
        if match is None:
            raise ValueError(f"{name}: {text!r} is not one of {', '.join(map(str, allowed))}")
        out.append(match)
    return out


@dataclass(frozen=True)
class Cell:
    """One benchmark cell: a row count and a shape."""

    n: int
    shape: str

    @property
    def grouped(self) -> bool:
        return self.shape == "grouped"

    @property
    def id(self) -> str:
        return f"{self.shape}-n{self.n}"


def cells(sizes: Sequence[int], shapes: Sequence[str]) -> list[Cell]:
    """Shape-major: every size of one shape, then the next."""
    return [Cell(n, shape) for shape in shapes for n in sizes]


def bundle_dir(root: Path) -> Path:
    return root / "streamlit_listview" / "frontend" / "build"


def require_run_from(root: Path, cwd: Path) -> None:
    """Stop unless the benchmark runs from the root of the checkout it lives in.

    The Streamlit server is started as ``python -m streamlit run …`` with
    pytest's working directory, and ``python -m`` puts that directory first on
    ``sys.path``: the server resolves the component's package, and through it
    its asset root, from the working directory. The pytest process cannot tell
    — it prepends the test package's rootdir to its own ``sys.path``, so an
    ``import streamlit_listview`` there would find the copy next to the
    benchmark — which is why this compares directories instead. Running a
    baseline's copy of e2e/perf/ from another checkout would measure that
    checkout while labelling every record with the baseline's hash.

    ``samefile`` rather than ``==``: Windows drive-letter case and symlinks
    must not trip it.
    """
    if not cwd.resolve().samefile(root):
        raise SystemExit(
            "run the browser benchmark from the root of the checkout it lives in: "
            f"the working directory is {cwd}, the benchmark belongs to {root}; "
            "the Streamlit server serves the package in its working directory."
        )


def require_bundle(root: Path) -> None:
    """Stop before the benchmark boots Streamlit when the checkout has no built bundle.

    Streamlit would fail as well, but at component registration, as a glob
    error far from the cause; the first question in a fresh or baseline checkout
    is "did I build it?", so answer it here, naming the directory.
    """
    if not any(bundle_dir(root).glob("index-*.js")):
        raise SystemExit(
            f"no built bundle under {bundle_dir(root)}; "
            f"run `npm run build` in {root / 'streamlit_listview' / 'frontend'} first "
            "(the browser benchmark measures the checkout it runs from)."
        )


def describe_checkout(root: Path) -> str:
    """``git describe --always --dirty`` of the measured checkout; "unknown" outside a repo."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "describe", "--always", "--dirty", "--abbrev=12"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def append_record(path: Path, record: dict) -> None:
    """Append one JSON line, creating the results directory (gitignored, so absent on a fresh clone)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
