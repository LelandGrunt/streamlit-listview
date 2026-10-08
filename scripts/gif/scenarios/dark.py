"""The hero and the Markdown scenario under the dark base theme (test only)."""

from scenarios import hero, markdown
from stage import Scenario, Stage, Take

DARK = ("--theme.base", "dark")


def page(take: str) -> None:
    (hero.page if take == "hero" else markdown.page)(take)


def play(stage: Stage) -> None:
    (hero.play if stage.take == "hero" else markdown.play)(stage)


SCENARIO = Scenario(
    name="dark",
    title="The hero and the Markdown scenario under the dark base theme",
    gallery=False,
    page=page,
    play=play,
    takes=(
        Take("hero", DARK),
        Take("markdown", DARK, clip_top=markdown.CLIP_TOP),
    ),
)
