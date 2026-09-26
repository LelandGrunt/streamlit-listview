import atexit
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st

# ---------------------------------------------------------------------------
# Module-level patch: st.components.v2.component is called at import time in
# streamlit_listview/__init__.py (the declaration line). When test_options.py does
#   from streamlit_listview._options import ...
# Python processes the streamlit_listview package, executing __init__.py, which calls
# st.components.v2.component(js="index-*.js", css="index-*.css", ...). Without
# a built frontend, the js=/css= globs match nothing and this raises
# StreamlitComponentRegistryError — which derives straight from streamlit's Error,
# NOT from StreamlitAPIException, so it cannot be caught as one. Patching the
# factory here (conftest.py is loaded BEFORE test modules are imported) makes the
# package importable in all tests regardless of whether they use listview_mod.
# The per-test listview_mod fixture replaces the module-cached _component with
# a fresh FakeComponent and does a clean re-import, so these tests are unaffected.
# ---------------------------------------------------------------------------
_import_time_fake = MagicMock(return_value=MagicMock(return_value={"selection": []}))
_import_time_patcher = patch.object(st.components.v2, "component", _import_time_fake)
_import_time_patcher.start()
# Pair the import-time start() with a stop() so this global patch does not leak
# past the test session: without it, st.components.v2.component would stay
# replaced by the fake for the entire process (even for code outside the
# listview_mod fixture). atexit restores the real factory when pytest exits.
atexit.register(_import_time_patcher.stop)


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
        self._return_value = self._UNSET

    @property
    def return_value(self):
        return {"selection": []} if self._return_value is self._UNSET else self._return_value

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

    Yields (module, fake) where fake.last is the kwargs of the last _component
    call and fake.return_value can be set to drive the wrapper's return mapping.
    """
    fake = FakeComponent()

    def fake_factory(name, *, js=None, css=None, html=None, isolate_styles=True):
        fake.declared = {
            "name": name,
            "js": js,
            "css": css,
            "html": html,
            "isolate_styles": isolate_styles,
        }
        return fake

    monkeypatch.setattr(st.components.v2, "component", fake_factory)

    # Ensure a fresh import so the patched factory is used for the
    # module-level declaration.
    sys.modules.pop("streamlit_listview", None)
    sys.modules.pop("streamlit_listview._options", None)
    mod = importlib.import_module("streamlit_listview")

    yield mod, fake

    # Clean up so other tests re-import against their own patch.
    sys.modules.pop("streamlit_listview", None)
