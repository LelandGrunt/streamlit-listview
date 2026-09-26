"""format_func transforms the displayed label; on_change fires before the rerun."""
import streamlit as st
from streamlit_listview import listview


def shout(option):
    # format_func maps an option to its display label, and listview only consults
    # it for options with no usable `label` of their own — which is why these
    # options carry none. Give one a `label` and it wins over shout().
    #
    # The option arrives as passed: a dict here, but a bare value if you hand
    # listview plain strings — so a preset that reads a field must cope with both.
    return str(option["id"] if isinstance(option, dict) else option).upper()


def on_change():
    st.toast("Selection changed", icon=":material/bolt:")


selected = listview(
    "Pick a city (labels shouted)",
    [{"id": "berlin"}, {"id": "paris"}],
    format_func=shout,
    on_change=on_change,
    key="events",
)
st.write("Selected:", selected)
