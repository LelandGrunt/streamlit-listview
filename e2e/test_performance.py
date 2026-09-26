# e2e/test_performance.py
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import echo
from e2e.e2e_utils import StreamlitRunner  # the app fixture's type, for annotations
from e2e.perf_dataset import N

# The harness e2e/conftest.py serves for this module.
APP_FILE = Path(__file__).with_name("app_performance.py")

# Derive the ids and search text this module types from the SAME generator, at
# the SAME N, the harness renders — re-spelling make_large_dataset's id format
# as literals here drifts the moment the generator changes. demo/ is not a
# package, so it goes on sys.path first (the import the harness itself does).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
from data import make_large_dataset  # noqa: E402

_ROWS = make_large_dataset(N)
FIRST_ID = _ROWS[0]["id"]
LAST_ID = _ROWS[-1]["id"]
# The last label's zero-padded number ("Item 04999" -> "04999"): unique among
# the N labels, so searching it narrows the list to exactly one row.
LAST_LABEL_NEEDLE = _ROWS[-1]["label"].split()[-1]
# Generous on purpose: guards against pathological regressions, not micro-timing,
# so it does not flake on a loaded CI box.
RENDER_BUDGET_S = 15.0


@pytest.fixture(autouse=True)
def go_to_app():
    """Opt out of the shared navigation (e2e/conftest.py) by overriding it.

    Both tests navigate themselves, and the budget test times its own
    ``page.goto`` — pre-navigating would make it measure a second, already-warm
    load instead of the cold render it is there to guard.
    """


def test_large_list_renders_all_rows_within_budget(page: Page, app: StreamlitRunner):
    start = time.perf_counter()
    page.goto(app.server_url)
    root = page.get_by_test_id("stListview").first
    expect(root).to_be_visible(timeout=20000)
    # Non-virtualized: the LAST row existing in the DOM proves the whole list
    # rendered. Assert presence (count), not visibility — it sits below the fold.
    last = root.get_by_test_id(f"stListviewOption-{LAST_ID}")
    expect(last).to_have_count(1, timeout=30000)
    elapsed = time.perf_counter() - start
    assert elapsed < RENDER_BUDGET_S, f"render took {elapsed:.1f}s (budget {RENDER_BUDGET_S}s)"


def test_large_list_stays_responsive(page: Page, app: StreamlitRunner):
    page.goto(app.server_url)
    root = page.get_by_test_id("stListview").first
    expect(root).to_be_visible(timeout=20000)

    # Search narrows N rows to a single label-unique match (the number of the
    # last item's label).
    root.get_by_test_id("stListviewSearch").fill(LAST_LABEL_NEEDLE)
    options = root.locator("[data-testid^='stListviewOption-']")
    expect(options).to_have_count(1, timeout=10000)
    expect(root.get_by_test_id(f"stListviewOption-{LAST_ID}")).to_be_visible()

    # Clear the search and select the first row; the selection echoes back.
    root.get_by_test_id("stListviewSearch").fill("")
    first = root.get_by_test_id(f"stListviewOption-{FIRST_ID}")
    first.click()
    expect(first).to_have_attribute("aria-selected", "true")
    expect(echo(page, "perf")).to_contain_text(FIRST_ID, timeout=10000)
