# e2e/test_native_parity_dark.py
"""The native-parity suite again, under the dark theme.

Every test in test_native_parity.py compares the listview with a native widget
on the same page, so it holds in any theme — but the dark theme is where the row
highlight takes the other branch of Streamlit's formula (bgMix lightened by 60
HSL points instead of darkened by 30), and only a dark boot exercises it. The
tests are re-collected here; the conftest boots this module's own server from
EXTRA_ARGS.
"""
from e2e.test_native_parity import *  # noqa: F401,F403 — the same tests, re-collected
from e2e.test_native_parity import APP_FILE  # noqa: F401 — read by the conftest

EXTRA_ARGS = ["--theme.base", "dark"]
