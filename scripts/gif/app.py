"""The capture page for the GIF scenarios.

generate.py starts one Streamlit server per take, with LISTVIEW_GIF_SCENARIO and
LISTVIEW_GIF_TAKE naming what to render. The page hides Streamlit's chrome,
renders that scenario's page for that take, and ends every run with a hidden run
counter, which stage.Stage.rerun() waits on.
"""

import os

import streamlit as st

from scenarios import SCENARIOS

scenario = SCENARIOS[os.environ.get("LISTVIEW_GIF_SCENARIO", "hero")]
take = os.environ.get("LISTVIEW_GIF_TAKE", scenario.takes[0].name)

# page_config adds options; it must not repeat page_title or layout.
st.set_page_config(
    page_title="streamlit-listview", layout="centered", **scenario.page_config
)

# Strip Streamlit's chrome so the frame is just the component, and take the run
# counter's element container out of the layout, so the counter moves nothing.
st.markdown(
    """
    <style>
      header[data-testid="stHeader"], [data-testid="stToolbar"],
      #MainMenu, footer {display: none !important;}
      .block-container {padding-top: 1.5rem; padding-bottom: 1rem; max-width: 640px;}
      [data-testid="stElementContainer"]:has(.gif-run) {display: none !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

scenario.page(take)

# The last element of every run. It changes only after the run has sent every
# other element, so a grown count means the run has finished.
runs = st.session_state.get("gif_runs", 0) + 1
st.session_state["gif_runs"] = runs
st.markdown(
    f'<span class="gif-run" data-run="{runs}">{runs}</span>', unsafe_allow_html=True
)
