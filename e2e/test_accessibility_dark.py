# e2e/test_accessibility_dark.py
"""The accessibility scan again, under the dark theme, where every surface and
every text color changes, and with them the contrast."""

from e2e.test_accessibility import *  # the same tests, re-collected
from e2e.test_accessibility import APP_FILE  # noqa: F401 — read by the conftest

EXTRA_ARGS = ["--theme.base", "dark"]
