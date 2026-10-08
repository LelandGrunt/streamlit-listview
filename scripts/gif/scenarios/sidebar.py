"""The listview in st.sidebar, whose theme swaps the two background tokens (test only)."""

import streamlit as st

from scenarios._cities import CITIES
from stage import Scenario, Stage


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    with st.sidebar:
        listview(
            "Cities",
            CITIES,
            selection_mode="multi",
            enable_search=True,
            search_placeholder="Search cities…",
            height=400,
            key="gif_sidebar",
        )


def play(stage: Stage) -> None:
    stage.snap("idle", 900)
    stage.opt("munich").hover()
    stage.snap("hover-munich", 700)
    with stage.rerun():
        stage.opt("paris").click()
    stage.snap("select-paris", 700)
    stage.search.click()
    stage.snap("search-focus", 700)
    stage.search.press_sequentially("o", delay=50)
    stage.snap("search-o", 900)


SCENARIO = Scenario(
    name="sidebar",
    title="The listview in st.sidebar",
    gallery=False,
    page=page,
    play=play,
    # Open at the capture's 720 px width.
    page_config={"initial_sidebar_state": "expanded"},
)
