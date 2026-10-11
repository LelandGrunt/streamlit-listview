"""100,000 options: the search stays pinned at the top while the list scrolls."""

from functools import cache

from data import make_large_dataset
from stage import Scenario, Stage


@cache
def options() -> list[dict[str, str]]:
    """The 100,000 options, built on first use and kept for the process.

    Not at import: generate.py, pytest and every take's server import the whole
    catalogue, and only this scenario's page needs the list.
    """
    return make_large_dataset(100_000)


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    listview(
        "100,000 options · `pin_search=True`",
        options(),
        selection_mode="multi",
        enable_search=True,
        pin_search=True,
        search_placeholder="Search 100,000 options…",
        collapsible_groups=True,
        height=480,
        width=560,
        key="gif_large_list",
    )


def play(stage: Stage) -> None:
    stage.snap("idle", 1000)
    for percent in (25, 60, 95):
        stage.scroll_list(percent / 100)
        stage.snap(f"scroll-{percent}", 900)
    stage.search.click()
    stage.snap("search-focus", 600)
    typed = ""
    for chunk in ("9", "99", "99"):
        stage.search.press_sequentially(chunk, delay=60)
        typed += chunk
        stage.snap(f"type-{typed}", 500)
    with stage.rerun():
        stage.opt("item-99999").click()
    stage.snap("select-99999", 1000)
    stage.search_clear.click()
    stage.snap("search-cleared", 1600)


SCENARIO = Scenario(
    name="large-list",
    title="100,000 options with a pinned search",
    gallery=False,
    page=page,
    play=play,
)
