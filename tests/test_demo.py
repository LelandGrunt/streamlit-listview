"""Unit tests for the demo's pure logic modules (demo/ is not a package)."""
import ast
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))

import data  # noqa: E402
import parsing  # noqa: E402
import codegen  # noqa: E402
import dataset  # noqa: E402


def test_dataset_shape():
    assert len(data.CITIES) >= 30
    ids = [c["id"] for c in data.CITIES]
    assert len(ids) == len(set(ids)), "ids must be unique"
    assert all("label" in c and "group" in c for c in data.CITIES)
    assert any(c.get("disabled") for c in data.CITIES), "expected >=1 disabled item"


def test_groups_are_ordered_unique():
    # data.GROUPS is derived through the one shared helper (parsing.group_names),
    # not a second spelling of the ordered-unique rule.
    assert data.GROUPS == parsing.group_names(data.CITIES)
    assert len(data.GROUPS) == len(set(data.GROUPS))


def test_group_names_orders_dedupes_and_skips_groupless():
    # Scalars and dicts without `group` contribute nothing; first occurrence
    # fixes a group's position.
    options = [
        {"id": "a", "group": "G1"},
        "scalar",
        {"id": "b"},
        {"id": "c", "group": "G2"},
        {"id": "d", "group": "G1"},
    ]
    assert parsing.group_names(options) == ["G1", "G2"]
    assert parsing.group_names([]) == []


def test_dataset_accepted_by_listview_normalizer():
    from streamlit_listview._options import normalize_options

    items, id_to_original = normalize_options(data.CITIES, str)
    assert len(items) == len(data.CITIES)


def test_format_presets_take_an_option():
    # format_func's contract is option -> label, so a preset is handed whatever
    # the caller passed: a plain str option (its own id), an int, or a dict.
    upper = data.FORMAT_PRESETS["UPPERCASE"]
    assert upper("Apple") == "APPLE"
    assert upper(7) == "7"
    assert upper({"id": "apple"}) == "APPLE"
    assert data.FORMAT_PRESETS["None"] is None
    # the preset used by codegen must be named exactly `fmt_upper`
    assert upper.__name__ == "fmt_upper"


def test_every_format_preset_handles_a_dict_option():
    # A preset is reachable from the UI against whatever the user pasted, so all
    # of them must survive a label-less dict — not just the one codegen emits.
    option = {"id": "new york"}
    assert data.fmt_upper(option) == "NEW YORK"
    assert data.fmt_title(option) == "New York"
    assert data.fmt_bullet(option) == "● new york"
    assert data.fmt_truncate({"id": "12345678901"}) == "123456789…"


def test_format_presets_match_the_real_listview_contract():
    """Drift guard against re-deriving listview's label rule in the demo.

    normalize_options is the rule's one implementation: it hands format_func the
    whole option and skips it entirely for a dict option with an explicit
    `label`. The presets must produce the right thing under exactly that, which a
    direct call cannot show.
    """
    from streamlit_listview._options import normalize_options

    items, _ = normalize_options(
        [{"id": "berlin"}, {"id": "paris", "label": "Paris"}, "rome"],
        data.fmt_upper,
    )
    assert [item["label"] for item in items] == ["BERLIN", "Paris", "ROME"]


def test_fmt_type_badge_builds_the_label_from_custom_fields():
    # The preset that demonstrates the point of the option contract: the label
    # comes from fields the option carries, which the id alone cannot reach.
    badge = data.FORMAT_PRESETS["Type badge (custom field)"]
    assert badge.__name__ == "fmt_type_badge"
    assert badge({"id": 1, "text": "Orders", "type": "Table"}) == "Orders"
    assert badge({"id": 2, "text": "OrdersView", "type": "View"}) == "OrdersView 👓"


def test_fmt_type_badge_never_raises_on_unexpected_shapes():
    # Reachable by clicking, against whatever the user pasted: a scalar option, a
    # missing `text` and a missing `type` must all degrade instead of raising.
    # Any exception here becomes a ValueError that blanks the demo's result panel.
    assert data.fmt_type_badge("rome") == "rome"
    assert data.fmt_type_badge(7) == "7"
    assert data.fmt_type_badge({"id": "orders", "type": "Table"}) == "orders"
    assert data.fmt_type_badge({"id": "orders"}) == "orders 👓"
    # `"text": null` is what pasted JSON gives for an empty cell. Absent means
    # absent — fall back to the id, never render the literal "None".
    assert data.fmt_type_badge({"id": "orders", "text": None}) == "orders 👓"
    assert (
        data.fmt_type_badge({"id": "orders", "text": None, "type": "Table"})
        == "orders"
    )


def test_make_on_change_returns_callable():
    assert callable(data.make_on_change())
    assert data.make_on_change() is not data.make_on_change()


def test_all_format_presets_transform_label():
    assert data.fmt_title("new york") == "New York"
    assert data.fmt_bullet("apple") == "● apple"
    assert data.fmt_upper("apple") == "APPLE"


def test_make_on_change_callback_bumps_counter_and_toasts(monkeypatch):
    # The returned callback imports streamlit and touches session_state/toast;
    # stub both so it runs outside a script-run context.
    import streamlit as st

    state = {}
    toasts = []
    monkeypatch.setattr(st, "session_state", state, raising=False)
    monkeypatch.setattr(st, "toast", lambda *a, **k: toasts.append((a, k)), raising=False)

    cb = data.make_on_change()
    cb()
    cb()
    assert state["demo_change_count"] == 2
    assert len(toasts) == 2


def test_fmt_truncate_boundary():
    trunc = data.fmt_truncate
    assert trunc("1234567890") == "1234567890"   # exactly 10 — kept
    assert trunc("12345678901") == "123456789…"  # 11 — truncated to 10
    assert trunc("short") == "short"             # under limit


def test_parse_empty_returns_empty_list():
    assert parsing.parse_options_text("") == []
    assert parsing.parse_options_text("   \n  ") == []
    assert parsing.parse_options_text(None) == []


def test_parse_json_array_of_dicts():
    out = parsing.parse_options_text('[{"id": "a", "label": "A"}, {"id": "b"}]')
    assert out == [{"id": "a", "label": "A"}, {"id": "b"}]


def test_parse_lines_when_not_json():
    assert parsing.parse_options_text("Apple\nBanana\n\nCherry") == [
        "Apple",
        "Banana",
        "Cherry",
    ]


def test_parse_single_json_object_is_wrapped():
    assert parsing.parse_options_text('{"id": "x"}') == [{"id": "x"}]


def test_option_ids_handles_scalars_and_dicts():
    # Scalars are their own id; dict options use their 'id'.
    assert parsing.option_ids(["a", {"id": "b", "label": "B"}, 3]) == ["a", "b", 3]


def test_option_ids_skips_dict_without_id():
    # A custom dict missing 'id' must NOT crash the demo's Default picker; it is
    # skipped here so the listview() call downstream surfaces the friendly
    # ValueError via st.error instead of a raw KeyError traceback.
    assert parsing.option_ids([{"label": "no id"}, "a"]) == ["a"]


def test_option_ids_empty():
    assert parsing.option_ids([]) == []


def test_has_selection_true_for_falsy_single_values():
    # Single mode returns the option itself; a falsy id (0, "") is a real
    # selection and must not collapse to "Nothing selected yet."
    assert parsing.has_selection(0) is True
    assert parsing.has_selection("") is True
    assert parsing.has_selection("a") is True
    assert parsing.has_selection({"id": "a"}) is True


def test_has_selection_false_for_none_and_empty_list():
    assert parsing.has_selection(None) is False
    assert parsing.has_selection([]) is False


def test_has_selection_true_for_nonempty_list():
    assert parsing.has_selection(["a"]) is True


def test_coerce_single_default_scalar():
    assert parsing.coerce_single_default("a", ["a", "b"]) == "a"
    assert parsing.coerce_single_default("gone", ["a", "b"]) is None
    assert parsing.coerce_single_default(None, ["a", "b"]) is None


def test_coerce_single_default_list_carries_first_entry():
    # A list default (carried over from multi mode) contributes its first entry.
    assert parsing.coerce_single_default(["b", "a"], ["a", "b"]) == "b"
    assert parsing.coerce_single_default(["gone"], ["a", "b"]) is None
    assert parsing.coerce_single_default([], ["a", "b"]) is None


def test_coerce_single_default_falsy_id_survives():
    # Membership, not truthiness: id 0 / "" are valid defaults.
    assert parsing.coerce_single_default(0, [0, 1]) == 0
    assert parsing.coerce_single_default("", ["", "a"]) == ""


def test_coerce_multi_default_filters_to_valid_ids():
    assert parsing.coerce_multi_default(["a", "gone", "b"], ["a", "b"]) == ["a", "b"]
    assert parsing.coerce_multi_default(None, ["a"]) == []


def test_coerce_multi_default_scalar_becomes_one_item_list():
    # A scalar default (carried over from single mode) must not be iterated
    # character by character.
    assert parsing.coerce_multi_default("ab", ["ab", "c"]) == ["ab"]
    assert parsing.coerce_multi_default("gone", ["a"]) == []


def test_coerce_multi_default_falsy_ids_survive():
    assert parsing.coerce_multi_default([0, ""], [0, "", "a"]) == [0, ""]


def test_coerce_multi_default_survives_unhashable_ids():
    # Custom pasted options can carry an unhashable id (a nested JSON array), so
    # the fast set-membership path must fall back instead of raising TypeError
    # before listview() gets to report the malformed option.
    assert parsing.coerce_multi_default(["a"], ["a", [1, 2]]) == ["a"]
    assert parsing.coerce_multi_default([[1, 2]], ["a", [1, 2]]) == [[1, 2]]


def test_coerce_multi_default_survives_unhashable_default_entry():
    # The reverse case: hashable ids, but a default carried over from a previous
    # (unhashable) dataset. It is simply not a member of the new id set.
    assert parsing.coerce_multi_default([[1, 2], "a"], ["a"]) == ["a"]


_BASE_CFG = {
    "data_source": "Built-in cities",
    "label": "Cities",
    "selection_mode": "single",
    "default": None,
    "placeholder": "",
    "help": "",
    "label_visibility": "visible",
    "width": "stretch",
    "height": 300,
    "item_height": None,
    "content_font_size": None,
    "show_grid_lines": True,
    "disabled": False,
    "accept_new_options": False,
    "max_selections": None,
    "select_all": False,
    "enable_search": False,
    "pin_search": False,
    "search_placeholder": "Search",
    "collapsible_groups": False,
    "collapsed_groups": None,
    "sort": None,
    "sort_ascending": True,
    "format_preset": "None",
    "on_change": False,
}
_OPTS = [{"id": "berlin", "label": "Berlin", "group": "Germany"}]


def _cfg(**overrides):
    return {**_BASE_CFG, **overrides}


def test_snippet_is_valid_python():
    code = codegen.build_snippet(_cfg(), _OPTS, builtin_dataset=True)
    compile(code, "<snippet>", "exec")  # raises SyntaxError if malformed


def test_snippet_minimal_has_label_options_key_only():
    code = codegen.build_snippet(_cfg(), _OPTS, builtin_dataset=True)
    assert '"Cities",' in code
    assert "    options,\n" in code
    assert 'key="demo_listview",' in code
    assert "selection_mode" not in code  # default omitted


def test_snippet_includes_non_defaults():
    code = codegen.build_snippet(
        _cfg(
            selection_mode="multi",
            enable_search=True,
            pin_search=True,
            max_selections=3,
            width=500,
        ),
        _OPTS,
        builtin_dataset=False,
    )
    assert 'selection_mode="multi",' in code
    assert "enable_search=True," in code
    assert "pin_search=True," in code
    assert "max_selections=3," in code
    assert "width=500," in code


def test_snippet_skips_inapplicable_params():
    code = codegen.build_snippet(
        _cfg(pin_search=True, search_placeholder="Find"), _OPTS, builtin_dataset=False
    )
    assert "pin_search" not in code
    assert "search_placeholder" not in code
    code2 = codegen.build_snippet(_cfg(max_selections=5), _OPTS, builtin_dataset=False)
    assert "max_selections" not in code2


def test_dependent_params_drive_skip_and_reset_in_agreement():
    """One table encodes each param's enabling rule; both consumers derive from it.

    codegen's skip predicates must be the exact negation of the enabling
    predicates (the two used to be spelled twice in opposite polarity), and each
    reset value must be the param's own listview default — resetting the cfg
    entry (render_demo) and skipping the kwarg (build_snippet) then describe the
    same call.
    """
    off = _cfg(selection_mode="single", enable_search=False)
    on = _cfg(selection_mode="multi", enable_search=True)
    for name, (enabled, reset) in codegen.DEPENDENT_PARAMS.items():
        assert not enabled(off) and enabled(on)
        assert codegen._SKIP_WHEN[name](off) is True
        assert codegen._SKIP_WHEN[name](on) is False
        assert reset == codegen._DEFAULTS[name]


def test_snippet_format_preset_emits_def_and_kwarg():
    code = codegen.build_snippet(_cfg(format_preset="UPPERCASE"), _OPTS, builtin_dataset=False)
    assert "def fmt_upper(option):" in code
    assert "format_func=fmt_upper," in code


def test_snippet_format_preset_def_is_self_contained():
    """The emitted definitions must not call a helper the snippet never defines.

    codegen used to prepend demo/data.py's private `_base_label` alongside the
    preset; presets are self-contained now, so the one def is the whole thing —
    and must stay that way even though every preset repeats the same dict unwrap.
    Executing every def in an empty namespace proves the snippet a user copies out
    actually runs.
    """
    code = codegen.build_snippet(_cfg(format_preset="UPPERCASE"), _OPTS, builtin_dataset=False)
    tree = ast.parse(code)
    namespace = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            exec(ast.get_source_segment(code, node), namespace)
    assert namespace["fmt_upper"]("berlin") == "BERLIN"


@pytest.mark.parametrize(
    "preset_name", [n for n in data.FORMAT_PRESETS if n != "None"]
)
def test_every_emitted_preset_runs_standalone(preset_name):
    """Self-containment holds for EVERY preset, not just the one spot-checked above.

    codegen emits `inspect.getsource(func)` and nothing else, so a preset that
    reached for a shared helper would NameError here — and in the snippet the user
    pastes into their own app. That is the whole reason each preset repeats the
    dict unwrap instead of factoring it out.
    """
    code = codegen.build_snippet(
        _cfg(format_preset=preset_name), _OPTS, builtin_dataset=False
    )
    func = data.FORMAT_PRESETS[preset_name]
    namespace = {}
    for node in ast.parse(code).body:
        if isinstance(node, ast.FunctionDef):
            exec(ast.get_source_segment(code, node), namespace)
    emitted = namespace[func.__name__]
    # Both option shapes listview can hand a formatter, run from the snippet's
    # own namespace — no import from demo.data involved.
    assert emitted("berlin") == func("berlin")
    assert emitted({"id": "berlin"}) == func({"id": "berlin"})


def test_snippet_on_change_emits_callback():
    code = codegen.build_snippet(_cfg(on_change=True), _OPTS, builtin_dataset=False)
    assert "def on_change():" in code
    assert "on_change=on_change," in code


def test_snippet_builtin_dataset_has_continuation_comment():
    assert "# …" in codegen.build_snippet(_cfg(), _OPTS, builtin_dataset=True)


def test_snippet_builtin_default_beyond_first_three_is_emitted():
    # The built-in dataset is abbreviated to the first few options, but any
    # option the configured default references MUST still be emitted — otherwise
    # the snippet shown to the user raises
    # ValueError("default id 'tokyo' is not present in options") when run.
    code = codegen.build_snippet(_cfg(default="tokyo"), data.CITIES, builtin_dataset=True)
    options_block = code.split("selected = listview")[0]
    assert '"tokyo"' in options_block
    assert "# …" in code  # still abbreviated
    compile(code, "<snippet>", "exec")


def test_snippet_builtin_multi_defaults_beyond_first_three_are_emitted():
    code = codegen.build_snippet(
        _cfg(selection_mode="multi", default=["tokyo", "paris"]),
        data.CITIES,
        builtin_dataset=True,
    )
    options_block = code.split("selected = listview")[0]
    assert '"tokyo"' in options_block
    assert '"paris"' in options_block
    compile(code, "<snippet>", "exec")


def test_snippet_builtin_first_three_default_does_not_duplicate():
    # A default among the first three must not be emitted twice.
    code = codegen.build_snippet(_cfg(default="berlin"), data.CITIES, builtin_dataset=True)
    options_block = code.split("selected = listview")[0]
    assert options_block.count('"berlin"') == 1


def test_snippet_custom_data_renders_all_options_not_truncated():
    # Custom (non-builtin) options must appear in full so the snippet reproduces
    # the live demo — including ids beyond the first three that default= /
    # max_selections may reference. Only the long built-in dataset is abbreviated.
    opts = [{"id": f"o{i}", "label": f"O{i}"} for i in range(5)]
    code = codegen.build_snippet(
        _cfg(selection_mode="multi", default=["o4"]),
        opts,
        builtin_dataset=False,
    )
    options_block = code.split("selected = listview")[0]
    for i in range(5):
        assert f'"o{i}"' in options_block, f"option o{i} missing from generated options block"
    assert "# …" not in code  # no built-in elision marker for custom data
    compile(code, "<snippet>", "exec")


def test_snippet_omits_empty_strings_and_empty_lists():
    code = codegen.build_snippet(
        _cfg(selection_mode="multi", default=[], placeholder="", help=""),
        _OPTS,
        builtin_dataset=False,
    )
    assert "default=" not in code
    assert "placeholder=" not in code
    assert "help=" not in code


def test_snippet_renders_unicode_and_literal_tokens():
    opts = [{"id": "sp", "label": "São Paulo: true", "group": "g: null"}]
    code = codegen.build_snippet(
        _cfg(enable_search=True, search_placeholder="Find…"), opts, builtin_dataset=False
    )
    assert '"São Paulo: true"' in code  # string content not corrupted, not escaped
    assert '"g: null"' in code
    assert '"Find…",' in code           # non-ASCII kwarg rendered literally
    compile(code, "<snippet>", "exec")


def test_pyval_renders_none_bool_and_lists():
    assert codegen._pyval(None) == "None"
    assert codegen._pyval(True) == "True"
    assert codegen._pyval(["a", 1, True]) == '["a", 1, True]'


def test_pyval_renders_floats_including_non_finite():
    # json.loads accepts NaN/Infinity by default (json.dumps of a DataFrame
    # NULL cell emits NaN), so pasted options can carry non-finite floats;
    # str() rendered them as bare identifiers (nan, inf) that NameError when
    # the snippet runs.
    assert codegen._pyval(1.5) == "1.5"
    assert codegen._pyval(float("nan")) == "float('nan')"
    assert codegen._pyval(float("inf")) == "float('inf')"
    assert codegen._pyval(float("-inf")) == "float('-inf')"


def test_snippet_with_nan_option_value_is_runnable():
    # A pasted option carrying a NaN (a NULL DataFrame cell round-tripped
    # through JSON) must yield a snippet whose options block still executes.
    opts = [{"id": "a", "label": "A", "score": float("nan")}]
    code = codegen.build_snippet(_cfg(), opts, builtin_dataset=False)
    assert "float('nan')" in code
    # Execute only the import + `options = ...` prefix (not the listview call,
    # which has no Streamlit runtime here); bare `nan` would NameError here.
    prefix = code.split("\nselected = listview")[0]
    ns = {}
    exec(compile(prefix, "<snippet-prefix>", "exec"), ns)
    assert math.isnan(ns["options"][0]["score"])


def test_pylit_renders_empty_dict_and_list():
    assert codegen._pylit({}) == "{}"
    assert codegen._pylit([]) == "[]"


def test_snippet_renders_list_valued_collapsed_groups():
    code = codegen.build_snippet(
        _cfg(collapsible_groups=True, collapsed_groups=["Germany", "France"]),
        _OPTS,
        builtin_dataset=False,
    )
    assert 'collapsed_groups=["Germany", "France"],' in code
    compile(code, "<snippet>", "exec")


def test_snippet_skips_collapsed_groups_without_collapsible():
    # collapsed_groups is inert unless collapsible_groups is on, so the snippet
    # must omit it in that case (mirrors the pin_search / max_selections gates).
    off = codegen.build_snippet(
        _cfg(collapsed_groups="all", collapsible_groups=False),
        _OPTS,
        builtin_dataset=False,
    )
    assert "collapsed_groups" not in off
    on = codegen.build_snippet(
        _cfg(collapsed_groups="all", collapsible_groups=True),
        _OPTS,
        builtin_dataset=False,
    )
    assert 'collapsed_groups="all",' in on
    assert "collapsible_groups=True," in on
    compile(on, "<snippet>", "exec")


def test_snippet_emits_show_grid_lines_only_when_false():
    # Default True is omitted; False is emitted (the compact, line-free look).
    on = codegen.build_snippet(_cfg(), _OPTS, builtin_dataset=False)
    assert "show_grid_lines" not in on
    off = codegen.build_snippet(
        _cfg(show_grid_lines=False), _OPTS, builtin_dataset=False
    )
    assert "show_grid_lines=False," in off
    compile(off, "<snippet>", "exec")


def test_snippet_emits_content_font_size_only_when_set():
    # Default None is omitted; an int is emitted.
    off = codegen.build_snippet(_cfg(), _OPTS, builtin_dataset=False)
    assert "content_font_size" not in off
    on = codegen.build_snippet(
        _cfg(content_font_size=12), _OPTS, builtin_dataset=False
    )
    assert "content_font_size=12," in on
    compile(on, "<snippet>", "exec")


def test_snippet_sidebar_wraps_call_in_with_block():
    code = codegen.build_snippet(_cfg(sidebar=True), _OPTS, builtin_dataset=False)
    assert "with st.sidebar:\n" in code
    assert "\n    selected = listview(\n" in code      # call indented one level
    assert '        key="demo_listview",\n' in code     # kwargs land at 8 spaces
    assert "\n    )\n" in code                           # closing paren indented one level
    assert "\nst.write(selected)\n" in code             # result stays top-level
    assert "sidebar=" not in code                        # never emitted as a kwarg
    compile(code, "<snippet>", "exec")


def test_snippet_no_sidebar_keeps_call_top_level():
    code = codegen.build_snippet(_cfg(), _OPTS, builtin_dataset=False)
    assert "with st.sidebar:" not in code
    assert "\nselected = listview(\n" in code            # top-level, unindented
    compile(code, "<snippet>", "exec")


def test_snippet_with_empty_options_renders_empty_list():
    code = codegen.build_snippet(_cfg(), [], builtin_dataset=False)
    assert "options = []" in code
    compile(code, "<snippet>", "exec")


def test_examples_compile():
    for name in ("single.py", "grouped.py", "events.py", "behavior.py"):
        src = (ROOT / "demo" / "examples" / name).read_text(encoding="utf-8")
        compile(src, name, "exec")


def test_app_compiles():
    src = (ROOT / "demo" / "app.py").read_text(encoding="utf-8")
    compile(src, "app.py", "exec")


def test_app_wires_large_data_source():
    src = (ROOT / "demo" / "app.py").read_text(encoding="utf-8")
    assert '"large_size"' in src            # config key
    assert "select_slider(" in src          # size control
    ds = (ROOT / "demo" / "dataset.py").read_text(encoding="utf-8")
    assert '"Large"' in ds                  # registry key (data-source segment)
    assert "make_large_dataset(" in ds      # options resolution


def test_snippet_includes_select_all_in_multi():
    code = codegen.build_snippet(
        _cfg(selection_mode="multi", select_all=True),
        _OPTS,
        builtin_dataset=False,
    )
    assert "select_all=True," in code
    compile(code, "<snippet>", "exec")


def test_snippet_skips_select_all_outside_multi():
    code = codegen.build_snippet(
        _cfg(selection_mode="single", select_all=True),
        _OPTS,
        builtin_dataset=False,
    )
    assert "select_all" not in code


def test_snippet_omits_select_all_when_false_in_multi():
    code = codegen.build_snippet(
        _cfg(selection_mode="multi", select_all=False),
        _OPTS,
        builtin_dataset=False,
    )
    assert "select_all" not in code


def test_snippet_includes_sort_when_set():
    snippet = codegen.build_snippet(_cfg(sort="both"), _OPTS, builtin_dataset=False)
    assert 'sort="both",' in snippet
    compile(snippet, "<snippet>", "exec")


def test_snippet_includes_sort_ascending_only_with_sort():
    with_sort = codegen.build_snippet(
        _cfg(sort="items", sort_ascending=False), _OPTS, builtin_dataset=False
    )
    assert "sort_ascending=False," in with_sort
    without_sort = codegen.build_snippet(
        _cfg(sort=None, sort_ascending=False), _OPTS, builtin_dataset=False
    )
    assert "sort_ascending" not in without_sort


def test_snippet_omits_sort_defaults():
    snippet = codegen.build_snippet(_cfg(), _OPTS, builtin_dataset=False)
    assert "sort=" not in snippet
    assert "sort_ascending" not in snippet


def test_make_large_dataset_size_and_shape():
    items = data.make_large_dataset(250)
    assert len(items) == 250
    assert all({"id", "label", "group"} <= set(it) for it in items)
    ids = [it["id"] for it in items]
    assert len(ids) == len(set(ids)), "ids must be unique"
    assert items[0] == {"id": "item-00000", "label": "Item 00000", "group": "Batch 000"}
    assert items[249]["id"] == "item-00249"


def test_make_large_dataset_groups_in_batches_of_100():
    items = data.make_large_dataset(250)
    assert items[0]["group"] == "Batch 000"
    assert items[99]["group"] == "Batch 000"
    assert items[100]["group"] == "Batch 001"
    assert items[200]["group"] == "Batch 002"


def test_make_large_dataset_is_deterministic():
    assert data.make_large_dataset(100) == data.make_large_dataset(100)


def test_make_large_dataset_empty():
    assert data.make_large_dataset(0) == []


def test_make_large_dataset_accepted_by_normalizer():
    from streamlit_listview._options import normalize_options

    items, _ = normalize_options(data.make_large_dataset(500), str)
    assert len(items) == 500


def test_snippet_large_source_emits_comprehension():
    code = codegen.build_snippet(
        _cfg(data_source="Large", large_size=250),
        data.make_large_dataset(250),
        builtin_dataset=False,
    )
    assert "for i in range(250)" in code
    assert 'f"item-{i:05d}"' in code
    assert '"item-00000"' not in code  # no inlined literal ids
    compile(code, "<snippet>", "exec")


def test_snippet_large_source_reproduces_dataset():
    n = 250
    code = codegen.build_snippet(
        _cfg(data_source="Large", large_size=n),
        data.make_large_dataset(n),
        builtin_dataset=False,
    )
    # Execute only the import + `options = ...` prefix (not the listview call,
    # which has no Streamlit runtime here) and compare to the generator.
    prefix = code.split("\nselected = listview")[0]
    ns = {}
    exec(compile(prefix, "<snippet-prefix>", "exec"), ns)
    assert ns["options"] == data.make_large_dataset(n)


def test_snippet_large_source_reflects_size():
    code = codegen.build_snippet(
        _cfg(data_source="Large", large_size=5000),
        data.make_large_dataset(5000),
        builtin_dataset=False,
    )
    assert "for i in range(5000)" in code


def _data_cfg(**overrides):
    base = {"data_source": "Built-in cities", "options_text": "", "large_size": 1000}
    return {**base, **overrides}


def test_resolve_builtin_returns_cities_with_groups():
    options, ids, groups, builtin = dataset.resolve_dataset(_data_cfg())
    assert options == data.CITIES
    assert builtin is True
    assert groups == data.GROUPS
    assert ids == [c["id"] for c in data.CITIES]


def test_resolve_empty_source():
    options, ids, groups, builtin = dataset.resolve_dataset(_data_cfg(data_source="Empty"))
    assert options == []
    assert ids == []
    assert groups == []
    assert builtin is False


def test_resolve_large_source():
    options, ids, groups, builtin = dataset.resolve_dataset(
        _data_cfg(data_source="Large", large_size=250)
    )
    assert len(options) == 250
    assert builtin is False
    assert ids[0] == "item-00000"
    assert groups[0] == "Batch 000"


def test_resolve_custom_source_ids_and_groups():
    # Mixed scalar + dict-with-group + dict-without-group exercises every branch
    # of the ids/groups derivation.
    cfg = _data_cfg(
        data_source="Custom",
        options_text='[{"id": "a"}, "b", {"id": "c", "group": "G"}]',
    )
    options, ids, groups, builtin = dataset.resolve_dataset(cfg)
    assert options == [{"id": "a"}, "b", {"id": "c", "group": "G"}]
    assert ids == ["a", "b", "c"]
    assert groups == ["G"]
    assert builtin is False


def test_data_sources_registry_keys_and_traits():
    # The registry is the one dispatch: its key order IS the segmented control's
    # choice order, and the traits carry what consumers used to decide by
    # comparing names.
    assert list(dataset.DATA_SOURCES) == ["Built-in cities", "Custom", "Empty", "Large"]
    builtin = {name for name, s in dataset.DATA_SOURCES.items() if s.builtin}
    assert builtin == {"Built-in cities"}
    explicit = {name for name, s in dataset.DATA_SOURCES.items() if s.labels_explicit}
    assert explicit == {"Built-in cities", "Large"}
    large = dataset.DATA_SOURCES["Large"]
    assert large.sized and large.timed and large.snippet_comprehension
    assert dataset.DATA_SOURCES["Custom"].options_editor
    assert dataset.DATA_SOURCES["Empty"].empty_caption


def test_resolve_unknown_source_raises_key_error():
    # No silent fallback to the built-in cities: an unknown name (unreachable via
    # the UI, whose choices come from the same registry) must fail loudly.
    with pytest.raises(KeyError):
        dataset.resolve_dataset(_data_cfg(data_source="Bogus"))


def test_app_uses_pills_section_switcher():
    src = (ROOT / "demo" / "app.py").read_text(encoding="utf-8")
    assert "st.pills(" in src
    # all nine section names appear as pill labels
    for name in ("Basic", "Data", "Appearance", "Layout", "Behavior",
                 "Search", "Groups", "Sorting", "Formatting"):
        assert f'"{name}"' in src, f"missing section {name!r}"


def test_app_no_longer_stacks_config_expanders():
    src = (ROOT / "demo" / "app.py").read_text(encoding="utf-8")
    # The config sections moved into pills; only non-config expanders (the API
    # tab's example snippets) may remain. The config section icons must be gone
    # as expander headers.
    assert 'st.expander(":material/tune: Basic"' not in src
    assert 'st.expander(":material/search: Search"' not in src


# --- API-reference drift guard -------------------------------------------------
# The demo's API reference (demo/app.py) hand-copies listview()'s signature into
# two module-level constants — SIGNATURE (a def-string) and PARAMS (a table of
# {Parameter, Type, Default, Description} dicts) — which can silently fall out of
# sync with the real function. select_all, for instance, was added to listview()
# but initially left out of the reference, and nothing caught it. The helpers
# below ast-parse all three sources rather than importing them — demo/app.py has
# a Streamlit script's side effects, and reading the reference as *text* is the
# only way to compare hand-written prose against the real function anyway.
# (codegen imports listview to derive its defaults; that works here only because
# conftest patches st.components.v2.component at import time — a bare
# `import streamlit_listview` raises without a built frontend.)


def _kwonly_func(source, func_name):
    """The `func_name` FunctionDef node, parsed from `source`."""
    return next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == func_name
    )


def _kwonly_param_names(source, func_name):
    """Keyword-only parameter names of `func_name`, parsed from `source`."""
    return {arg.arg for arg in _kwonly_func(source, func_name).args.kwonlyargs}


def _kwonly_defaults(source, func_name):
    """Keyword-only parameter name -> its default rendered back as source text."""
    func = _kwonly_func(source, func_name)
    return {
        arg.arg: ast.unparse(default)
        for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults)
        if default is not None
    }


def _module_constant(source, name):
    """The AST value node assigned to module-level `name` in `source`."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise AssertionError(f"module-level {name!r} assignment not found")


def _documented_param_names(app_source):
    """Names in PARAMS' `Parameter` column, splitting the combined
    'args / kwargs' row into its two individual names."""
    params = _module_constant(app_source, "PARAMS")
    names = set()
    for entry in params.elts:  # each entry is a dict literal
        for key, value in zip(entry.keys, entry.values):
            if isinstance(key, ast.Constant) and key.value == "Parameter":
                names.update(part.strip() for part in ast.literal_eval(value).split("/"))
    return names


def _documented_defaults(app_source):
    """PARAMS' `Default` column, keyed by the row's `Parameter` name."""
    params = _module_constant(app_source, "PARAMS")
    rows = {}
    for entry in params.elts:  # each entry is a dict literal
        row = {
            key.value: ast.literal_eval(value)
            for key, value in zip(entry.keys, entry.values)
        }
        rows[row["Parameter"]] = row["Default"]
    return rows


def _signature_param_names(app_source):
    """Keyword-only parameter names declared in the SIGNATURE def-string."""
    sig = ast.literal_eval(_module_constant(app_source, "SIGNATURE"))
    # SIGNATURE is a bare `def listview(...) -> ...` with no body; add a body so
    # it parses, then read its keyword-only args exactly like the real function.
    return _kwonly_param_names(sig + ": ...", "listview")


def test_api_reference_documents_every_keyword_param():
    listview_source = (ROOT / "streamlit_listview" / "__init__.py").read_text(
        encoding="utf-8"
    )
    app_source = (ROOT / "demo" / "app.py").read_text(encoding="utf-8")

    real = _kwonly_param_names(listview_source, "listview")
    assert "select_all" in real, "sanity: failed to parse listview()'s keyword params"

    undocumented = real - _documented_param_names(app_source)
    assert not undocumented, f"missing from demo PARAMS table: {sorted(undocumented)}"

    missing_from_signature = real - _signature_param_names(app_source)
    assert not missing_from_signature, (
        f"missing from demo SIGNATURE string: {sorted(missing_from_signature)}"
    )


def test_app_section_table_dispatches_every_pill():
    """SECTIONS carries the renderer, so no pill can render an empty panel.

    The switcher used to dispatch through an if/elif chain that repeated the
    SECTIONS key list, so a section added to one but not the other rendered a pill
    and a header above nothing, silently and without an error. The table is now
    the dispatch, which only holds if every renderer named in it exists and takes
    the shared (cfg, ids, groups) triple render_demo calls it with. "Data" is the
    documented exception: its controls decide *what* gets resolved, so it renders
    before resolution and carries no post-resolve renderer.
    """
    app_source = (ROOT / "demo" / "app.py").read_text(encoding="utf-8")
    arity = {
        node.name: len(node.args.args)
        for node in ast.parse(app_source).body
        if isinstance(node, ast.FunctionDef)
    }

    table = _module_constant(app_source, "SECTIONS")
    renderers = {}
    for key, value in zip(table.keys, table.values):
        icon, renderer = value.elts
        assert isinstance(icon, ast.Constant), "the icon must stay a plain string"
        # `None` for Data, otherwise a bare function name.
        renderers[key.value] = getattr(renderer, "id", None)

    assert renderers["Data"] is None, "Data must render before dataset resolution"
    assert "render_data(cfg)" in app_source, "...and still be called there"
    for name, renderer in renderers.items():
        if renderer is None:
            continue
        assert renderer in arity, f"section {name!r} names a missing renderer"
        assert arity[renderer] == 3, (
            f"{renderer} takes {arity[renderer]} args; the section renderers share "
            "one (cfg, ids, groups) signature so SECTIONS can dispatch them"
        )


def test_codegen_defaults_come_from_the_real_signature():
    """codegen._DEFAULTS must equal listview()'s own defaults.

    build_snippet emits a kwarg only when the configured value differs from its
    default, so a default that drifted from the real one silently makes the demo's
    headline feature — a copy-pasteable snippet reproducing what you see — emit
    code that renders a *different* widget. The name-only guard above cannot catch
    that. _DEFAULTS is derived via inspect.signature; comparing it against the
    function's *source* keeps this test independent of that mechanism.
    """
    listview_source = (ROOT / "streamlit_listview" / "__init__.py").read_text(
        encoding="utf-8"
    )
    real = _kwonly_defaults(listview_source, "listview")
    assert "select_all" in real, "sanity: failed to parse listview()'s defaults"

    assert {name: repr(value) for name, value in codegen._DEFAULTS.items()} == {
        name: default
        for name, default in real.items()
        if name not in codegen._NOT_VALUE_KWARGS
    }


def test_api_reference_documents_the_real_defaults():
    """SIGNATURE and PARAMS must show listview()'s real defaults, not stale ones.

    Both are prose the demo presents as *the* API contract, so a default that
    drifts there teaches users the wrong thing. They stay hand-written (the
    signature block and the Description column carry wording no derivation can
    produce), so this is the guard: codegen._DEFAULTS comes off the function
    itself, and codegen._pyval renders a value exactly the way PARAMS spells it.
    """
    app_source = (ROOT / "demo" / "app.py").read_text(encoding="utf-8")
    listview_source = (ROOT / "streamlit_listview" / "__init__.py").read_text(
        encoding="utf-8"
    )

    documented = _documented_defaults(app_source)
    for name, value in codegen._DEFAULTS.items():
        assert documented[name] == codegen._pyval(value), (
            f"PARAMS row {name!r} documents default {documented[name]}, "
            f"but listview() defaults to {codegen._pyval(value)}"
        )

    # SIGNATURE is a bare def with no body; add one so it parses (see
    # _signature_param_names), then compare its defaults token for token.
    sig = ast.literal_eval(_module_constant(app_source, "SIGNATURE")) + ": ..."
    assert _kwonly_defaults(sig, "listview") == _kwonly_defaults(
        listview_source, "listview"
    )
