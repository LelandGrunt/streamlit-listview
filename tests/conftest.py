import importlib
import sys
from pathlib import Path

import pytest
import streamlit as st


class FakeComponent:
    """Records the kwargs of the most recent mount call and returns a
    configurable result (an object exposing dict-style .get / __getitem__).

    When a test has NOT set ``return_value`` explicitly, the fake mirrors the V2
    runtime on first render: it echoes the seeded ``default=`` state passed by the
    wrapper. This keeps the unit suite honest about the ``default`` ->
    ``{"selection": ...}`` round-trip + the ``map_selection`` mapping, instead of
    always returning an empty selection and silently bypassing that contract.
    Tests needing a specific frontend result assign ``return_value`` directly.
    """

    _UNSET = object()

    def __init__(self):
        self.calls = []
        self.declared = None  # the factory kwargs, recorded at the first call
        self.declarations = 0  # how often the wrapper declared the component
        self._return_value = self._UNSET

    @property
    def return_value(self):
        return (
            {"selection": []}
            if self._return_value is self._UNSET
            else self._return_value
        )

    @return_value.setter
    def return_value(self, value):
        self._return_value = value

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self._return_value is self._UNSET:
            # First-render simulation: the V2 runtime returns the seeded default
            # state when no user interaction has produced a value yet.
            return kwargs.get("default", {"selection": []})
        return self._return_value

    @property
    def last(self):
        return self.calls[-1]


@pytest.fixture
def listview_mod(monkeypatch):
    """Import listview with st.components.v2.component patched to a FakeComponent.

    Yields (module, fake) where fake.last is the kwargs of the last mount call
    and fake.return_value can be set to drive the wrapper's return mapping.
    """
    fake = FakeComponent()

    def fake_factory(name, *, js=None, css=None, html=None, isolate_styles=True):
        fake.declarations += 1
        fake.declared = {
            "name": name,
            "js": js,
            "css": css,
            "html": html,
            "isolate_styles": isolate_styles,
        }
        return fake

    monkeypatch.setattr(st.components.v2, "component", fake_factory)

    # A fresh import starts without a declared component, so the first
    # listview() call declares it through the patched factory.
    sys.modules.pop("streamlit_listview", None)
    sys.modules.pop("streamlit_listview._options", None)
    mod = importlib.import_module("streamlit_listview")

    yield mod, fake

    # Clean up so other tests re-import against their own patch.
    sys.modules.pop("streamlit_listview", None)


BUILD = (
    Path(__file__).resolve().parent.parent / "streamlit_listview" / "frontend" / "build"
)


@pytest.fixture
def built_bundle():
    """Fail a test that renders the real listview when no bundle is built.

    AppTest resolves the component's index-*.js and index-*.css globs as a server
    does, so without a build the render fails with an error that names neither
    the build nor the command that makes it.
    """
    if not any(BUILD.glob("index-*.js")):
        pytest.fail(
            "This test renders the listview through AppTest and needs the built "
            "bundle: run npm run build in streamlit_listview/frontend."
        )
