# e2e/app_remount.py
"""Harness for the container-move remount test (e2e/test_remount.py).

One keyed single-mode listview renders in st.sidebar or the main body,
depending on a checkbox. Moving a keyed widget between containers keeps its
Python-side widget state (keyed element ids drop the container) while the
frontend remounts from scratch — the scenario data["state_selection"] exists
for. `default=` deliberately names a DIFFERENT option than the one the test
selects, so a remount that wrongly re-seeded from `default` shows up as the
wrong row being highlighted, not as a coincidental pass.
"""
import streamlit as st

from streamlit_listview import listview

OPTIONS = [
    {"id": "apple", "label": "Apple"},
    {"id": "banana", "label": "Banana"},
    {"id": "carrot", "label": "Carrot"},
]

st.title("streamlit-listview e2e remount app")

if "change_count" not in st.session_state:
    st.session_state.change_count = 0


def on_change() -> None:
    st.session_state.change_count += 1


in_sidebar = st.checkbox("Render in sidebar", value=False, key="in_sidebar")
target = st.sidebar if in_sidebar else st.container()

with target:
    selected = listview(
        "Pick one",
        OPTIONS,
        selection_mode="single",
        default="apple",
        height=200,
        on_change=on_change,
        key="remount_single",
    )

st.text(f"remount_echo={selected!r}")
st.text(f"change_count={st.session_state.change_count}")
