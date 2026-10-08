"""Markdown in the widget label and in the help tooltip.

The component renders Markdown in `label` and `help` only; option labels are
plain text, so the options here are plain city names.
"""

import streamlit as st

from stage import Scenario, Stage, Take

# The help popover opens above its trigger. The frame reaches this far above the
# listview, and the page leaves the same room above it.
CLIP_TOP = 195

OPTIONS = ["Berlin", "Paris", "Tokyo", "Kyoto", "Seattle", "New York"]

HELP = (
    "**Markdown** in `help`:\n\n"
    "- `:red[…]` → :red[red text]\n"
    "- `:blue-badge[…]` → :blue-badge[badge]\n"
    "- `:material/…:` → :material/flight:\n"
    "- emoji → :tada:\n\n"
    "*Lists, tables and code blocks work too.*"
)


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    st.markdown(f'<div style="height: {CLIP_TOP}px"></div>', unsafe_allow_html=True)
    listview(
        ":material/travel_explore: **Destinations** :blue-badge[label] "
        "with :orange[*Markdown*] :tada:",
        OPTIONS,
        selection_mode="multi",
        height=260,
        width=560,
        help=HELP,
        key="gif_markdown",
    )


def play(stage: Stage) -> None:
    stage.snap("idle", 1200)
    with stage.rerun():
        stage.opt("Paris").click()
    stage.snap("select-paris", 700)
    stage.help_icon.hover()
    stage.snap("help-open", 3200)
    stage.park_pointer()
    stage.snap("help-closed", 900)


SCENARIO = Scenario(
    name="markdown",
    title="Markdown in the label and the help tooltip",
    gallery=True,
    page=page,
    play=play,
    takes=(Take(clip_top=CLIP_TOP),),
)
