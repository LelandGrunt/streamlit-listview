# e2e/app_on_change.py
"""Harness for e2e/test_on_change.py: the README's recipe for user input only.

It runs the README's own code block, the one that sets ``fruit_changed``, so
the test checks the recipe as a reader copies it. The recipe calls
``st.toast`` for user input only; the ``st`` it receives counts those calls.
"""

import re
import textwrap
from pathlib import Path

import streamlit as st

from streamlit_listview import listview

README = Path(__file__).resolve().parent.parent / "README.md"


@st.cache_resource
def recipe() -> str:
    """The README's recipe, read once per server: Streamlit runs this module
    again on every rerun. The block regex is the one tests/test_readme.py uses;
    the e2e package cannot import tests/."""
    blocks = re.findall(
        r"```python\n(.*?)```", README.read_text(encoding="utf-8"), flags=re.DOTALL
    )
    return next(textwrap.dedent(block) for block in blocks if "fruit_changed" in block)


class CountingStreamlit:
    """``st`` for the recipe, with ``st.toast`` counted."""

    def __getattr__(self, name):
        return getattr(st, name)

    def toast(self, *args, **kwargs):
        st.session_state.user_changes = st.session_state.get("user_changes", 0) + 1
        return st.toast(*args, **kwargs)


st.session_state.runs = st.session_state.get("runs", 0) + 1
namespace = {"st": CountingStreamlit(), "listview": listview}
exec(recipe(), namespace)

st.text(f"runs={st.session_state.runs}")
st.text(f"user_changes={st.session_state.get('user_changes', 0)}")
st.text(f"fruit_echo={namespace['fruit']!r}")
