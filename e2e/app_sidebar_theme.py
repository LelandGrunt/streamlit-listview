# e2e/app_sidebar_theme.py
"""Harness for the sidebar surface-color test (e2e/test_sidebar_theme.py).

The same grouped, searchable listview with an add field is rendered twice —
once in st.sidebar, once in the main body — each next to an st.selectbox and an
st.dataframe in the SAME container.
They are the references the assertions compare against: the open selectbox menu
for the list surface, and the dataframe header for the group band. Streamlit
gives the sidebar a theme of its own, so each container resolves them from its
own tokens. Reading both from one page is what makes the comparison a real
measurement rather than a hardcoded hex the test and the stylesheet could drift
away from together.
"""

import streamlit as st

from streamlit_listview import listview

OPTIONS = [
    {"id": "apple", "label": "Apple", "group": "Fruit"},
    {"id": "banana", "label": "Banana", "group": "Fruit"},
    {"id": "carrot", "label": "Carrot", "group": "Veg"},
]
# Short column labels leave most of the header row bare, so its fill is the
# most common colour of a strip across it.
TABLE = {"a": [1, 2], "b": [3, 4], "c": [5, 6]}

st.title("streamlit-listview e2e sidebar theme app")

with st.sidebar:
    st.selectbox("sidebar reference", ["a", "b"], key="sidebar_ref")
    listview(
        "Sidebar list",
        OPTIONS,
        enable_search=True,
        accept_new_options=True,
        height=200,
        key="sidebar_list",
    )
    st.dataframe(TABLE, hide_index=True)

st.selectbox("main reference", ["a", "b"], key="main_ref")
listview(
    "Main list",
    OPTIONS,
    enable_search=True,
    accept_new_options=True,
    height=200,
    key="main_list",
)
st.dataframe(TABLE, hide_index=True)
