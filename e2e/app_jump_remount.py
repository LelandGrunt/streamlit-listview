# e2e/app_jump_remount.py
"""Harness for the key-change remount test (e2e/test_jump_remount.py).

A horizontal radio picks the default of one 1,000-row grouped listview, and the
key carries the default, the way demo/app.py folds `default` into its
`widget_key`. Each pick therefore remounts the frontend into a new shadow root,
which loads the component's stylesheet again.
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
DEFAULTS = ("item-00042", "item-00500", "item-00987")

st.title("streamlit-listview e2e jump-after-remount app")

choice = st.radio("Default", DEFAULTS, horizontal=True)
listview(
    "Jump",
    OPTIONS,
    selection_mode="single",
    default=choice,
    height=300,
    key=f"jump_{choice}",
)
