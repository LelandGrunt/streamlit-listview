"""The GIF scenario catalogue: scenario name -> Scenario, the gallery scenario first.

demo/ goes on sys.path because two scenarios reuse the demo's dataset generator
(demo/data.py), as the demo's own tests do.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "demo"))

from scenarios import (
    add_options,
    dark,
    hero,
    jump_to_default,
    keyboard,
    large_list,
    layout,
    limits,
    markdown,
    sidebar,
    themes,
)
from stage import Scenario

SCENARIOS: dict[str, Scenario] = {
    scenario.name: scenario
    for scenario in (
        # The gallery scenario: the only one that builds a GIF.
        hero.SCENARIO,
        # Test scenarios: recorded, never a GIF.
        keyboard.SCENARIO,
        add_options.SCENARIO,
        markdown.SCENARIO,
        layout.SCENARIO,
        themes.SCENARIO,
        large_list.SCENARIO,
        jump_to_default.SCENARIO,
        dark.SCENARIO,
        sidebar.SCENARIO,
        limits.SCENARIO,
    )
}
