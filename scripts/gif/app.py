"""Minimal capture page for the README demo GIF (one well-configured listview)."""

import streamlit as st

from streamlit_listview import listview

st.set_page_config(page_title="streamlit-listview", layout="centered")

# Strip Streamlit chrome so the frame is just the component.
st.markdown(
    """
    <style>
      header[data-testid="stHeader"], [data-testid="stToolbar"],
      #MainMenu, footer {display: none !important;}
      .block-container {padding-top: 1.5rem; padding-bottom: 1rem; max-width: 640px;}
    </style>
    """,
    unsafe_allow_html=True,
)

CITIES = [
    {"id": "berlin", "label": "Berlin", "group": "Germany"},
    {"id": "munich", "label": "Munich", "group": "Germany"},
    {"id": "hamburg", "label": "Hamburg", "group": "Germany"},
    {"id": "paris", "label": "Paris", "group": "France"},
    {"id": "lyon", "label": "Lyon", "group": "France"},
    {"id": "marseille", "label": "Marseille", "group": "France"},
    {"id": "tokyo", "label": "Tokyo", "group": "Japan"},
    {"id": "osaka", "label": "Osaka", "group": "Japan"},
    {"id": "kyoto", "label": "Kyoto", "group": "Japan"},
    {"id": "newyork", "label": "New York", "group": "USA"},
    {"id": "chicago", "label": "Chicago", "group": "USA"},
    {"id": "seattle", "label": "Seattle", "group": "USA"},
]

listview(
    "Cities",
    CITIES,
    selection_mode="multi",
    enable_search=True,
    pin_search=False,
    search_placeholder="Search cities…",
    collapsible_groups=True,
    select_all=True,
    height=640,
    width=560,
    help="Pick the cities you want to include.",
    key="gif_demo",
)
