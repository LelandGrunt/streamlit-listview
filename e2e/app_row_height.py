# e2e/app_row_height.py
"""Harness for the row-height change test (e2e/test_row_height.py).

One keyed listview of 1,000 grouped rows, and three widgets that change the
height of its rows on a rerun while the key stays: `item_height` (a row's
minimum height), `content_font_size` and `show_grid_lines` (a 1 px border per
row). The key stays fixed, so each change reruns the mounted frontend instead
of remounting it.
"""

import sys
from pathlib import Path

import streamlit as st

# The demo's dataset generator (demo/ is not a package, so it goes on sys.path
# first; `streamlit run` does not put it there).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
from data import make_large_dataset
from streamlit_listview import listview

OPTIONS = make_large_dataset(1_000)

st.title("streamlit-listview e2e row-height app")

item_height = st.radio("item_height", ("None", "50"), horizontal=True)
content_font_size = st.radio("content_font_size", ("None", "24"), horizontal=True)
show_grid_lines = st.checkbox("show_grid_lines", value=True)
listview(
    "Rows",
    OPTIONS,
    selection_mode="single",
    height=300,
    item_height=None if item_height == "None" else int(item_height),
    content_font_size=None if content_font_size == "None" else int(content_font_size),
    show_grid_lines=show_grid_lines,
    key="rows",
)
