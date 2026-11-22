"""streamlit_listview.testing, run against the real listview through AppTest.

Each test renders an app through AppTest, so the module needs the built bundle.
A Python 3.10 environment, where only Streamlit 1.65 installs, skips it: the
helper needs Streamlit 1.66.
"""

import importlib
import subprocess
import sys

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.usefixtures("built_bundle")
testing = pytest.importorskip("streamlit_listview.testing", exc_type=ImportError)

OPTIONS = [
    {"id": "dbo.Orders", "label": "Orders", "group": "dbo"},
    {"id": "dbo.Customers", "label": "Customers", "group": "dbo"},
    {"id": 7, "label": "Seven"},
    {"id": "old", "label": "Old", "disabled": True},
]
BASE = {
    "label": "**Tables**",
    "options": OPTIONS,
    "key": "tables",
    "selection_mode": "multi",
    "max_selections": 2,
    "default": ["dbo.Orders"],
}


def _app(params):
    import streamlit as st

    from streamlit_listview import listview

    st.write(f"picked={listview(**params)!r}")


def _sidebar_app():
    import streamlit as st

    from streamlit_listview import listview

    with st.sidebar:
        listview("Side", ["a"], key="side")


def _other_component_app():
    import streamlit as st

    other = st.components.v2.component("other_component", html="<div></div>")
    other(key="other")


def _run(**params):
    return AppTest.from_function(_app, args=(params,), default_timeout=60).run()


def test_get_listview_reads_the_payload():
    lv = testing.get_listview(_run(**BASE), "tables")
    assert (lv.key, lv.label, lv.disabled, lv.selection_mode) == (
        "tables",
        "**Tables**",
        False,
        "multi",
    )
    assert (lv.max_selections, lv.accept_new_options) == (2, False)


def test_options_follow_the_payload_order():
    assert testing.get_listview(_run(**BASE), "tables").options == [
        testing.Option("dbo.Orders", "Orders", "dbo", False),
        testing.Option("dbo.Customers", "Customers", "dbo", False),
        testing.Option(7, "Seven", None, False),
        testing.Option("old", "Old", None, True),
    ]


def test_selection_reads_the_stored_ids():
    assert testing.get_listview(_run(**BASE), "tables").selection == ["dbo.Orders"]


def test_a_listview_in_the_sidebar_is_found():
    at = AppTest.from_function(_sidebar_app, default_timeout=60).run()
    assert testing.get_listview(at, "side").label == "Side"


def test_a_missing_key_names_the_keys_that_exist():
    with pytest.raises(KeyError, match=r"'tables-1'.*'tables'"):
        testing.get_listview(_run(**BASE), "tables-1")


def test_get_listview_before_a_run_says_to_run_first():
    at = AppTest.from_function(_app, args=(BASE,), default_timeout=60)
    with pytest.raises(KeyError, match=r"at\.run\(\)"):
        testing.get_listview(at, "tables")


def test_another_component_with_the_key_is_no_listview():
    at = AppTest.from_function(_other_component_app, default_timeout=60).run()
    assert not at.exception
    with pytest.raises(KeyError, match="'other'"):
        testing.get_listview(at, "other")


def test_the_package_does_not_load_the_helper(tmp_path):
    script = (
        "import sys, streamlit_listview; "
        "print('streamlit_listview.testing' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout.strip() == "False"


def test_import_refuses_streamlit_before_1_66(monkeypatch):
    monkeypatch.setattr(streamlit, "__version__", "1.65.0")
    monkeypatch.delitem(sys.modules, "streamlit_listview.testing")
    with pytest.raises(
        ImportError, match=r"needs Streamlit 1\.66 or later; found 1\.65\.0"
    ):
        importlib.import_module("streamlit_listview.testing")
