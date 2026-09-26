# e2e/app_features.py
import streamlit as st

from streamlit_listview import listview

# Enough items that the jump target sits below the fold in a short list.
OPTIONS = [
    {"id": "apple", "label": "Apple", "group": "Fruit"},
    {"id": "banana", "label": "Banana", "group": "Fruit"},
    {"id": "cherry", "label": "Cherry", "group": "Fruit"},
    {"id": "carrot", "label": "Carrot", "group": "Vegetable"},
    {"id": "potato", "label": "Potato", "group": "Vegetable"},
    {"id": "onion", "label": "Onion", "group": "Vegetable"},
    {"id": "salmon", "label": "Salmon", "group": "Fish"},
    {"id": "tuna", "label": "Tuna", "group": "Fish"},
]

st.title("streamlit-listview e2e features app")

st.subheader("Search")
searched = listview(
    "Search me",
    OPTIONS,
    selection_mode="single",
    enable_search=True,
    height=200,
    key="search",
)
st.text(f"search_echo={searched!r}")

st.subheader("Pinned search")
pinned = listview(
    "Pinned search",
    OPTIONS,
    selection_mode="single",
    enable_search=True,
    pin_search=True,
    height=160,
    key="pinned",
)
st.text(f"pinned_echo={pinned!r}")

st.subheader("Collapsible")
collapsed = listview(
    "Collapse me",
    OPTIONS,
    selection_mode="multi",
    enable_search=True,
    collapsible_groups=True,
    collapsed_groups=["Fish"],
    height=240,
    key="collapsible",
)
st.text(f"collapsible_echo={collapsed!r}")

st.subheader("Jump to default")
jumped = listview(
    "Jump",
    OPTIONS,
    selection_mode="single",
    default="tuna",
    height=140,
    key="jump",
)
st.text(f"jump_echo={jumped!r}")

st.subheader("Accept new options")
created = listview(
    "Add your own",
    OPTIONS,
    selection_mode="multi",
    accept_new_options=True,
    height=200,
    key="newopt",
)
st.text(f"newopt_echo={created!r}")

st.subheader("Select all")
if "selectall_runs" not in st.session_state:
    st.session_state.selectall_runs = 0


def _selectall_changed():
    st.session_state.selectall_runs += 1


selectall = listview(
    "Bulk select",
    OPTIONS,
    selection_mode="multi",
    select_all=True,
    enable_search=True,
    height=200,
    on_change=_selectall_changed,
    key="selectall",
)
st.text(f"selectall_echo={selectall!r}")
st.text(f"selectall_runs={st.session_state.selectall_runs}")

st.subheader("Sort")
sorted_ = listview(
    "Sorted",
    OPTIONS,
    selection_mode="single",
    sort="both",
    height=240,
    key="sorted",
)
st.text(f"sorted_echo={sorted_!r}")
