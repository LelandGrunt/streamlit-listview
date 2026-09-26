# e2e/app_sidebar_theme.py
"""Harness for the sidebar surface-color test (e2e/test_sidebar_theme.py).

The same grouped, searchable listview is rendered twice — once in st.sidebar,
once in the main body — each next to an st.selectbox in the SAME container.
The selectbox is the reference the assertions compare against: Streamlit fills
its control from --st-secondary-background-color, which its sidebar theme swaps
with --st-background-color. Reading both from one page is what makes the
comparison a real measurement rather than a hardcoded hex the test and the
stylesheet could drift away from together.
"""
import streamlit as st

from streamlit_listview import listview

OPTIONS = [
    {"id": "apple", "label": "Apple", "group": "Fruit"},
    {"id": "banana", "label": "Banana", "group": "Fruit"},
    {"id": "carrot", "label": "Carrot", "group": "Veg"},
]

st.title("streamlit-listview e2e sidebar theme app")

with st.sidebar:
    st.selectbox("sidebar reference", ["a", "b"], key="sidebar_ref")
    listview(
        "Sidebar list",
        OPTIONS,
        enable_search=True,
        height=200,
        key="sidebar_list",
    )

st.selectbox("main reference", ["a", "b"], key="main_ref")
listview(
    "Main list",
    OPTIONS,
    enable_search=True,
    height=200,
    key="main_list",
)
