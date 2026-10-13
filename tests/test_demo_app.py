"""Runs of the demo script itself (demo/app.py) through Streamlit's AppTest.

The e2e suite drives the demo in a browser. These tests cover what a browser
cannot set up: another session changing the server theme at an exact point of
this session's run.
"""

import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "demo" / "app.py"
sys.path.insert(0, str(ROOT / "demo"))

import themes

_THEME_FILES = themes.discover_themes(ROOT / "demo" / ".streamlit")
_APPLIED, _OTHER = list(_THEME_FILES)[:2]


def _apply(name):
    text = _THEME_FILES[name].read_text(encoding="utf-8")
    themes.SERVER_THEME.apply(
        name, themes.flatten_theme(text), now=datetime.now(timezone.utc)
    )


# What another session does to the server theme. Each one runs on a thread of
# its own, as a second session's rerun would.
_OTHER_SESSION = {
    "reset": themes.SERVER_THEME.reset,
    "switch": lambda: _apply(_OTHER),
    "expire": lambda: themes.SERVER_THEME.expire(
        now=datetime.now(timezone.utc) + 2 * themes.THEME_TTL
    ),
}


@pytest.fixture
def theme_panel(monkeypatch):
    """An AppTest of the demo with the Theme section open and a theme applied."""
    monkeypatch.delenv(themes.SWITCHER_ENV, raising=False)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["cfg_section"] = "Theme"
    _apply(_APPLIED)
    yield at
    themes.SERVER_THEME.reset()


@pytest.mark.parametrize("change", list(_OTHER_SESSION))
def test_the_theme_panel_renders_one_theme_while_another_session_changes_it(
    theme_panel, monkeypatch, change
):
    """The panel reads the server theme once and renders that one throughout.

    It read ``SERVER_THEME.active`` again for each part, so a reset landing
    between two reads raised ``KeyError: None`` at the theme-file lookup, and
    a switch showed one theme in the picker and another theme's file.
    """
    fired = []
    caption = st.caption

    def caption_then_change(body, *args, **kwargs):
        element = caption(body, *args, **kwargs)
        if "Falls back to" in str(body):
            other = threading.Thread(target=_OTHER_SESSION[change])
            other.start()
            # A panel that rendered while holding the theme lock would block
            # the other session for good.
            other.join(timeout=10)
            assert not other.is_alive()
            fired.append(change)
        return element

    monkeypatch.setattr(st, "caption", caption_then_change)
    theme_panel.run()

    assert fired == [change]
    assert not theme_panel.exception
    assert theme_panel.selectbox(key="cfg_theme").value == _APPLIED
    # st.code drops the file's trailing newline.
    applied_text = _THEME_FILES[_APPLIED].read_text(encoding="utf-8").rstrip("\n")
    assert [c.value for c in theme_panel.code if c.language == "toml"] == [applied_text]


def test_the_theme_panel_shows_when_the_applied_theme_expires(theme_panel):
    theme_panel.run()

    expiry = f"{themes.SERVER_THEME.expires_at:%Y-%m-%d %H:%M} UTC"
    assert any(expiry in c.value for c in theme_panel.caption)
