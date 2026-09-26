"""Multi-select with groups, search, a pinned + collapsible group UI, and a cap."""
import streamlit as st
from streamlit_listview import listview

CITIES = [
    {"id": "berlin", "label": "Berlin", "group": "Germany"},
    {"id": "munich", "label": "Munich", "group": "Germany"},
    {"id": "paris", "label": "Paris", "group": "France"},
    {"id": "rome", "label": "Rome", "group": "Italy"},
    {"id": "venice", "label": "Venice", "group": "Italy", "disabled": True},
]

selected = listview(
    "Pick up to two cities",
    CITIES,
    selection_mode="multi",
    max_selections=2,
    enable_search=True,
    pin_search=True,
    collapsible_groups=True,
    collapsed_groups=["Italy"],
    help="Items with the same **group** render under one sticky header.",
    key="grouped",
)
st.write("Selected:", selected)
