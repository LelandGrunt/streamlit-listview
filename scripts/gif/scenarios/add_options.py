"""accept_new_options: a new value becomes a row; a known label selects its row."""

from scenarios._cities import CITIES
from stage import Scenario, Stage


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    listview(
        "Cities · `accept_new_options=True`",
        CITIES,
        selection_mode="multi",
        accept_new_options=True,
        # Room for the 12 cities, Vienna, the 4 group headers and the header of
        # the options without a group; the add field sits in the footer below.
        height=680,
        width=560,
        key="gif_add_options",
    )


def _type(stage: Stage, chunks: tuple[str, ...]) -> None:
    typed = ""
    for chunk in chunks:
        stage.new_option.press_sequentially(chunk, delay=60)
        typed += chunk
        stage.snap(f"type-{typed.lower()}", 350)


def play(stage: Stage) -> None:
    stage.snap("idle", 900)
    stage.new_option.click()
    stage.snap("focus-add-field", 600)
    _type(stage, ("Vi", "en", "na"))
    with stage.rerun():
        stage.new_option.press("Enter")
    stage.snap("vienna-added", 1500)
    _type(stage, ("pa", "ri", "s"))
    with stage.rerun():
        stage.new_option.press("Enter")
    stage.snap("paris-selected", 1800)


SCENARIO = Scenario(
    name="add-options",
    title="Add new options; a known label selects its row",
    gallery=False,
    page=page,
    play=play,
)
