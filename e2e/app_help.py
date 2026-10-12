# e2e/app_help.py
"""Harness for the help popover and a code label (e2e/test_help_popover.py).

The long help comes first on the page and first in the sidebar, where less
room lies above the trigger than the help needs, so its popover opens below the
trigger and scrolls. The sidebar copy also sits at the viewport's left edge.
"""

import streamlit as st

from streamlit_listview import listview

OPTIONS = ["Apple", "Banana", "Cherry"]
LONG_HELP = "\n\n".join(f"Paragraph {i}." for i in range(1, 31))

listview("Long", OPTIONS, help=LONG_HELP, key="long")
listview("Linked", OPTIONS, help="See the [docs](https://example.com).", key="linked")
listview("`*`", OPTIONS, key="code")
with st.sidebar:
    listview("Sidebar long", OPTIONS, help=LONG_HELP, key="sidebar_long")
