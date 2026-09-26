"""Basic single selection over a plain list of strings."""
import streamlit as st
from streamlit_listview import listview

selected = listview(
    "Pick a city",
    ["Berlin", "Paris", "Rome", "Madrid", "Tokyo"],
    selection_mode="single",
    key="single",
)
st.write("Selected:", selected)
