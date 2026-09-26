"""Behavior flags: cap selections, let users add their own, or lock the list."""
import streamlit as st
from streamlit_listview import listview

LABELS = ["bug", "enhancement", "documentation", "question", "help wanted"]

# accept_new_options lets users add entries that aren't in the list (each comes
# back as the plain typed string); max_selections caps how many can be picked.
labels = listview(
    "Tag this issue (up to 3 — or type your own)",
    LABELS,
    selection_mode="multi",
    max_selections=3,
    accept_new_options=True,
    enable_search=True,
    help="Pick existing labels, or type a new one and press Enter to add it.",
    key="behavior_tags",
)
st.write("Labels:", labels)

# disabled renders the list greyed-out and non-interactive — useful while a
# prerequisite step is incomplete or data is still loading.
listview(
    "Locked until the steps above are done",
    LABELS,
    selection_mode="multi",
    default=["bug"],
    disabled=True,
    key="behavior_locked",
)
