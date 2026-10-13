# e2e/app_enum_ids.py
"""Harness for the enum-id round trip (e2e/test_enum_ids.py).

Two keyed lists whose option ids subclass str and int. JSON carries their
plain values, so the frontend keys the rows "red"/"blue" and "1"/"2", while
Python's str() spells them "Color.RED" and "Prio.HIGH". A click must come back
as the original option.
"""

import enum

import streamlit as st

from streamlit_listview import listview


class Color(str, enum.Enum):
    RED = "red"
    BLUE = "blue"


class Prio(enum.IntEnum):
    HIGH = 1
    LOW = 2

    def __str__(self) -> str:
        # Python 3.10's IntEnum.__str__; from 3.11 on, str() spells the value.
        return f"{type(self).__name__}.{self.name}"


st.title("streamlit-listview e2e enum-id app")

color = listview(
    "Color",
    [{"id": Color.RED, "label": "Red"}, {"id": Color.BLUE, "label": "Blue"}],
    height=120,
    key="color",
)
st.text(f"color_echo={color!r}")

prio = listview(
    "Priority",
    [Prio.HIGH, Prio.LOW],
    selection_mode="multi",
    format_func=lambda p: p.name.title(),
    height=120,
    key="prio",
)
st.text(f"prio_echo={prio!r}")
