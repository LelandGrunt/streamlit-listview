"""The same list in four app themes. A theme is server configuration, so each
theme is a take with its own server.

Two takes use theme files the demo ships (demo/.streamlit/), passed as one
``--theme.*`` flag per option. Their fonts come from Google Fonts, so this
scenario needs the network; a font that fails to load changes the frames.
"""

from pathlib import Path

from scenarios._cities import CITIES
from stage import Scenario, Stage, Take
from themes import flatten_theme, theme_labels

DEMO_THEMES = Path(__file__).resolve().parents[3] / "demo" / ".streamlit"
BRAND_THEMES = ("databricks_brand", "snowflake_brand")


def theme_flags(name: str) -> tuple[str, ...]:
    """Every option of ``config_theme_<name>.toml`` as ``streamlit run`` flags."""
    text = (DEMO_THEMES / f"config_theme_{name}.toml").read_text(encoding="utf-8")
    flags: list[str] = []
    for key, value in flatten_theme(text).items():
        if isinstance(value, list):
            raise TypeError(f"{key} is a list; a theme flag takes one value")
        flags += [
            f"--{key}",
            str(value).lower() if isinstance(value, bool) else str(value),
        ]
    return tuple(flags)


def _take_name(name: str) -> str:
    return name.replace("_", "-")


DISPLAY_NAMES = theme_labels(DEMO_THEMES)
LABELS = {
    "light": "Light theme · `--theme.base light`",
    "dark": "Dark theme · `--theme.base dark`",
    **{
        _take_name(name): (
            f"{DISPLAY_NAMES.get(name, name)} theme · `config_theme_{name}.toml`"
        )
        for name in BRAND_THEMES
    },
}


def page(take: str) -> None:
    from streamlit_listview import listview  # inside page(): see hero.py

    listview(
        LABELS[take],
        CITIES,
        selection_mode="multi",
        enable_search=True,
        search_placeholder="Search cities…",
        collapsible_groups=True,
        height=600,
        width=560,
        key="gif_themes",
    )


def play(stage: Stage) -> None:
    stage.snap("idle", 800)
    with stage.rerun():
        stage.opt("paris").click()
    stage.snap("select-paris", 500)
    with stage.rerun():
        stage.opt("kyoto").click()
    stage.opt("tokyo").hover()
    stage.snap("select-kyoto-hover-tokyo", 1500)


SCENARIO = Scenario(
    name="themes",
    title="Follows the app theme: light, dark and two brand themes",
    gallery=False,
    page=page,
    play=play,
    # Streamlit's own themes first, then the demo's brand themes, so a
    # recording reads from the familiar to the custom.
    takes=(
        Take("light", ("--theme.base", "light")),
        Take("dark", ("--theme.base", "dark")),
        *(Take(_take_name(name), theme_flags(name)) for name in BRAND_THEMES),
    ),
)
