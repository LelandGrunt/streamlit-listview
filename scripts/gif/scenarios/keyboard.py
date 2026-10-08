"""Single selection by keyboard; a badge in the frame shows each key."""

from scenarios._cities import CITIES
from stage import Scenario, Stage


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    listview(
        "Cities",
        CITIES,
        selection_mode="single",
        enable_search=True,
        search_placeholder="Search cities…",
        height=640,
        width=560,
        key="gif_keyboard",
    )


def play(stage: Stage) -> None:
    stage.snap("idle", 900)
    stage.search.click()
    stage.snap("click-search", 700)
    stage.press("Tab", badge=True)
    stage.snap("tab-to-list", 700)
    for n in (1, 2, 3):
        stage.press("ArrowDown", badge=True)
        stage.snap(f"down-{n}", 450)
    with stage.rerun():
        stage.press("Enter", badge=True)
    stage.snap("enter-selects-hamburg", 1000)
    stage.press("End", badge=True)
    stage.snap("end", 800)
    stage.press("Home", badge=True)
    stage.snap("home", 800)
    stage.press("/", badge=True)
    stage.snap("slash-to-search", 800)
    for key in ("o", "s"):
        stage.press(key, badge=True)
        stage.snap(f"type-{key}", 450)
    # With text in the field its clear button comes next in the tab order.
    stage.press("Tab", badge=True)
    stage.snap("tab-to-clear", 500)
    stage.press("Tab", badge=True)
    stage.snap("tab-back-to-list", 600)
    stage.press("ArrowDown", badge=True)
    stage.snap("down-to-osaka", 500)
    with stage.rerun():
        stage.press("Enter", badge=True)
    stage.snap("enter-selects-osaka", 1000)
    stage.press("Escape", badge=True)
    stage.snap("escape-clears-search", 1400)
    stage.badge(None)
    stage.snap("loop-hold", 600)


SCENARIO = Scenario(
    name="keyboard",
    title="Keyboard: arrows, Home/End, Enter, / to search, Esc to clear",
    gallery=True,
    page=page,
    play=play,
)
