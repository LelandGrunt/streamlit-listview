"""Streamlit Listview demo — run with: streamlit run example.py"""
import streamlit as st

from streamlit_listview import listview

st.title("Streamlit Listview demo")

FRUIT = ["Apple", "Banana", "Cherry", "Date", "Elderberry"]

GROUPED = [
    {"id": "apple", "label": "Apple", "group": "Fruit"},
    {"id": "banana", "label": "Banana", "group": "Fruit"},
    {"id": "cherry", "label": "Cherry", "group": "Fruit", "disabled": True},
    {"id": "carrot", "label": "Carrot", "group": "Vegetable"},
    {"id": "potato", "label": "Potato", "group": "Vegetable"},
    {"id": "salmon", "label": "Salmon", "group": "Fish"},
    {"id": "tuna", "label": "Tuna", "group": "Fish"},
]

st.header("Single selection")
single = listview("Pick one fruit", FRUIT, selection_mode="single", key="single")
st.write("Selected:", single)

st.header("Multi selection (max 2)")
multi = listview(
    "Pick up to two",
    FRUIT,
    selection_mode="multi",
    max_selections=2,
    key="multi",
)
st.write("Selected:", multi)

st.header("Groups + collapsible + pinned search")
grouped = listview(
    "Search and collapse",
    GROUPED,
    selection_mode="multi",
    enable_search=True,
    pin_search=True,
    collapsible_groups=True,
    collapsed_groups=["Fish"],
    height=260,
    key="grouped",
)
st.write("Selected:", grouped)

st.header("Jump to default")
jumped = listview(
    "Pre-seeded + scrolled into view",
    GROUPED,
    selection_mode="single",
    default="tuna",
    height=140,
    key="jump",
)
st.write("Selected:", jumped)

st.header("Accept new options")
created = listview(
    "Add your own",
    FRUIT,
    selection_mode="multi",
    accept_new_options=True,
    key="newopt",
)
st.write("Selected:", created)

st.header("Markdown label & help + theming")
themed = listview(
    "**Pick** a :red[fruit] :material/star:",
    FRUIT,
    selection_mode="single",
    help=(
        "## How to choose\n\n"
        "Pick the **best** fruit. Supports GFM:\n\n"
        "- lists\n"
        "- [links](https://streamlit.io)\n"
        "- `code`\n"
    ),
    key="themed",
)
st.write("Selected:", themed)
