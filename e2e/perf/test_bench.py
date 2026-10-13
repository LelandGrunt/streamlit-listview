# e2e/perf/test_bench.py
"""The browser-tier benchmark: one test per cell, one JSONL record per measured rep.

Not a pass/fail performance test — it fails only when a scenario cannot
complete (a precondition or a timeout inside measure.py). Skipped unless
``--perf-out`` is given (e2e/perf/conftest.py). The full matrix at the default
3 reps takes about 24 minutes, 4 of them in the three 100k cells;
``--perf-sizes 1000,50000`` for a quick look.
"""

from datetime import datetime, timezone

import pytest

from e2e.perf.cells import Cell, append_record
from e2e.perf.measure import run_cell

# e2e/conftest.py starts this module's server with these flags. Streamlit's
# default already sends uncompressed frames, but config.toml or a
# STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION variable could turn compression
# on and change what every round trip costs; a command line flag outranks both.
EXTRA_ARGS = ["--server.enableWebsocketCompression=false"]


@pytest.mark.perf
def test_cell(cell: Cell, browser, app, perf):
    # Warm-up: the first page load of a cell pays the component's asset
    # serving and the dataset caches. Measured, it would be an outlier.
    run_cell(browser, app.server_url, cell, perf.throttle)
    for rep in range(perf.reps):
        record = run_cell(browser, app.server_url, cell, perf.throttle)
        record.update(
            rep=rep,
            branch=perf.branch,
            bundle=perf.bundle,
            streamlit=perf.streamlit,
            browser=browser.version,
            started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        append_record(perf.out, record)
