"""One list, four looks: the layout parameters, switched by a radio above the frame."""

from typing import Any

import streamlit as st

from scenarios._cities import CITIES
from stage import Scenario, Stage

# Radio option -> (listview label, layout parameters, step name).
PRESETS: dict[str, tuple[str, dict[str, Any], str]] = {
    "Default": ("Default · no layout parameters", {}, "default"),
    "Compact": (
        "Compact · `content_font_size=12` · `show_grid_lines=False`",
        {"content_font_size": 12, "show_grid_lines": False},
        "compact",
    ),
    "Roomy": ("Roomy · `item_height=44`", {"item_height": 44}, "roomy"),
    "Sorted Z→A": (
        'Sorted Z→A · `sort="both"` · `sort_ascending=False`',
        {"sort": "both", "sort_ascending": False},
        "sorted-z-a",
    ),
}


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    preset = (
        st.radio(
            "Preset",
            list(PRESETS),
            horizontal=True,
            key="preset",
            label_visibility="collapsed",
        )
        or "Default"
    )
    # Keeps the radio out of the frame's 12 px margin.
    st.markdown('<div style="height: 24px"></div>', unsafe_allow_html=True)
    label, params, _ = PRESETS[preset]
    listview(
        label,
        CITIES,
        selection_mode="multi",
        default=["paris", "tokyo"],
        height=600,
        width=560,
        # One key for every preset, so the selection survives each switch.
        key="gif_layout",
        **params,
    )


def play(stage: Stage) -> None:
    for index, (preset, (_, _, step)) in enumerate(PRESETS.items()):
        if index:
            with stage.rerun():
                stage.control(preset).click()
        stage.snap(step, 1600)


SCENARIO = Scenario(
    name="layout",
    title="One list, four looks: font size, grid lines, row height, sort order",
    gallery=False,
    page=page,
    play=play,
)
