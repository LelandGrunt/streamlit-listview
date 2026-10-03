# e2e/perf/conftest.py
"""Options, marker and fixtures of the browser-tier performance benchmark (e2e/perf/).

Opt-in: every ``perf``-marked test is skipped unless ``--perf-out`` names the
JSONL file to append to, so ``pytest e2e/`` keeps its meaning and never boots
the benchmark server.

Everything the package needs is registered HERE, not in e2e/conftest.py, so the
directory is self-contained and can be copied into another checkout to
benchmark it. pytest reads ``pytest_addoption`` from the conftests it loads at
start-up, which include this one whenever e2e/perf (or a file in it) is on the
command line — run the benchmark as ``pytest e2e/perf/ --perf-out …``. Under a
plain ``pytest e2e/`` this conftest loads late: pytest replays its historic
``pytest_addoption`` and sets the defaults, so the options exist there with
their defaults, and only the command line rejects ``--perf-*`` (it is parsed
before the replay). The ``default=None`` passed to every ``getoption`` below is
therefore belt and braces, not a workaround for missing options — keep it: the
benchmark must stay collectable, parametrised over the full matrix, and skipped
whichever way pytest loads this file.

Overrides from e2e/conftest.py, the way e2e/demo/conftest.py does for the demo:
``app_file`` (one harness for the package) and ``go_to_app`` (each cell
navigates to its own query string, and the pure tests need no page at all).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from e2e.perf.cells import (
    REPO_ROOT,
    SHAPES,
    SIZES,
    cells,
    describe_checkout,
    parse_subset,
    require_bundle,
    require_run_from,
)

APP_FILE = Path(__file__).with_name("app_bench.py")


def pytest_addoption(parser):
    group = parser.getgroup("perf", "browser-tier performance benchmark (e2e/perf)")
    group.addoption(
        "--perf-out",
        default=None,
        metavar="FILE.jsonl",
        help="append one JSON record per measured rep to FILE; also the opt-in — "
        "without it every e2e/perf benchmark is skipped",
    )
    group.addoption(
        "--perf-reps", type=int, default=3, metavar="N",
        help="measured reps per cell, after one discarded warm-up (default 3)",
    )
    group.addoption(
        "--perf-throttle", type=int, default=1, metavar="RATE",
        help="CDP CPU throttling rate: 1 = none (default), 4 = a slow laptop",
    )
    group.addoption(
        "--perf-sizes", default=None, metavar="LIST",
        help="comma-separated subset of 100,1000,5000,10000,25000,50000",
    )
    group.addoption(
        "--perf-shapes", default=None, metavar="LIST",
        help="comma-separated subset of grouped,ungrouped",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "perf: browser-tier performance benchmark (e2e/perf); skipped unless --perf-out is given",
    )


@dataclass(frozen=True)
class PerfOptions:
    out: Path
    reps: int
    throttle: int
    root: Path
    branch: str


@pytest.fixture(scope="module")
def app_file():
    return APP_FILE


@pytest.fixture(autouse=True)
def go_to_app():
    """Each benchmark cell navigates itself; the pure tests need no page."""


def pytest_generate_tests(metafunc):
    if "cell" in metafunc.fixturenames:
        config = metafunc.config
        sizes = parse_subset("--perf-sizes", config.getoption("--perf-sizes", default=None), SIZES)
        shapes = parse_subset("--perf-shapes", config.getoption("--perf-shapes", default=None), SHAPES)
        matrix = cells(sizes, shapes)
        metafunc.parametrize("cell", matrix, ids=[c.id for c in matrix])


def pytest_collection_modifyitems(config, items):
    if config.getoption("--perf-out", default=None) is not None:
        return
    skip = pytest.mark.skip(reason="benchmark: pass --perf-out <file.jsonl> to run it")
    for item in items:
        if item.get_closest_marker("perf") is not None:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def perf(request) -> PerfOptions:
    out = request.config.getoption("--perf-out", default=None)
    assert out is not None, "perf tests are skipped without --perf-out"
    # Fail here, with the directory named, rather than inside the server boot —
    # or, worse, after it, with records labelled by a checkout the server did
    # not serve.
    require_run_from(REPO_ROOT, Path.cwd())
    require_bundle(REPO_ROOT)
    return PerfOptions(
        out=Path(out),
        reps=request.config.getoption("--perf-reps"),
        throttle=request.config.getoption("--perf-throttle"),
        root=REPO_ROOT,
        branch=describe_checkout(REPO_ROOT),
    )
