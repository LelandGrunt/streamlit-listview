# e2e/conftest.py
"""Shared fixtures and locator helpers for the harness-app e2e modules
(everything directly under e2e/).

Each module declares which Streamlit script it drives and navigates to it
before every test; the launch/await preamble they used to duplicate lives here
instead — the same de-duplication e2e/demo/conftest.py already did for the
demo subpackage (whose own ``app_file`` / ``go_to_app`` shadow these). Servers
are booted once per distinct (script, flags) pair for the whole session and
shared across modules — see ``_servers``.

Per-module contract:

* ``APP_FILE`` (required) — ``Path`` of the Streamlit script to serve.
* ``EXTRA_ARGS`` (optional) — extra ``streamlit run`` flags, e.g. a theme.
* define a module-level ``go_to_app`` fixture to override the shared navigation
  (test_performance.py does: it times ``page.goto`` itself).
"""
import contextlib

import pytest
from playwright.sync_api import Page, expect

from e2e.e2e_utils import StreamlitRunner

# Harness script -> the number of listview instances it renders, awaited before
# any test interacts; ``None`` = do not assert it here. This is the one place
# the counts live: test_core.py and test_markdown.py drive the SAME harness
# (e2e/app.py), so a listview added there must not have to be mirrored in two
# test modules. Every harness is registered, so a new module that forgets to
# add itself fails loudly with a KeyError instead of silently skipping the wait.
LISTVIEW_COUNTS = {
    "app.py": 4,  # single, multi, default-seeded single, markdown
    "app_features.py": 7,  # search, pinned, collapsible, jump, newopt, selectall, sorted
    "app_remount.py": 1,  # keyed single that moves between sidebar and main
    "app_sidebar_theme.py": 2,  # the same list in the sidebar and the main body
    "app_native_parity.py": 1,  # one list beside the native widgets it mirrors
    # test_performance.py overrides go_to_app (it times page.goto itself), so no
    # count here is ever asserted. None rather than a number: a number nothing
    # reads is a number nothing keeps true.
    "app_performance.py": None,
    # Asserting example.py's instance count IS test_example_smoke's test, so
    # pre-asserting it here would duplicate the very thing under test.
    "example.py": None,
}


def stext(page: Page, name: str):
    """The harness's ``st.text(f"{name}=...")`` line — every harness reports
    state through these, so the one locator shape lives here."""
    return page.get_by_test_id("stText").filter(has_text=f"{name}=").first


def echo(page: Page, prefix: str):
    """The harness's echoed listview return value: ``st.text(f"{prefix}_echo=...")``."""
    return stext(page, f"{prefix}_echo")


@pytest.fixture(scope="module")
def app_file(request):
    """The Streamlit script the current module drives.

    Split out of ``app`` below so a whole subpackage whose modules share ONE
    harness can override just the path (e2e/demo/conftest.py does) instead of
    restating the launch — there is one StreamlitRunner call in this suite.
    """
    return request.module.APP_FILE


@pytest.fixture(scope="session")
def _servers():
    """Session-scoped cache of running harness servers.

    Keyed by (script, extra args): modules that drive the same script with the
    same flags share one boot — the five demo modules all serve demo/app.py —
    while a module with its own flags (test_core's theme) gets a distinct
    server automatically. Test isolation is unharmed: Streamlit session state
    lives per browser session and every test opens a fresh page. ExitStack
    stops every server at session end even if one teardown raises.
    """
    with contextlib.ExitStack() as stack:
        runners = {}

        def lookup(app_file, extra_args) -> StreamlitRunner:
            key = (str(app_file), tuple(extra_args or ()))
            if key not in runners:
                runners[key] = stack.enter_context(
                    StreamlitRunner(app_file, extra_args=list(key[1]))
                )
            return runners[key]

        yield lookup


@pytest.fixture(scope="module")
def app(request, app_file, _servers):
    """The Streamlit server for the current module — a cache lookup, not a boot.

    A failed boot raises out of the lookup without caching a runner, so every
    test in this module fails promptly via pytest's per-module fixture-error
    caching instead of hanging, and the next module that needs the same server
    retries the boot — the old boot-per-module failure semantics.
    """
    return _servers(app_file, getattr(request.module, "EXTRA_ARGS", None))


@pytest.fixture(autouse=True)
def go_to_app(page: Page, app: StreamlitRunner, app_file):
    page.goto(app.server_url)
    expected = LISTVIEW_COUNTS[app_file.name]
    if expected is not None:
        # Generous timeout: on a cold first navigation the component's
        # bundle/assets may still be compiling/serving, so the default 5s can
        # race and intermittently resolve to 0 elements.
        expect(page.get_by_test_id("stListview")).to_have_count(expected, timeout=20000)
