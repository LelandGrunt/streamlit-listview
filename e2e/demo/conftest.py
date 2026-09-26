# e2e/demo/conftest.py
"""Shared fixtures for the demo-app e2e modules (everything in e2e/demo/).

Every module in this package drives the demo playground (demo/app.py), so what
this conftest overrides from e2e/conftest.py is deliberately narrow:

* ``app_file`` — up there each module names its own harness via ``APP_FILE``,
  whereas all five here share one, so the path belongs in this conftest rather
  than in five modules. The StreamlitRunner launch itself is NOT repeated: the
  parent's ``app`` fixture consumes this path, so anything added to the launch
  (a timeout knob, a retry, a warm-up) lands in one place — and since its
  session cache keys servers by (script, flags), the five modules share ONE
  demo server boot.
* ``go_to_app`` — the readiness gate genuinely differs. The harness apps render a
  fixed, asserted number of listviews; the demo renders a configurable one, so it
  waits for the first to be visible instead of counting.
"""
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from e2e.e2e_utils import StreamlitRunner

ROOT = Path(__file__).parent.parent.parent.absolute()
APP_FILE = ROOT / "demo" / "app.py"

# Locator note: the demo's st.pills / st.segmented_control options render as
# <button type="button" role="radio"> inside a role="radiogroup" (Streamlit
# builds them on react-aria-components). The explicit ARIA role overrides the
# implicit one, so they are reachable as get_by_role("radio", ...) and NOT as
# get_by_role("button", ...). Plain st.button widgets stay role="button".


@pytest.fixture(scope="module")
def app_file():
    """Every module in this package drives the demo playground."""
    return APP_FILE


@pytest.fixture(autouse=True)
def go_to_app(page: Page, app: StreamlitRunner):
    page.goto(app.server_url)
    expect(page.get_by_test_id("stListview").first).to_be_visible(timeout=20000)
