"""The list scrolls its default into view when it first renders.

Each default is its own take, so each frame comes from a fresh mount. A key
change would remount the listview as well, but on a remount the component's
stylesheet arrives a frame after the first row is measured, and the list then
places the default row outside its frame. Switch to a key-change remount once
that is fixed.
"""

from data import make_large_dataset
from stage import Scenario, Stage, Take

OPTIONS = make_large_dataset(1_000)
DEFAULTS = ("item-00042", "item-00500", "item-00987")


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    listview(
        f"default = `{take}`",
        OPTIONS,
        selection_mode="single",
        default=take,
        height=300,
        width=560,
        key="gif_jump_to_default",
    )


def play(stage: Stage) -> None:
    stage.snap(f"default-{stage.take.removeprefix('item-')}", 1500)


SCENARIO = Scenario(
    name="jump-to-default",
    title="Scrolls the default into view",
    gallery=True,
    page=page,
    play=play,
    takes=tuple(Take(default) for default in DEFAULTS),
)
