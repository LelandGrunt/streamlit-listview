"""The README's hero GIF: live search, multi-select, select-all, a group collapsed."""

from scenarios._cities import CITIES
from stage import Scenario, Stage


def page(take: str) -> None:
    # Imported here, not at the top: importing the package declares the
    # component, which works only inside a Streamlit server, and generate.py
    # imports this catalogue in a plain process.
    from streamlit_listview import listview

    listview(
        "Cities",
        CITIES,
        selection_mode="multi",
        enable_search=True,
        pin_search=False,
        search_placeholder="Search cities…",
        collapsible_groups=True,
        select_all=True,
        height=640,
        width=560,
        help="Pick the cities you want to include.",
        key="gif_demo",
    )


def play(stage: Stage) -> None:
    stage.snap("idle", 1000)
    # Live search: a client-side filter, no rerun.
    stage.search.click()
    for typed in ("b", "be", "ber"):
        stage.search.press_sequentially(typed[-1], delay=70)
        stage.snap(f"search-{typed}", 260)
    stage.snap("search-hold", 1200)
    stage.search_clear.click()
    stage.snap("search-cleared", 1000)
    # Multi-select: each click reruns the script.
    for city in ("berlin", "paris", "tokyo"):
        with stage.rerun():
            stage.opt(city).click()
        stage.snap(f"select-{city}", 520)
    stage.snap("select-hold", 1100)
    with stage.rerun():
        stage.select_all.click()
    stage.snap("select-all", 1400)
    with stage.rerun():
        stage.select_all.click()
    stage.snap("deselect-all", 900)
    # Collapse and expand a group: client-side, no rerun.
    stage.group("USA").click()
    stage.snap("collapse-usa", 1100)
    stage.group("USA").click()
    stage.snap("expand-usa", 900)
    stage.snap("loop-hold", 700)


SCENARIO = Scenario(
    name="hero",
    title="Live search · collapsible groups · multi-select · select-all",
    gallery=True,
    page=page,
    play=play,
    gif_name="listview-demo.gif",
)
