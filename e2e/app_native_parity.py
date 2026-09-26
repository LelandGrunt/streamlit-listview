# e2e/app_native_parity.py
"""Harness for the native-parity tests (e2e/test_native_parity.py).

One listview next to the Streamlit widgets whose parts it plays: the open
st.selectbox menu (row highlight), an active st.pills (selected row) and
st.text_input (search field). The references render on the same page so every
assertion compares two measured elements — never a hardcoded hex — and follows
whatever theme the module boots.

The list is deliberately shorter than its height, leaving empty space below the
last row for the click-to-focus test, and its groups are collapsible so the
headers render as <button>s.
"""
import streamlit as st

from streamlit_listview import listview

OPTIONS = [
    {"id": "apple", "label": "Apple", "group": "Fruit"},
    {"id": "banana", "label": "Banana", "group": "Fruit"},
    {"id": "cherry", "label": "Cherry", "group": "Fruit", "disabled": True},
    {"id": "carrot", "label": "Carrot", "group": "Veg"},
]

st.title("streamlit-listview e2e native parity app")

st.selectbox("reference selectbox", ["Apple", "Banana", "Carrot"], key="ref_sb")
st.pills("reference pills", ["Apple", "Banana"], default="Banana", key="ref_pills")
st.text_input("reference text input", key="ref_ti")
listview(
    "Parity list",
    OPTIONS,
    selection_mode="multi",
    default=["banana"],
    enable_search=True,
    collapsible_groups=True,
    height=400,
    key="parity_list",
)
