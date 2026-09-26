# e2e/app.py
import streamlit as st

from streamlit_listview import listview

# Grouped options: simple-value items plus one disabled dict item.
OPTIONS = [
    {"id": "apple", "label": "Apple", "group": "Fruit"},
    {"id": "banana", "label": "Banana", "group": "Fruit"},
    {"id": "cherry", "label": "Cherry", "group": "Fruit", "disabled": True},
    {"id": "carrot", "label": "Carrot", "group": "Vegetable"},
    {"id": "potato", "label": "Potato", "group": "Vegetable"},
]

st.title("streamlit-listview e2e core app")

st.subheader("Single")
single = listview(
    "Pick one",
    OPTIONS,
    selection_mode="single",
    height=200,
    key="single",
)
st.text(f"single_echo={single!r}")

st.subheader("Multi")
multi = listview(
    "Pick several",
    OPTIONS,
    selection_mode="multi",
    height=200,
    key="multi",
)
st.text(f"multi_echo={multi!r}")

st.subheader("Default")
default_single = listview(
    "Pick one (pre-seeded)",
    OPTIONS,
    selection_mode="single",
    default="banana",
    height=200,
    key="default_single",
)
st.text(f"default_echo={default_single!r}")

st.subheader("Markdown")
markdown_lv = listview(
    "**Pick** a :red[fruit] :material/check:",
    OPTIONS,
    selection_mode="single",
    height=200,
    help=(
        "## Choose wisely\n\n"
        "Pick the **best** fruit. "
        "See the [docs](https://example.com).\n\n"
        "- first\n"
        "- second\n"
    ),
    key="markdown",
)
st.text(f"markdown_echo={markdown_lv!r}")
