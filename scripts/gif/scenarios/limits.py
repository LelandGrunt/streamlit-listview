"""Selection cap, disabled rows and widget, empty list, label visibility (test only)."""

from typing import Any

import streamlit as st

from scenarios._cities import CITIES
from stage import Scenario, Stage

PRESETS = (
    "Cap",
    "Disabled rows",
    "Disabled widget",
    "Empty",
    "Label hidden",
    "Label collapsed",
)
DISABLED = ("munich", "lyon", "osaka")
ROWS = [{**city, "disabled": city["id"] in DISABLED} for city in CITIES]


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    preset = (
        st.radio(
            "Preset",
            PRESETS,
            horizontal=True,
            key="preset",
            label_visibility="collapsed",
        )
        or PRESETS[0]
    )
    # Keeps the radio out of the frame's 12 px margin.
    st.markdown('<div style="height: 24px"></div>', unsafe_allow_html=True)
    # A key per preset, so each preset starts fresh.
    common: dict[str, Any] = {
        "height": 560,
        "width": 560,
        "key": f"gif_limits_{preset}",
    }
    if preset == "Cap":
        listview(
            "Cap · `max_selections=2`",
            CITIES,
            selection_mode="multi",
            max_selections=2,
            select_all=True,
            default=["berlin", "paris"],
            **common,
        )
    elif preset == "Disabled rows":
        listview(
            "Disabled rows · Munich, Lyon, Osaka",
            ROWS,
            selection_mode="multi",
            enable_search=True,
            select_all=True,
            **common,
        )
    elif preset == "Disabled widget":
        listview(
            "Disabled widget · `disabled=True`",
            CITIES,
            selection_mode="multi",
            disabled=True,
            **common,
        )
    elif preset == "Empty":
        listview("Empty · `placeholder`", [], placeholder="No cities yet", **common)
    elif preset == "Label hidden":
        listview("Hidden label", CITIES, label_visibility="hidden", **common)
    else:
        listview("Collapsed label", CITIES, label_visibility="collapsed", **common)


def play(stage: Stage) -> None:
    stage.snap("cap", 700)
    # At the cap a click on an unselected row changes nothing and reruns nothing.
    stage.opt("tokyo").click()
    stage.snap("cap-holds", 700)
    with stage.rerun():
        stage.control("Disabled rows").click()
    stage.snap("disabled-rows", 700)
    stage.opt("lyon").hover()
    stage.snap("hover-disabled-lyon", 700)
    stage.search.click()
    stage.search.press_sequentially("a", delay=50)
    stage.snap("search-a", 700)
    with stage.rerun():
        stage.select_all.click()
    stage.snap("select-all-matches", 900)
    for preset, step in (
        ("Disabled widget", "disabled-widget"),
        ("Empty", "empty"),
        ("Label hidden", "label-hidden"),
        ("Label collapsed", "label-collapsed"),
    ):
        with stage.rerun():
            stage.control(preset).click()
        stage.snap(step, 700)


SCENARIO = Scenario(
    name="limits",
    title="Selection cap, disabled rows and widget, empty list, label visibility",
    gallery=False,
    page=page,
    play=play,
)
