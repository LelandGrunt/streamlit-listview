"""Capture pages that start without a visible row (e2e/test_gif_capture.py).

The `state` query parameter picks the page: an empty list, a list whose groups
all start collapsed, or no list at all. Each run ends with the run counter of
scripts/gif/app.py, which the GIF capture waits on.
"""

import streamlit as st

from streamlit_listview import listview

state = st.query_params.get("state", "empty")
if state == "empty":
    listview("Cities", [], key="cities", placeholder="No cities yet")
elif state == "collapsed":
    listview(
        "Cities",
        [
            {"id": "paris", "label": "Paris", "group": "Europe"},
            {"id": "tokyo", "label": "Tokyo", "group": "Asia"},
        ],
        key="cities",
        collapsible_groups=True,
        collapsed_groups="all",
    )

runs = st.session_state.get("gif_runs", 0) + 1
st.session_state["gif_runs"] = runs
st.markdown(
    f'<span class="gif-run" data-run="{runs}">{runs}</span>', unsafe_allow_html=True
)
