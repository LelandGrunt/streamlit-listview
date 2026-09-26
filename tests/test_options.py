import datetime
import types

import pytest

from streamlit_listview._options import (
    MAX_SAFE_JS_INT,
    map_selection,
    normalize_options,
    sort_items,
)


def test_normalize_simple_string_values():
    items, id_to_original = normalize_options(["Apple", "Banana"], None)
    assert items == [
        {"id": "Apple", "label": "Apple"},
        {"id": "Banana", "label": "Banana"},
    ]
    assert id_to_original == {"Apple": "Apple", "Banana": "Banana"}


def test_normalize_simple_int_values_label_is_string():
    items, id_to_original = normalize_options([1, 2, 3], None)
    assert items == [
        {"id": 1, "label": "1"},
        {"id": 2, "label": "2"},
        {"id": 3, "label": "3"},
    ]
    # id stays the original int; original preserved for mapping
    assert id_to_original == {1: 1, 2: 2, 3: 3}


def test_normalize_none_options_returns_empty():
    items, id_to_original = normalize_options(None, None)
    assert items == []
    assert id_to_original == {}


def test_normalize_applies_format_func_to_simple_values():
    items, id_to_original = normalize_options(
        [1, 2], lambda v: f"#{v}"
    )
    assert items == [
        {"id": 1, "label": "#1"},
        {"id": 2, "label": "#2"},
    ]
    # id and original are the raw value, not the formatted label
    assert id_to_original == {1: 1, 2: 2}


def test_normalize_format_func_result_is_stringified():
    # format_func may return a non-str; label must be str()
    items, _ = normalize_options([1], lambda v: v * 10)
    assert items == [{"id": 1, "label": "10"}]


def test_normalize_format_func_exception_reraised_with_option():
    def boom(v):
        raise RuntimeError("kaboom")

    with pytest.raises(ValueError) as excinfo:
        normalize_options(["Apple"], boom)
    msg = str(excinfo.value)
    assert "format_func" in msg
    assert "Apple" in msg
    assert "kaboom" in msg


def test_normalize_dict_option_format_func_exception_reraised():
    # A dict option without a usable label routes through format_func too; the
    # failure must be wrapped as a ValueError naming the offending option (the
    # whole dict, not just the id it was called with).
    def boom(o):
        raise RuntimeError("kaboom")

    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"id": "x"}], boom)
    msg = str(excinfo.value)
    assert "format_func" in msg
    assert "kaboom" in msg
    assert "'x'" in msg or "x" in msg


def test_normalize_no_format_func_str_failure_wrapped_with_option():
    # With no formatter the label is str(id), and that call stays under the same
    # guard: every other bad-option path in _options raises a ValueError naming
    # the option, so an id whose __str__ raises must not be the one that escapes
    # raw. The message says str(id), not format_func — there isn't one.
    class Boom(str):
        def __str__(self):
            raise RuntimeError("kaboom")

        def __repr__(self):
            return "<Boom>"

    with pytest.raises(ValueError) as excinfo:
        normalize_options([Boom()], None)
    msg = str(excinfo.value)
    assert "str(id)" in msg
    assert "<Boom>" in msg
    assert "kaboom" in msg


def test_normalize_explicit_label_str_failure_wrapped_with_option():
    # The explicit-label arm is guarded like the other two. All three things that
    # can produce a label — a label, a format_func result, the id — can raise in
    # __str__, and this module's contract is a ValueError naming the option, so
    # none of them may escape raw.
    class Bad:
        def __str__(self):
            raise RuntimeError("kaboom")

        def __repr__(self):
            return "<Bad>"

    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"id": 1, "label": Bad()}], None)
    msg = str(excinfo.value)
    assert "str(label)" in msg
    assert "<Bad>" in msg
    assert "kaboom" in msg


def test_normalize_dict_option_with_explicit_label():
    opt = {"id": 1, "label": "Apple"}
    items, id_to_original = normalize_options([opt], None)
    assert items == [{"id": 1, "label": "Apple"}]
    # original dict preserved exactly (same object) for return mapping
    assert id_to_original[1] is opt


def test_normalize_dict_option_label_defaults_to_str_id():
    # format_func=None is "no formatter": a label-less dict falls back to
    # str(id) — never str(dict).
    items, _ = normalize_options([{"id": 42}], None)
    assert items == [{"id": 42, "label": "42"}]


def test_normalize_no_format_func_labels_scalars_by_str():
    # The same fallback for scalar options, where the id IS the option.
    items, _ = normalize_options(["Apple", 7], None)
    assert [it["label"] for it in items] == ["Apple", "7"]


def test_normalize_dict_explicit_label_wins_over_format_func():
    # Documented contract: an explicit 'label' is the display text, full stop.
    # format_func only fills in the label when the dict has none.
    opt = {"id": 1, "label": "Hand-written"}
    items, _ = normalize_options([opt], lambda i: f"#{i}")
    assert items == [{"id": 1, "label": "Hand-written"}]


def test_normalize_dict_without_label_format_func_receives_option():
    # The contract: format_func gets the option AS PASSED, so a label-less dict
    # arrives whole and the formatter can read any field it carries.
    seen = []

    def fmt(option):
        seen.append(option)
        return "x"

    normalize_options([{"id": "apple", "kind": "fruit"}], fmt)
    assert seen == [{"id": "apple", "kind": "fruit"}]


def test_normalize_format_func_builds_label_from_a_custom_field():
    # The reason the contract changed: build the label out of the option's own
    # extra fields, which the id alone cannot reach.
    items, _ = normalize_options(
        [
            {"id": 1, "text": "Orders", "type": "Table"},
            {"id": 2, "text": "OrdersView", "type": "View"},
        ],
        lambda o: f"{o['text']}{'' if o['type'] == 'Table' else ' 👓'}",
    )
    assert [it["label"] for it in items] == ["Orders", "OrdersView 👓"]


def test_normalize_scalar_only_format_func_wrapped_for_dict_option():
    # str.upper is an unbound descriptor: it only accepts a str. Now that a
    # label-less dict reaches format_func whole, such a formatter raises — and
    # the failure must surface as the friendly ValueError naming the option,
    # not a bare TypeError out of the middle of normalize_options.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"id": "apple"}], str.upper)
    msg = str(excinfo.value)
    assert "format_func" in msg
    assert "apple" in msg


def test_normalize_scalar_only_format_func_still_works_for_scalars():
    # The other half: a formatter written for plain values is untouched, because
    # a scalar option IS its own id. An explicitly labelled dict never reaches it.
    items, _ = normalize_options(
        [{"id": "banana", "label": "Banana!"}, "cherry"],
        str.upper,
    )
    assert [it["label"] for it in items] == ["Banana!", "CHERRY"]


def test_normalize_dict_label_none_treated_as_absent():
    # df.to_dict("records") yields label=None for a NULL cell in a string-dtype
    # column. Presence alone is not usability: rendering the literal "None" is
    # never what the caller meant, so fall back to str(id).
    items, _ = normalize_options([{"id": "apple", "label": None}], None)
    assert items == [{"id": "apple", "label": "apple"}]


def test_normalize_dict_label_nan_treated_as_absent():
    # The object-dtype counterpart of the None case: pandas yields nan, which
    # would render as the literal "nan". Detected by self-inequality (no pandas
    # import in this package).
    items, _ = normalize_options([{"id": 7, "label": float("nan")}], None)
    assert items == [{"id": 7, "label": "7"}]


def test_normalize_dict_label_none_routes_through_format_func():
    # "Absent" means absent: the fallback is format_func, not bare str(id) — and
    # the formatter receives the whole option, `label: None` included. This is
    # the df.to_dict("records") NULL-cell shape, so a formatter that assumes it
    # only ever sees label-LESS dicts is wrong about the most common case.
    seen = []

    def fmt(option):
        seen.append(option)
        return f"#{option['id']}"

    items, _ = normalize_options([{"id": "apple", "label": None}], fmt)
    assert items == [{"id": "apple", "label": "#apple"}]
    assert seen == [{"id": "apple", "label": None}]


def test_normalize_dict_finite_float_label_is_kept():
    # Only NaN is treated as missing; an ordinary float label is usable text.
    items, _ = normalize_options([{"id": "x", "label": 1.5}], None)
    assert items == [{"id": "x", "label": "1.5"}]


def test_normalize_dict_missing_id_raises():
    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"label": "no id here"}], None)
    assert "id" in str(excinfo.value)


def test_normalize_dict_includes_group_and_disabled_when_set():
    items, _ = normalize_options(
        [{"id": 1, "label": "A", "group": "G1", "disabled": True}], None
    )
    assert items == [
        {"id": 1, "label": "A", "group": "G1", "disabled": True}
    ]


def test_normalize_dict_omits_group_and_disabled_when_absent():
    items, _ = normalize_options([{"id": 1, "label": "A"}], None)
    assert items == [{"id": 1, "label": "A"}]
    assert "group" not in items[0]
    assert "disabled" not in items[0]


def test_normalize_dict_disabled_false_still_included():
    # explicit disabled=False is "set", so it is carried through
    items, _ = normalize_options([{"id": 1, "label": "A", "disabled": False}], None)
    assert items == [{"id": 1, "label": "A", "disabled": False}]


def test_normalize_dict_non_string_group_raises():
    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"id": 1, "label": "A", "group": 7}], None)
    msg = str(excinfo.value)
    assert "group" in msg
    assert "str" in msg or "string" in msg


def test_normalize_dict_non_bool_disabled_raises():
    # 'disabled' is documented as an optional bool; a non-bool would be
    # forwarded and judged by JS truthiness on the frontend, so reject it here
    # the same way a non-str 'group' is rejected.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"id": 1, "label": "A", "disabled": "yes"}], None)
    msg = str(excinfo.value)
    assert "disabled" in msg
    assert "bool" in msg


def test_normalize_non_iterable_options_raises():
    with pytest.raises(ValueError) as excinfo:
        normalize_options(123, None)  # int is not iterable
    assert "iterable" in str(excinfo.value)


@pytest.mark.parametrize(
    "options, type_name",
    [
        ("Berlin", "str"),  # would render six one-character rows
        (b"ab", "bytes"),  # would render int rows 97 and 98
        (bytearray(b"ab"), "bytearray"),
        ({"id": 1, "label": "One"}, "dict"),  # would render rows "id" and "label"
        (types.MappingProxyType({"id": 1}), "mappingproxy"),  # any Mapping
    ],
)
def test_normalize_rejects_a_bare_str_bytes_or_mapping_as_options(options, type_name):
    # All of these ARE iterable, so iter() alone lets them through — and each
    # element is a legal str/int option, so nothing downstream would flag the
    # mistake; the widget silently rendered the wrong rows.
    with pytest.raises(ValueError) as excinfo:
        normalize_options(options, None)
    msg = str(excinfo.value)
    assert "iterable" in msg
    assert type_name in msg


@pytest.mark.parametrize(
    "options, expected_ids",
    [
        (("Apple", "Banana"), ["Apple", "Banana"]),  # tuple
        (iter(["a", "b"]), ["a", "b"]),  # one-shot iterator
        ({"a": 1, "b": 2}.keys(), ["a", "b"]),  # a KeysView is not a Mapping
        (range(3), [0, 1, 2]),
    ],
)
def test_normalize_accepts_non_list_iterables(options, expected_ids):
    # The bare-str/mapping guard must not over-tighten: any other iterable of
    # options is fine.
    items, _ = normalize_options(options, None)
    assert [item["id"] for item in items] == expected_ids


def test_normalize_duplicate_simple_ids_raises():
    with pytest.raises(ValueError) as excinfo:
        normalize_options(["Apple", "Apple"], None)
    msg = str(excinfo.value)
    assert "duplicate" in msg.lower()
    assert "Apple" in msg


def test_normalize_duplicate_dict_ids_raises():
    with pytest.raises(ValueError) as excinfo:
        normalize_options(
            [{"id": 1, "label": "A"}, {"id": 1, "label": "B"}], None
        )
    assert "duplicate" in str(excinfo.value).lower()


def test_normalize_stringified_id_collision_raises():
    # int 1 and str "1" are distinct dict keys in Python but collapse to the
    # same String(id) on the frontend (React keys, DOM ids, scroll selector),
    # so they must be rejected at the boundary.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([1, "1"], None)
    msg = str(excinfo.value)
    assert "collides" in msg
    assert "'1'" in msg


def test_normalize_stringified_id_collision_dicts_raises():
    with pytest.raises(ValueError) as excinfo:
        normalize_options(
            [{"id": 2, "label": "int two"}, {"id": "2", "label": "str two"}], None
        )
    assert "collides" in str(excinfo.value)


def test_normalize_distinct_stringified_ids_ok():
    # No collision: distinct string forms pass through unchanged.
    items, _ = normalize_options([1, 2, "x"], None)
    assert [it["id"] for it in items] == [1, 2, "x"]


def test_normalize_unhashable_simple_id_raises():
    # a list is unhashable; as a simple value it becomes an unhashable id
    with pytest.raises(ValueError) as excinfo:
        normalize_options([["nested"]], None)
    assert "unhashable" in str(excinfo.value).lower()


def test_normalize_unhashable_dict_id_raises():
    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"id": ["nested"], "label": "A"}], None)
    assert "unhashable" in str(excinfo.value).lower()


def test_normalize_float_id_rejected():
    # The frontend identifies rows by JS String(id); Python str() diverges for
    # floats (str(1.0) == '1.0' but JS String(1.0) === '1'), so a float id 1.0
    # and an int 1 / str "1" would render as the same row yet pass the str()
    # collision guard. Reject float ids outright at the boundary.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([1.0], None)
    msg = str(excinfo.value)
    assert "float" in msg
    assert "1.0" in msg


def test_normalize_float_id_rejected_in_dict_option():
    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"id": 2.5, "label": "two-and-a-half"}], None)
    assert "float" in str(excinfo.value)


def test_normalize_nan_id_rejected():
    # NaN is hashable and unique, so it slips past the dedup/collision guards,
    # but NaN != NaN breaks the selection round-trip and json emits non-standard
    # 'NaN'. Rejected as a (non-finite) float id.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([float("nan")], None)
    assert "float" in str(excinfo.value)


def test_normalize_infinity_id_rejected():
    with pytest.raises(ValueError) as excinfo:
        normalize_options([float("inf")], None)
    assert "float" in str(excinfo.value)


def test_normalize_int_id_still_accepted():
    # Guard against over-broad rejection: genuine ints (not float) are fine.
    items, _ = normalize_options([1, 2], None)
    assert [it["id"] for it in items] == [1, 2]


def test_normalize_bool_id_rejected():
    # bool is an int subclass, so a positive str/int gate must reject it
    # explicitly. It has to go: Python str(True) == 'True' but JS
    # String(true) === 'true', so [True, "true"] slips past the str()-collision
    # guard and renders two rows with the same React key and DOM id.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([True], None)
    msg = str(excinfo.value)
    assert "bool" in msg
    assert "str or int" in msg


def test_normalize_bool_and_str_true_no_longer_collide_silently():
    # The concrete collision the bool gate prevents.
    with pytest.raises(ValueError, match="bool"):
        normalize_options([True, "true"], None)


def test_normalize_none_id_rejected():
    # str(None) == 'None' vs String(null) === 'null': the same as-rendered
    # ambiguity, and None is not a usable row identity.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([{"id": None, "label": "nothing"}], None)
    assert "NoneType" in str(excinfo.value)


def test_normalize_non_json_serializable_id_rejected():
    # A date/Decimal/UUID id is hashable and unique, so it used to sail through —
    # but json.dumps chokes on it and Streamlit's serializer swallows the
    # TypeError and ships json.dumps(str(data)), leaving the frontend with a
    # string where the payload object should be: the widget renders BLANK with no
    # Python-side error. Reject it here instead.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([datetime.date(2026, 1, 1)], None)
    msg = str(excinfo.value)
    assert "date" in msg
    assert "str or int" in msg


def test_normalize_int_id_beyond_js_safe_range_rejected():
    # 2**53 is the first int a JS double cannot represent alongside its
    # neighbours; ids that far out round together (BIGINT PKs, snowflake ids),
    # collapsing distinct rows and breaking the id round-trip.
    with pytest.raises(ValueError) as excinfo:
        normalize_options([2**53], None)
    msg = str(excinfo.value)
    assert "safe integer" in msg
    assert str(MAX_SAFE_JS_INT) in msg


def test_normalize_negative_int_id_beyond_js_safe_range_rejected():
    # The bound is on magnitude, not on sign.
    with pytest.raises(ValueError, match="safe integer"):
        normalize_options([-(2**53)], None)


def test_normalize_two_unsafe_ints_that_would_render_as_one_row_rejected():
    # The verified failure: both of these parse to the same JS Number, so they
    # pass the Python str()-collision guard yet render with the same key.
    with pytest.raises(ValueError, match="safe integer"):
        normalize_options([9007199254740992, 9007199254740993], None)


def test_normalize_max_safe_int_boundary_accepted():
    # Guard against an off-by-one: the largest exactly-representable int, and its
    # negative counterpart, must still be accepted.
    items, _ = normalize_options([MAX_SAFE_JS_INT, -MAX_SAFE_JS_INT], None)
    assert [it["id"] for it in items] == [MAX_SAFE_JS_INT, -MAX_SAFE_JS_INT]


def test_max_safe_js_int_matches_javascript():
    # Number.MAX_SAFE_INTEGER === 9007199254740991
    assert MAX_SAFE_JS_INT == 9007199254740991


def test_map_single_found_returns_original():
    id_to_original = {1: {"id": 1, "label": "A"}, 2: {"id": 2, "label": "B"}}
    result = map_selection([1], id_to_original, "single", accept_new_options=False)
    assert result == {"id": 1, "label": "A"}


def test_map_single_empty_returns_none():
    result = map_selection([], {1: 1}, "single", accept_new_options=False)
    assert result is None


def test_map_single_unknown_id_dropped_returns_none():
    # id not in map and accept_new_options False -> dropped -> None
    result = map_selection([99], {1: 1}, "single", accept_new_options=False)
    assert result is None


def test_map_single_unknown_id_accept_new_returns_str():
    result = map_selection([99], {1: 1}, "single", accept_new_options=True)
    assert result == "99"


def test_map_single_returns_first_mapped_when_multiple_ids():
    id_to_original = {1: "one", 2: "two"}
    result = map_selection([2, 1], id_to_original, "single", accept_new_options=False)
    assert result == "two"


def test_map_multi_found_returns_list_of_originals():
    id_to_original = {1: "one", 2: "two", 3: "three"}
    result = map_selection([1, 3], id_to_original, "multi", accept_new_options=False)
    assert result == ["one", "three"]


def test_map_multi_empty_returns_empty_list():
    result = map_selection([], {1: "one"}, "multi", accept_new_options=False)
    assert result == []


def test_map_multi_preserves_selection_order():
    id_to_original = {1: "one", 2: "two", 3: "three"}
    # ids arrive in selection order 3,1,2 -> originals must follow
    result = map_selection([3, 1, 2], id_to_original, "multi", accept_new_options=False)
    assert result == ["three", "one", "two"]


def test_map_multi_unknown_ids_dropped_when_not_accept_new():
    id_to_original = {1: "one"}
    result = map_selection([1, 99, 2], id_to_original, "multi", accept_new_options=False)
    assert result == ["one"]


def test_map_multi_unknown_ids_kept_as_str_when_accept_new():
    id_to_original = {1: "one"}
    result = map_selection([1, 99, "new"], id_to_original, "multi", accept_new_options=True)
    assert result == ["one", "99", "new"]


def test_map_multi_mixed_found_new_dropped_order_preserved():
    # accept_new True: found originals kept, unknowns become str(id),
    # all in the order the ids appear
    id_to_original = {"a": {"id": "a"}, "b": {"id": "b"}}
    result = map_selection(
        ["b", 5, "a"], id_to_original, "multi", accept_new_options=True
    )
    assert result == [{"id": "b"}, "5", {"id": "a"}]


def test_map_single_accept_new_int_id_stringified():
    # an int id not in the map, accept_new True -> plain str
    result = map_selection([7], {}, "single", accept_new_options=True)
    assert result == "7"
    assert isinstance(result, str)


def test_map_unhashable_selected_id_does_not_crash():
    # state coming back from the frontend should always be hashable scalars,
    # but the lookup must not raise on a stray list id — its row-identity key
    # (a str) exists for any object, so it simply matches no row and is dropped.
    id_to_original = {1: "one"}
    # not accepting new -> the unknown id is simply dropped
    result = map_selection([[99], 1], id_to_original, "multi", accept_new_options=False)
    assert result == ["one"]


def test_map_single_resolves_dtype_flipped_str_id_to_int_original():
    # A keyed widget's selection outlives the payload it was made against: when
    # the options column flips dtype (str "7" -> int 7), the frontend keeps the
    # row selected because it keys rows by String(id). A raw-== lookup called
    # the stored "7" unknown and returned None while the UI showed the row
    # selected; resolution by _id_key row identity maps it to the option.
    result = map_selection(["7"], {7: 7}, "single", accept_new_options=False)
    assert result == 7
    assert isinstance(result, int)


def test_map_single_resolves_dtype_flipped_int_id_to_str_original():
    # The reverse flip: the stored int 7 names the row of the str option "7".
    id_to_original = {"7": {"id": "7", "label": "Seven"}}
    result = map_selection([7], id_to_original, "single", accept_new_options=False)
    assert result == {"id": "7", "label": "Seven"}


def test_map_accept_new_id_matching_option_row_returns_option_immediately():
    # A typed "7" that names the int option 7 IS that option: the mapping
    # resolves by row identity on the way out, so the caller gets the option
    # object on the same rerun — not a plain "7" until the frontend's
    # "7" -> 7 reconciliation write-back lands one rerun later.
    result = map_selection(["7"], {7: 7}, "single", accept_new_options=True)
    assert result == 7
    assert isinstance(result, int)


def test_map_multi_duplicate_keys_collapse_to_earliest_survivor():
    # A key seen twice is one row; the frontend's reconcileSelection collapses
    # it, so the mapping must too — otherwise the value holds the option twice.
    id_to_original = {"a": "A", "b": "B"}
    result = map_selection(
        ["a", "a", "b"], id_to_original, "multi", accept_new_options=False
    )
    assert result == ["A", "B"]


def test_map_multi_duplicate_collapse_happens_before_truncation():
    # ['a', 'a', 'b'] under cap 2 renders as the two rows a and b, and the
    # frontend commits ['a', 'b']. Truncating before collapsing would return
    # ['A', 'A'] — a duplicate consuming a cap slot — so the collapse comes
    # first and the two sides agree on the survivors.
    id_to_original = {"a": "A", "b": "B", "c": "C"}
    result = map_selection(
        ["a", "a", "b"],
        id_to_original,
        "multi",
        accept_new_options=False,
        max_selections=2,
    )
    assert result == ["A", "B"]


def test_map_multi_cross_spelling_duplicate_collapses():
    # 1 and "1" spell the same row; earliest survivor wins, mapped to the
    # original option.
    result = map_selection([1, "1"], {1: "one"}, "multi", accept_new_options=False)
    assert result == ["one"]


def test_map_multi_unknown_duplicate_collapses_under_accept_new():
    # Duplicate collapse applies to synthetic (typed) rows too, matching the
    # frontend, which renders one row for the typed value.
    result = map_selection(["x", "x"], {}, "multi", accept_new_options=True)
    assert result == ["x"]


def test_map_multi_truncates_to_max_selections_keeping_earliest():
    # The rerun that LOWERS max_selections reads selection state made against the
    # old cap: the frontend clamps and commits a correction, but that lands one
    # rerun later. Truncate here so len(result) <= max_selections always holds,
    # keeping the earliest-selected ids — exactly the survivors the frontend keeps.
    id_to_original = {1: "one", 2: "two", 3: "three"}
    result = map_selection(
        [3, 1, 2], id_to_original, "multi", accept_new_options=False, max_selections=2
    )
    assert result == ["three", "one"]


def test_map_multi_under_max_selections_is_untouched():
    id_to_original = {1: "one", 2: "two"}
    result = map_selection(
        [1, 2], id_to_original, "multi", accept_new_options=False, max_selections=5
    )
    assert result == ["one", "two"]


def test_map_multi_max_selections_counts_only_survivors():
    # An unknown id is dropped, so it must not consume a cap slot either — the
    # frontend's reconcile counts only the ids it keeps, and the two must agree.
    id_to_original = {1: "one", 2: "two"}
    result = map_selection(
        [99, 1, 2], id_to_original, "multi", accept_new_options=False, max_selections=2
    )
    assert result == ["one", "two"]


def test_map_single_ignores_max_selections():
    # single mode is already a cap of one; max_selections there is None or 1.
    id_to_original = {1: "one", 2: "two"}
    result = map_selection(
        [2, 1], id_to_original, "single", accept_new_options=False, max_selections=1
    )
    assert result == "two"


def test_sort_none_is_noop_preserves_order():
    items = [
        {"id": "b", "label": "Banana", "group": "Fruit"},
        {"id": "a", "label": "Apple", "group": "Fruit"},
    ]
    assert sort_items(items, None, True) == items


def test_sort_items_within_groups_preserves_group_order():
    items = [
        {"id": "carrot", "label": "Carrot", "group": "Veg"},
        {"id": "beet", "label": "Beet", "group": "Veg"},
        {"id": "banana", "label": "Banana", "group": "Fruit"},
        {"id": "apple", "label": "Apple", "group": "Fruit"},
    ]
    result = sort_items(items, "items", True)
    # Group order (first-appearance: Veg, Fruit) preserved; items sorted within.
    assert [it["id"] for it in result] == ["beet", "carrot", "apple", "banana"]


def test_sort_items_consolidates_ungrouped_at_first_appearance():
    items = [
        {"id": "z", "label": "Zucchini"},                     # ungrouped, first
        {"id": "carrot", "label": "Carrot", "group": "Veg"},
        {"id": "a", "label": "Avocado"},                      # ungrouped again
    ]
    result = sort_items(items, "items", True)
    # Ungrouped block consolidates at its first-appearance position (before Veg),
    # its items sorted: Avocado, Zucchini.
    assert [it["id"] for it in result] == ["a", "z", "carrot"]


def test_sort_groups_orders_named_groups_ungrouped_last():
    items = [
        {"id": "u1", "label": "Ungrouped one"},               # ungrouped
        {"id": "carrot", "label": "Carrot", "group": "Veg"},
        {"id": "beet", "label": "Beet", "group": "Veg"},
        {"id": "banana", "label": "Banana", "group": "Fruit"},
    ]
    result = sort_items(items, "groups", True)
    # Named groups sorted (Fruit, Veg); items within preserved; ungrouped last.
    assert [it["id"] for it in result] == ["banana", "carrot", "beet", "u1"]


def test_sort_both_sorts_groups_and_items_ungrouped_last():
    items = [
        {"id": "u1", "label": "Umbrella"},                    # ungrouped
        {"id": "carrot", "label": "Carrot", "group": "Veg"},
        {"id": "beet", "label": "Beet", "group": "Veg"},
        {"id": "cherry", "label": "Cherry", "group": "Fruit"},
        {"id": "banana", "label": "Banana", "group": "Fruit"},
    ]
    result = sort_items(items, "both", True)
    assert [it["id"] for it in result] == ["banana", "cherry", "beet", "carrot", "u1"]


def test_sort_descending_reverses_items_and_groups_ungrouped_still_last():
    items = [
        {"id": "u1", "label": "Umbrella"},                    # ungrouped
        {"id": "banana", "label": "Banana", "group": "Fruit"},
        {"id": "cherry", "label": "Cherry", "group": "Fruit"},
        {"id": "beet", "label": "Beet", "group": "Veg"},
    ]
    result = sort_items(items, "both", False)
    # Groups desc (Veg, Fruit); items desc within; ungrouped STILL last.
    assert [it["id"] for it in result] == ["beet", "cherry", "banana", "u1"]


def test_sort_is_case_insensitive():
    items = [
        {"id": 1, "label": "banana"},
        {"id": 2, "label": "Apple"},
        {"id": 3, "label": "cherry"},
    ]
    result = sort_items(items, "items", True)
    assert [it["label"] for it in result] == ["Apple", "banana", "cherry"]


def test_sort_is_stable_for_equal_keys():
    items = [
        {"id": "first", "label": "apple"},
        {"id": "second", "label": "Apple"},
    ]
    result = sort_items(items, "items", True)
    assert [it["id"] for it in result] == ["first", "second"]


def test_sort_flat_list_groups_noop_items_and_both_sort():
    items = [
        {"id": "b", "label": "Banana"},
        {"id": "a", "label": "Apple"},
    ]
    assert [it["id"] for it in sort_items(items, "groups", True)] == ["b", "a"]
    assert [it["id"] for it in sort_items(items, "items", True)] == ["a", "b"]
    assert [it["id"] for it in sort_items(items, "both", True)] == ["a", "b"]


def test_sort_empty_list_all_modes():
    for mode in (None, "items", "groups", "both"):
        assert sort_items([], mode, True) == []


def test_sort_does_not_mutate_input():
    items = [
        {"id": "b", "label": "Banana", "group": "Fruit"},
        {"id": "a", "label": "Apple", "group": "Fruit"},
    ]
    snapshot = [dict(it) for it in items]
    sort_items(items, "both", True)
    assert items == snapshot  # original list order + dict contents unchanged
