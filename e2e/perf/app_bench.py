# e2e/perf/app_bench.py
"""Streamlit harness for the browser-tier performance benchmark (e2e/perf).

Driven by e2e/perf/test_bench.py through Playwright. The query string picks the
cell — ``?n=<rows>&grouped=<0|1>&newopt=<0|1>`` — and the list mounts only on
the "show" button, so the test times the mount itself. "rerun" is an unrelated
widget interaction: the options arrive unchanged, as freshly parsed JSON.
"edit" flips one option's label (row N/2), so the rerun it causes ships a
one-row change; the next "edit" flips it back. ``newopt=1`` renders with
``accept_new_options=True`` for the add-option scenario, on a page load of its
own, so every other scenario runs the plain configuration. The status line is
what the test waits for.

Measures the checkout it runs from: Streamlit registers the component's assets
from the installed distribution at server start, so this script imports
``streamlit_listview`` the ordinary way and never touches its resolution.
"""
import json
import sys
import time
from pathlib import Path

import streamlit as st

# `streamlit run` does not put demo/ on sys.path (it is not a package).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "demo"))
from data import make_large_dataset  # noqa: E402

from streamlit_listview import listview  # noqa: E402

qp = st.query_params
n = int(qp.get("n", "1000"))
grouped = qp.get("grouped", "1") == "1"
newopt = qp.get("newopt", "0") == "1"


@st.cache_resource
def dataset(n: int, grouped: bool) -> list:
    rows = make_large_dataset(n)
    return rows if grouped else [{"id": r["id"], "label": r["label"]} for r in rows]


@st.cache_resource
def options_bytes(n: int, grouped: bool) -> int:
    """Size of the options as the caller passes them — what Streamlit resends every rerun."""
    return len(json.dumps(dataset(n, grouped)).encode())


base = dataset(n, grouped)

ss = st.session_state
ss.setdefault("show", False)
ss.setdefault("reruns", 0)
ss.setdefault("edits", 0)
ss.reruns += 1

col_show, col_rerun, col_edit = st.columns(3)
if col_show.button("show", key="btn_show"):
    ss.show = True
col_rerun.button("rerun", key="btn_rerun")
if col_edit.button("edit", key="btn_edit"):
    ss.edits += 1

options = base
if ss.edits % 2 == 1:
    mid = n // 2
    options = list(base)
    options[mid] = {**base[mid], "label": f"{base[mid]['label']} (edited)"}

if ss.show:
    started = time.perf_counter()
    selected = listview(
        "Benchmark",
        options,
        selection_mode="single",
        enable_search=True,
        collapsible_groups=grouped,
        accept_new_options=newopt,
        height=300,
        key="bench",
    )
    py_ms = (time.perf_counter() - started) * 1000
    sel = selected["id"] if isinstance(selected, dict) else selected
    st.text(
        f"BENCH py_ms={py_ms:.1f} options_bytes={options_bytes(n, grouped)} "
        f"sel={sel} rerun={ss.reruns} edit={ss.edits}"
    )
else:
    st.text(f"BENCH hidden rerun={ss.reruns} edit={ss.edits}")
