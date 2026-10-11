"""The list scrolls its default into view, switched by a radio above the frame.

The key carries the default, the way the demo folds `default` into its widget
key, so each pick remounts the listview and the new instance scrolls its
default into view.
"""

from functools import cache

import streamlit as st

from data import make_large_dataset
from stage import Scenario, Stage

DEFAULTS = ("item-00042", "item-00500", "item-00987")


@cache
def options() -> list[dict[str, str]]:
    """The 1,000 options, built on first use and kept for the process.

    Not at import: generate.py, pytest and every take's server import the whole
    catalogue, and only this scenario's page needs the list.
    """
    return make_large_dataset(1_000)


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    default = (
        st.radio(
            "Default",
            DEFAULTS,
            horizontal=True,
            key="default",
            label_visibility="collapsed",
        )
        or DEFAULTS[0]
    )
    # Keeps the radio out of the frame's 12 px margin.
    st.markdown('<div style="height: 24px"></div>', unsafe_allow_html=True)
    listview(
        f"default = `{default}`",
        options(),
        selection_mode="single",
        default=default,
        height=300,
        width=560,
        key=f"gif_jump_to_default_{default}",
    )


def play(stage: Stage) -> None:
    for index, default in enumerate(DEFAULTS):
        if index:
            with stage.rerun():
                stage.control(default).click()
        stage.snap(f"default-{default.removeprefix('item-')}", 1500)


SCENARIO = Scenario(
    name="jump-to-default",
    title="Scrolls the default into view",
    gallery=False,
    page=page,
    play=play,
)
