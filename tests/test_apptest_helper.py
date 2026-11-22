"""streamlit_listview.testing, run against the real listview through AppTest.

Each test renders an app through AppTest, so the module needs the built bundle.
A Python 3.10 environment, where only Streamlit 1.65 installs, skips it: the
helper needs Streamlit 1.66. The coverage gate therefore needs Python 3.11.
"""

import enum
import importlib
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
import streamlit
from streamlit.testing.v1 import AppTest, AppTestError

pytestmark = pytest.mark.usefixtures("built_bundle")
testing = pytest.importorskip("streamlit_listview.testing", exc_type=ImportError)

if TYPE_CHECKING:
    from streamlit_listview.testing import ListviewElement

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
SINGLE = {
    **BASE,
    "selection_mode": "single",
    "max_selections": None,
    "default": "dbo.Orders",
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


def test_set_selection_then_run_returns_the_options():
    at = _run(**BASE)
    testing.get_listview(at, "tables").set_selection(["dbo.Customers", 7]).run()
    assert at.markdown[0].value == (
        "picked=[{'id': 'dbo.Customers', 'label': 'Customers', 'group': 'dbo'}, "
        "{'id': 7, 'label': 'Seven'}]"
    )


def test_selection_shows_the_write_after_a_run():
    at = _run(**BASE)
    lv = testing.get_listview(at, "tables")
    lv.set_selection(["dbo.Customers"]).run()
    assert lv.selection == ["dbo.Customers"]
    assert testing.get_listview(at, "tables").selection == ["dbo.Customers"]


def test_the_selection_lasts_over_later_runs():
    at = _run(**BASE)
    testing.get_listview(at, "tables").set_selection(["dbo.Customers"]).run()
    at.run()
    assert at.markdown[0].value.startswith("picked=[{'id': 'dbo.Customers'")


def test_none_clears_the_selection():
    at = _run(**BASE)
    testing.get_listview(at, "tables").set_selection(None).run()
    assert at.markdown[0].value == "picked=[]"


def test_single_mode_takes_one_id():
    at = _run(**SINGLE)
    testing.get_listview(at, "tables").set_selection(7).run()
    assert at.markdown[0].value == "picked={'id': 7, 'label': 'Seven'}"


def test_an_id_is_written_in_the_options_spelling():
    lv = testing.get_listview(_run(**BASE), "tables")
    lv.set_selection(["7"])
    assert lv.selection == [7]


def test_an_enum_member_is_written_as_its_value():
    class Color(str, enum.Enum):
        RED = "red"

    lv = testing.get_listview(
        _run(
            label="Colors",
            options=["red", "blue"],
            key="tables",
            selection_mode="multi",
        ),
        "tables",
    )
    lv.set_selection([Color.RED])
    assert lv.selection == ["red"]
    assert type(lv.selection[0]) is str


def test_a_tuple_counts_as_a_list_of_ids():
    lv = testing.get_listview(_run(**BASE), "tables")
    lv.set_selection(("dbo.Customers", 7))
    assert lv.selection == ["dbo.Customers", 7]


def test_a_selected_disabled_option_may_stay():
    at = _run(**{**BASE, "default": ["old"]})
    lv = testing.get_listview(at, "tables")
    lv.set_selection(["old", "dbo.Orders"]).run()
    assert lv.selection == ["old", "dbo.Orders"]


@pytest.mark.parametrize(
    ("params", "ids", "message"),
    [
        ({**BASE, "disabled": True}, ["dbo.Customers"], "disabled listview"),
        (BASE, ["old"], "disabled option 'old'"),
        (BASE, ["nope"], "no option 'nope'"),
        ({**BASE, "accept_new_options": True}, ["nope"], "no new entries"),
        (BASE, ["dbo.Orders", "dbo.Orders"], "twice"),
        (BASE, [7, "7"], "twice"),
        (SINGLE, ["dbo.Orders", 7], "takes one id"),
        (BASE, ["dbo.Orders", "dbo.Customers", 7], "max_selections=2"),
    ],
)
def test_a_selection_no_user_can_make_is_refused(params, ids, message):
    at = _run(**params)
    lv = testing.get_listview(at, "tables")
    before = lv.selection
    with pytest.raises(AppTestError, match=message):
        lv.set_selection(ids)
    assert testing.get_listview(at, "tables").selection == before


def test_an_id_of_another_type_raises_valueerror():
    lv = testing.get_listview(_run(**BASE), "tables")
    with pytest.raises(ValueError, match="selected id must be a str or int"):
        lv.set_selection([1.5])


def _raising_app():
    raise ValueError("boom")


def _no_listview_app():
    import streamlit as st

    st.write("nothing here")


def _changing_app():
    import streamlit as st

    from streamlit_listview import listview

    options = ["c"] if st.session_state.get("narrow", False) else ["a", "b"]
    listview("Pick", options, key="pick", selection_mode="multi")


def _counting_app():
    import streamlit as st

    from streamlit_listview import listview

    listview("Pick", ["a"], key=f"pick-{st.session_state.get('count', 0)}")


def test_import_names_the_version_before_streamlit_has_apptesterror(monkeypatch):
    """Streamlit before 1.63 has no AppTestError; the guard must speak first."""
    import streamlit.testing.v1 as apptest

    monkeypatch.setattr(streamlit, "__version__", "1.62.0")
    monkeypatch.delattr(apptest, "AppTestError")
    monkeypatch.delitem(sys.modules, "streamlit_listview.testing")
    with pytest.raises(
        ImportError, match=r"needs Streamlit 1\.66 or later; found 1\.62\.0"
    ):
        importlib.import_module("streamlit_listview.testing")


def test_a_run_that_raised_names_the_exception():
    at = AppTest.from_function(_raising_app, default_timeout=60).run()
    with pytest.raises(KeyError) as raised:
        testing.get_listview(at, "tables")
    assert "boom" in str(raised.value)
    assert "at.run()" not in str(raised.value)


def test_a_run_without_a_listview_does_not_say_to_run_first():
    at = AppTest.from_function(_no_listview_app, default_timeout=60).run()
    with pytest.raises(KeyError) as raised:
        testing.get_listview(at, "tables")
    assert "at.run()" not in str(raised.value)


def test_a_reused_element_checks_the_latest_run():
    at = AppTest.from_function(_changing_app, default_timeout=60).run()
    lv = testing.get_listview(at, "pick")
    at.session_state["narrow"] = True
    at.run()
    assert lv.options == [testing.Option("c", "c", None, False)]
    with pytest.raises(AppTestError, match="no option 'b'"):
        lv.set_selection(["b"])


def test_a_reused_element_names_the_keys_of_the_latest_run():
    at = AppTest.from_function(_counting_app, default_timeout=60).run()
    lv = testing.get_listview(at, "pick-0")
    at.session_state["count"] = 1
    at.run()
    with pytest.raises(KeyError, match=r"'pick-0'.*'pick-1'"):
        _ = lv.selection


def test_a_list_of_str_is_a_valid_argument():
    """ty checks this call against set_selection's hint: a list is invariant."""
    ids: list[str] = ["dbo.Customers"]
    lv: ListviewElement = testing.get_listview(_run(**BASE), "tables")
    lv.set_selection(ids)
    assert lv.selection == ["dbo.Customers"]


@pytest.mark.parametrize(
    "ids",
    [{"dbo.Orders"}, (i for i in ["dbo.Orders"]), {"dbo.Orders": 1}.keys()],
    ids=["set", "generator", "dict_keys"],
)
def test_another_container_is_named(ids):
    lv = testing.get_listview(_run(**BASE), "tables")
    with pytest.raises(ValueError, match="one id, a list or a tuple of ids, or None"):
        lv.set_selection(ids)


@pytest.mark.parametrize("ids", [OPTIONS[1], [OPTIONS[1]]], ids=["alone", "in_a_list"])
def test_an_option_dict_is_named(ids):
    lv = testing.get_listview(_run(**BASE), "tables")
    with pytest.raises(ValueError, match="Pass the option's id"):
        lv.set_selection(ids)


def test_a_listview_under_another_element_class_is_found(monkeypatch):
    """A later Streamlit may give V2 components a class of their own."""
    at = _run(**BASE)

    class FutureElement:
        def __init__(self, element):
            self.proto = element.proto
            self.key = element.key

    found = [FutureElement(element) for element in at.get("bidi_component")]
    monkeypatch.setattr(at, "get", lambda element_type: found)
    assert testing.get_listview(at, "tables").label == "**Tables**"
