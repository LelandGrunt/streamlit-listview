import datetime
import re
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TYPES_TS = ROOT / "streamlit_listview" / "frontend" / "src" / "types.ts"


def call(mod, **overrides):
    """Invoke mod.listview with sensible defaults, applying overrides."""
    params = {
        "label": "Pick",
        "options": ["a", "b", "c"],
    }
    params.update(overrides)
    return mod.listview(**params)


# --------------------------------------------------------------------------
# Declaration
# --------------------------------------------------------------------------

def test_component_declared_with_globs_and_root_html(listview_mod):
    mod, fake = listview_mod
    assert fake.declared["name"] == "streamlit_listview.listview"
    assert fake.declared["js"] == "index-*.js"
    assert fake.declared["css"] == "index-*.css"
    assert fake.declared["html"] == '<div class="listview-root"></div>'


# --------------------------------------------------------------------------
# Validation: label / help / placeholder / search_placeholder
#
# All four are forwarded to the frontend as Markdown source or as input text. A
# non-str label reaches escapeLabelSource, whose .replace() throws during React
# render — with no error boundary the widget renders EMPTY and Python never sees
# a traceback. So the type is rejected at the boundary (like collapsed_groups).
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, 42, ["a"], b"bytes"])
def test_label_non_str_raises(listview_mod, bad):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="label must be a str"):
        call(mod, label=bad)


def test_label_empty_string_ok(listview_mod):
    mod, fake = listview_mod
    # "" is a legitimate label (paired with label_visibility="collapsed").
    call(mod, label="", label_visibility="collapsed")
    assert fake.last["data"]["label"] == ""


@pytest.mark.parametrize("bad", [42, ["a"], {"x": 1}])
def test_help_non_str_raises(listview_mod, bad):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="help must be a str or None"):
        call(mod, help=bad)


def test_help_none_and_str_ok(listview_mod):
    mod, fake = listview_mod
    # help is nullable on the frontend (`help: string | null`); None means
    # "no tooltip" and must stay accepted.
    call(mod, help=None)
    assert fake.last["data"]["help"] is None
    call(mod, help="**why**")
    assert fake.last["data"]["help"] == "**why**"


@pytest.mark.parametrize("bad", [42, ["a"]])
def test_placeholder_non_str_raises(listview_mod, bad):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="placeholder must be a str or None"):
        call(mod, placeholder=bad)


def test_placeholder_none_ok(listview_mod):
    mod, fake = listview_mod
    # Nullable on the frontend (`placeholder: string | null`).
    call(mod, placeholder=None)
    assert fake.last["data"]["placeholder"] is None


@pytest.mark.parametrize("bad", [None, 42, ["a"]])
def test_search_placeholder_non_str_raises(listview_mod, bad):
    mod, fake = listview_mod
    # Non-nullable on the frontend (`search_placeholder: string`) and it has a
    # non-None signature default, so None is a wrong type here too.
    with pytest.raises(ValueError, match="search_placeholder must be a str"):
        call(mod, enable_search=True, search_placeholder=bad)


def test_search_placeholder_str_ok(listview_mod):
    mod, fake = listview_mod
    call(mod, enable_search=True, search_placeholder="Filter…")
    assert fake.last["data"]["search_placeholder"] == "Filter…"


# --------------------------------------------------------------------------
# Validation: selection_mode
# --------------------------------------------------------------------------

def test_invalid_selection_mode_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="selection_mode"):
        call(mod, selection_mode="multiple")


def test_select_all_true_in_single_mode_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="select_all"):
        call(mod, selection_mode="single", select_all=True)


@pytest.mark.parametrize("mode", ["single", "multi"])
def test_valid_selection_mode_accepted(listview_mod, mode):
    mod, fake = listview_mod
    # Valid mode must not raise. (Payload content checked in wrapper-call task.)
    call(mod, selection_mode=mode, default=None)


# --------------------------------------------------------------------------
# Validation: label_visibility
# --------------------------------------------------------------------------

def test_invalid_label_visibility_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="label_visibility"):
        call(mod, label_visibility="gone")


@pytest.mark.parametrize("lv", ["visible", "hidden", "collapsed"])
def test_valid_label_visibility_accepted(listview_mod, lv):
    mod, fake = listview_mod
    # Valid visibility must not raise.
    call(mod, label_visibility=lv)


# --------------------------------------------------------------------------
# Validation: width
# --------------------------------------------------------------------------

def test_width_stretch_ok(listview_mod):
    mod, fake = listview_mod
    # Must not raise.
    call(mod, width="stretch")


def test_width_positive_int_ok(listview_mod):
    mod, fake = listview_mod
    # Must not raise.
    call(mod, width=420)


@pytest.mark.parametrize("bad", [0, -5, "wide", 3.5, True])
def test_width_invalid_raises(listview_mod, bad):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="width"):
        call(mod, width=bad)


# --------------------------------------------------------------------------
# Validation: height
# --------------------------------------------------------------------------

def test_height_default_ok(listview_mod):
    mod, fake = listview_mod
    # Default height (300) must not raise.
    call(mod)


@pytest.mark.parametrize("bad", [99, 0, -10, "300", 100.0, True])
def test_height_invalid_raises(listview_mod, bad):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="height"):
        call(mod, height=bad)


def test_height_min_boundary_ok(listview_mod):
    mod, fake = listview_mod
    # Min boundary (100) must not raise.
    call(mod, height=100)


# --------------------------------------------------------------------------
# Validation: item_height
# --------------------------------------------------------------------------

def test_item_height_none_ok(listview_mod):
    mod, fake = listview_mod
    # None must not raise.
    call(mod, item_height=None)


def test_item_height_min_boundary_ok(listview_mod):
    mod, fake = listview_mod
    # Min boundary (1) must not raise. item_height is a min-height floor, so any
    # positive int is accepted; the browser absorbs values below a row's content.
    call(mod, item_height=1)


@pytest.mark.parametrize("bad", [0, -1, "40", 30.0, True])
def test_item_height_invalid_raises(listview_mod, bad):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="item_height"):
        call(mod, item_height=bad)


# --------------------------------------------------------------------------
# Validation: content_font_size
# --------------------------------------------------------------------------

def test_content_font_size_none_ok(listview_mod):
    mod, fake = listview_mod
    # None must not raise (theme-derived default size).
    call(mod, content_font_size=None)


def test_content_font_size_min_boundary_ok(listview_mod):
    mod, fake = listview_mod
    # Min boundary (1) must not raise.
    call(mod, content_font_size=1)


@pytest.mark.parametrize("bad", [0, -1, "12", 12.0, True])
def test_content_font_size_invalid_raises(listview_mod, bad):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="content_font_size"):
        call(mod, content_font_size=bad)


# --------------------------------------------------------------------------
# Validation: max_selections
# --------------------------------------------------------------------------

def test_max_selections_none_ok_multi(listview_mod):
    mod, fake = listview_mod
    # None in multi must not raise.
    call(mod, selection_mode="multi", max_selections=None)


def test_max_selections_positive_ok_multi(listview_mod):
    mod, fake = listview_mod
    # Positive int in multi must not raise.
    call(mod, selection_mode="multi", max_selections=2)


@pytest.mark.parametrize("bad", [0, -1, "2", 2.0, True])
def test_max_selections_invalid_value_raises(listview_mod, bad):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="max_selections"):
        call(mod, selection_mode="multi", max_selections=bad)


def test_max_selections_gt_one_in_single_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="max_selections"):
        call(mod, selection_mode="single", max_selections=2)


def test_max_selections_one_in_single_ok(listview_mod):
    mod, fake = listview_mod
    # 1 in single must not raise.
    call(mod, selection_mode="single", max_selections=1)


def test_default_exceeds_max_selections_raises(listview_mod):
    mod, fake = listview_mod
    # A multi default longer than the cap would otherwise seed (and return) an
    # over-cap selection on first render; reject it like st.multiselect does.
    with pytest.raises(ValueError, match="max_selections"):
        call(
            mod,
            selection_mode="multi",
            default=["a", "b", "c"],
            max_selections=2,
        )


def test_default_equal_to_max_selections_ok(listview_mod):
    mod, fake = listview_mod
    # A default exactly at the cap is fine.
    call(mod, selection_mode="multi", default=["a", "b"], max_selections=2)


def test_default_multi_duplicates_are_deduplicated(listview_mod):
    mod, fake = listview_mod
    # A repeated default id is a single selection: it must be de-duplicated
    # (order preserved) before seeding, so the frontend never receives a
    # duplicate id.
    call(mod, selection_mode="multi", default=["a", "a", "b"])
    assert fake.last["data"]["default_ids"] == ["a", "b"]
    assert fake.last["default"] == {"selection": ["a", "b"]}


def test_default_duplicates_do_not_trip_max_selections(listview_mod):
    mod, fake = listview_mod
    # ["a", "a"] is one distinct option, so max_selections=1 must NOT raise
    # (the count is taken AFTER de-duplication).
    call(mod, selection_mode="multi", default=["a", "a"], max_selections=1)
    assert fake.last["data"]["default_ids"] == ["a"]


def test_default_deduplicates_by_rendered_row_identity(listview_mod):
    mod, fake = listview_mod
    # "1" and 1 are two spellings of ONE row: the frontend keys rows by
    # String(id), renders a single row for the pair and counts it once. So the
    # de-duplication here has to use that same notion of identity rather than
    # Python equality, which calls them distinct — otherwise a default naming one
    # row twice seeds a duplicate id AND is rejected by a max_selections that the
    # rendered selection actually satisfies. accept_new_options, because
    # normalize_options forbids two options whose ids collide as strings, so this
    # pair can only reach here as an unknown default.
    call(
        mod,
        options=["1"],
        selection_mode="multi",
        default=["1", 1],
        max_selections=1,
        accept_new_options=True,
    )
    assert fake.last["data"]["default_ids"] == ["1"]


# --------------------------------------------------------------------------
# Validation: pin_search requires enable_search
# --------------------------------------------------------------------------

def test_select_all_non_bool_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="select_all must be a bool"):
        call(mod, select_all="yes")


def test_select_all_int_rejected(listview_mod):
    mod, fake = listview_mod
    # bool is a subclass of int; isinstance(1, bool) is False, so an int is
    # rejected by the isinstance(..., bool) type check.
    with pytest.raises(ValueError, match="select_all must be a bool"):
        call(mod, select_all=1)


def test_select_all_non_bool_raises_even_in_single_mode(listview_mod):
    mod, fake = listview_mod
    # Type check runs before the single-mode check (§1.7): the type message
    # wins regardless of selection_mode.
    with pytest.raises(ValueError, match="select_all must be a bool"):
        call(mod, selection_mode="single", select_all="yes")


def test_select_all_false_in_single_mode_allowed(listview_mod):
    mod, fake = listview_mod
    # call() seeds non-empty options, so the data dict is always built.
    call(mod, selection_mode="single")  # default select_all=False
    assert fake.last["data"]["select_all"] is False


def test_payload_select_all_true_in_multi(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="multi", select_all=True, default=None)
    assert fake.last["data"]["select_all"] is True


def test_payload_select_all_defaults_false(listview_mod):
    mod, fake = listview_mod
    call(mod)
    assert fake.last["data"]["select_all"] is False


def test_pin_search_without_enable_search_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="pin_search"):
        call(mod, enable_search=False, pin_search=True)


def test_pin_search_with_enable_search_ok(listview_mod):
    mod, fake = listview_mod
    # pin_search with enable_search must not raise.
    call(mod, enable_search=True, pin_search=True)


# --------------------------------------------------------------------------
# Validation: the boolean flags
#
# All eight flags are forwarded to the frontend verbatim and judged by JS
# truthiness there, so a non-bool never fails loudly on its own:
# enable_search="no" ENABLES the search box, accept_new_options="false" ENABLES
# adding, and a truthy non-JSON-serializable disabled blanks the whole widget
# (Streamlit's serializer swallows the TypeError). select_all/sort_ascending
# were already checked; these pin the other six going through the same
# _validate_bool.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("enable_search", "no"),
        ("pin_search", "yes"),
        ("collapsible_groups", "yes"),
        ("accept_new_options", "false"),
        ("show_grid_lines", 1),   # int rejected too: bool is checked by type
        ("disabled", object()),   # truthy AND non-JSON-serializable
    ],
)
def test_flag_non_bool_raises(listview_mod, flag, value):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match=f"{flag} must be a bool"):
        call(mod, **{flag: value})


def test_pin_search_non_bool_named_as_type_error_not_combination(listview_mod):
    mod, fake = listview_mod
    # Type checks run before the flag cross-checks: a truthy non-bool
    # pin_search with enable_search=False must be named a type error, not
    # reported as "pin_search=True requires enable_search=True" for a value that
    # isn't True.
    with pytest.raises(ValueError, match="pin_search must be a bool"):
        call(mod, enable_search=False, pin_search="yes")


# --------------------------------------------------------------------------
# Validation: callables
# --------------------------------------------------------------------------

def test_non_callable_on_change_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="on_change"):
        call(mod, on_change="nope")


def test_non_callable_format_func_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="format_func"):
        call(mod, format_func="nope")


def test_none_format_func_accepted(listview_mod):
    # None is the default and the sentinel for "no formatter", so the callable
    # check must let it through the way the on_change check does.
    mod, fake = listview_mod
    call(mod, format_func=None)


# --------------------------------------------------------------------------
# default -> default_ids resolution + shape validation
# (only the raising behavior is asserted here; payload content is checked in
#  the wrapper-call task where _component is invoked)
# --------------------------------------------------------------------------

def test_default_none_single_no_raise(listview_mod):
    mod, fake = listview_mod
    # None default in single must not raise.
    call(mod, selection_mode="single", default=None)


def test_default_none_multi_no_raise(listview_mod):
    mod, fake = listview_mod
    # None default in multi must not raise.
    call(mod, selection_mode="multi", default=None)


def test_default_single_scalar_no_raise(listview_mod):
    mod, fake = listview_mod
    # A known scalar default in single must not raise.
    call(mod, selection_mode="single", default="b")


def test_default_single_list_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="default"):
        call(mod, selection_mode="single", default=["a"])


def test_default_multi_list_no_raise(listview_mod):
    mod, fake = listview_mod
    # A list of known ids in multi must not raise.
    call(mod, selection_mode="multi", default=["a", "c"])


def test_default_multi_scalar_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="default"):
        call(mod, selection_mode="multi", default="a")


def test_default_unknown_id_raises_when_not_accept_new(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="default"):
        call(mod, selection_mode="single", default="zzz")


def test_default_unknown_id_allowed_when_accept_new(listview_mod):
    mod, fake = listview_mod
    # Unknown default id is permitted when accept_new_options=True.
    call(mod, selection_mode="single", default="zzz", accept_new_options=True)


def test_default_multi_unknown_id_raises_when_not_accept_new(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="default"):
        call(mod, selection_mode="multi", default=["a", "zzz"])


def test_default_unhashable_raises_value_error_not_type_error(listview_mod):
    mod, fake = listview_mod
    # Round-tripping a returned dict option (default=OPTS[0]) is the natural way
    # to get here. The de-dup and the membership test both hash the id, so
    # without a guard this escapes as a bare TypeError from a library internal —
    # contradicting the documented "shape mismatches raise ValueError".
    opts = [{"id": "a", "label": "A"}]
    with pytest.raises(ValueError, match="unhashable"):
        mod.listview("Pick", opts, selection_mode="single", default=opts[0])


def test_default_unhashable_in_multi_list_raises_value_error(listview_mod):
    mod, fake = listview_mod
    opts = [{"id": "a", "label": "A"}]
    with pytest.raises(ValueError, match="unhashable"):
        mod.listview("Pick", opts, selection_mode="multi", default=[opts[0]])


def test_default_unhashable_raises_even_when_accept_new_options(listview_mod):
    mod, fake = listview_mod
    # accept_new_options skips the membership check, but the de-duplication still
    # hashes, so the guard must run before it regardless.
    with pytest.raises(ValueError, match="unhashable"):
        call(
            mod,
            selection_mode="multi",
            default=[{"id": "a"}],
            accept_new_options=True,
        )


# --------------------------------------------------------------------------
# default ids go through the SAME boundary gate as option ids (_validate_id):
# a default is seeded straight into the frontend selection, so an id the
# JSON/String(id) boundary cannot carry is just as broken there as in options.
# --------------------------------------------------------------------------

def test_default_bool_rejected(listview_mod):
    mod, fake = listview_mod
    # True == 1, so the old raw-== membership accepted default=True against an
    # int option 1 — seeding an id that matches no rendered row (String(true)),
    # desyncing the UI from the returned value. Rejected like an option id.
    with pytest.raises(ValueError, match="default id must be a str or int"):
        call(mod, options=[1, 2], selection_mode="single", default=True)


def test_default_float_rejected(listview_mod):
    mod, fake = listview_mod
    # str(1.0) == '1.0' but String(1.0) === '1': a float default spells its row
    # differently on the two sides, so it is rejected like a float option id.
    with pytest.raises(ValueError, match="default id must be a str or int"):
        call(mod, options=[1, 2], selection_mode="single", default=1.0)


def test_default_decimal_rejected_even_when_equality_would_match(listview_mod):
    mod, fake = listview_mod
    # Decimal('7') == 7, so the old raw-== membership accepted it — then
    # json.dumps choked on the payload, Streamlit swallowed the TypeError, and
    # the widget rendered BLANK with no Python-side error at all.
    with pytest.raises(ValueError, match="default id must be a str or int"):
        call(mod, options=[7], selection_mode="single", default=Decimal("7"))


def test_default_unsafe_int_rejected_even_with_accept_new_options(listview_mod):
    mod, fake = listview_mod
    # accept_new_options waives membership, not representability: 2**53 + 1
    # rounds on the IEEE-754 side, so the id coming back never equals the one
    # seeded and the selection silently drops on every rerun.
    with pytest.raises(ValueError, match="safe integer"):
        call(
            mod,
            selection_mode="single",
            default=2**53 + 1,
            accept_new_options=True,
        )


def test_default_mixed_int_float_spellings_raise_on_the_float(listview_mod):
    mod, fake = listview_mod
    # [1, 1.0] used to slip the gate and miscount against max_selections
    # (_id_key(1.0) != '1' although JS String(1.0) === '1', so the de-dup kept
    # both). The float is now rejected outright, before any counting.
    with pytest.raises(ValueError, match="not float"):
        call(
            mod,
            options=[1, 2],
            selection_mode="multi",
            default=[1, 1.0],
            max_selections=1,
        )


def test_default_membership_judged_by_rendered_row_identity(listview_mod):
    mod, fake = listview_mod
    # The str default "1" names the row the int option 1 renders (the frontend
    # keys rows by String(id)), so membership accepts it — raw Python ==
    # called it absent and raised. The seed is shipped in the OPTION's own
    # spelling: the frontend canonicalizes its selection to that spelling on
    # first render and commits any difference through setStateValue, so a seed
    # of ["1"] cost an extra rerun and a spurious on_change at mount.
    result = call(mod, options=[1, 2], selection_mode="single", default="1")
    assert fake.last["data"]["default_ids"] == [1]
    assert fake.last["default"] == {"selection": [1]}
    assert result == 1
    assert isinstance(result, int)


def test_default_is_canonicalized_to_the_option_spelling_with_accept_new_options(
    listview_mod,
):
    # Same canonicalization when accept_new_options is on: "7" names the row of
    # the int option 7, so it ships as 7; the genuinely unknown "new" stays as
    # given (it is the synthetic row's id and label).
    mod, fake = listview_mod
    call(
        mod,
        options=[7, 8],
        selection_mode="multi",
        default=["7", "new"],
        accept_new_options=True,
    )
    assert fake.last["data"]["default_ids"] == [7, "new"]
    assert fake.last["default"] == {"selection": [7, "new"]}


# --------------------------------------------------------------------------
# Deferred valid-value payload assertions (now that _component is invoked)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["single", "multi"])
def test_payload_selection_mode(listview_mod, mode):
    mod, fake = listview_mod
    call(mod, selection_mode=mode, default=None)
    assert fake.last["data"]["selection_mode"] == mode


@pytest.mark.parametrize("lv", ["visible", "hidden", "collapsed"])
def test_payload_label_visibility(listview_mod, lv):
    mod, fake = listview_mod
    call(mod, label_visibility=lv)
    assert fake.last["data"]["label_visibility"] == lv


def test_payload_width_stretch(listview_mod):
    mod, fake = listview_mod
    call(mod, width="stretch")
    assert fake.last["data"]["width"] == "stretch"


def test_payload_width_positive_int(listview_mod):
    mod, fake = listview_mod
    call(mod, width=420)
    assert fake.last["data"]["width"] == 420


def test_payload_height_default(listview_mod):
    mod, fake = listview_mod
    call(mod)
    assert fake.last["data"]["height"] == 300


def test_payload_height_min_boundary(listview_mod):
    mod, fake = listview_mod
    call(mod, height=100)
    assert fake.last["data"]["height"] == 100


def test_payload_item_height_none(listview_mod):
    mod, fake = listview_mod
    call(mod, item_height=None)
    assert fake.last["data"]["item_height"] is None


def test_payload_item_height_min_boundary(listview_mod):
    mod, fake = listview_mod
    call(mod, item_height=1)
    assert fake.last["data"]["item_height"] == 1


def test_payload_content_font_size_none(listview_mod):
    mod, fake = listview_mod
    call(mod, content_font_size=None)
    assert fake.last["data"]["content_font_size"] is None


def test_payload_content_font_size_value(listview_mod):
    mod, fake = listview_mod
    call(mod, content_font_size=12)
    assert fake.last["data"]["content_font_size"] == 12


def test_payload_show_grid_lines_default_true(listview_mod):
    mod, fake = listview_mod
    call(mod)
    assert fake.last["data"]["show_grid_lines"] is True


def test_payload_show_grid_lines_false(listview_mod):
    mod, fake = listview_mod
    call(mod, show_grid_lines=False)
    assert fake.last["data"]["show_grid_lines"] is False


def test_payload_max_selections_none_multi(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="multi", max_selections=None)
    assert fake.last["data"]["max_selections"] is None


def test_payload_max_selections_positive_multi(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="multi", max_selections=2)
    assert fake.last["data"]["max_selections"] == 2


def test_payload_max_selections_one_single(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="single", max_selections=1)
    assert fake.last["data"]["max_selections"] == 1


def test_payload_pin_search_with_enable_search(listview_mod):
    mod, fake = listview_mod
    call(mod, enable_search=True, pin_search=True)
    assert fake.last["data"]["pin_search"] is True
    assert fake.last["data"]["enable_search"] is True


# --------------------------------------------------------------------------
# default_ids payload (resolution behavior asserted earlier; value here)
# --------------------------------------------------------------------------

def test_payload_default_ids_none_single_empty(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="single", default=None)
    assert fake.last["data"]["default_ids"] == []


def test_payload_default_ids_single_scalar_wraps(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="single", default="b")
    assert fake.last["data"]["default_ids"] == ["b"]


def test_payload_default_ids_multi_passthrough(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="multi", default=["a", "c"])
    assert fake.last["data"]["default_ids"] == ["a", "c"]


def test_payload_default_ids_unknown_when_accept_new(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="single", default="zzz", accept_new_options=True)
    assert fake.last["data"]["default_ids"] == ["zzz"]


# --------------------------------------------------------------------------
# format_func contract end-to-end (locks normalize_options <-> wrapper)
# --------------------------------------------------------------------------

def test_dict_option_no_format_func_label_from_id(listview_mod):
    mod, fake = listview_mod
    # The signature default is format_func=None, which labels by str(id), so a
    # label-less dict is labelled '1' — NEVER str(dict).
    mod.listview("L", [{"id": 1}])
    items = fake.last["data"]["items"]
    assert items == [{"id": 1, "label": "1"}]


def test_format_func_receives_option_and_yields_to_explicit_label(listview_mod):
    mod, fake = listview_mod
    # The documented contract, end-to-end: format_func gets the option as passed
    # — the dict for dict options, the scalar itself for plain values — and a
    # dict's own 'label' wins over it.
    mod.listview(
        "L",
        [
            {"id": "apple", "text": "Apple"},
            {"id": "berlin", "label": "Berlin"},
            "cherry",
        ],
        format_func=lambda o: f"#{o['text'] if isinstance(o, dict) else o}",
    )
    items = fake.last["data"]["items"]
    assert [it["label"] for it in items] == ["#Apple", "Berlin", "#cherry"]


# --------------------------------------------------------------------------
# _component mount call: kwargs, default seeding, callback registration
# --------------------------------------------------------------------------

def test_mount_passes_key_through(listview_mod):
    mod, fake = listview_mod
    call(mod, key="my_key")
    assert fake.last["key"] == "my_key"


# --------------------------------------------------------------------------
# Payload: state_selection — the persisted st.session_state selection that
# re-seeds a frontend remount which kept the Python-side widget state (a keyed
# widget moved between st.sidebar and the main body). _persisted_selection is
# best-effort: everything short of a well-shaped state ships None, which the
# frontend reads as "seed from default_ids".
# --------------------------------------------------------------------------

def test_state_selection_is_none_without_a_key(listview_mod):
    mod, fake = listview_mod
    call(mod)
    assert fake.last["data"]["state_selection"] is None


def test_state_selection_is_none_when_the_key_has_no_state(listview_mod):
    # No script run context here, so the read goes to streamlit's bare-mode
    # mock session state, where an unknown key raises KeyError — the same
    # "nothing persisted" answer a real first run gives.
    mod, fake = listview_mod
    call(mod, key="lv_state_never_written")
    assert fake.last["data"]["state_selection"] is None


def test_state_selection_mirrors_a_well_formed_persisted_state(
    listview_mod, monkeypatch
):
    import streamlit as st

    mod, fake = listview_mod
    persisted = ["b"]
    monkeypatch.setattr(st, "session_state", {"lv": {"selection": persisted}})
    call(mod, key="lv")
    shipped = fake.last["data"]["state_selection"]
    assert shipped == ["b"]
    # A copy, not the live session-state list: the V2 presenter hands out a
    # write-through view of the widget state, which the payload must not alias.
    assert shipped is not persisted


@pytest.mark.parametrize(
    "state",
    [
        "not-a-dict",
        ["selection"],
        {},  # no "selection" key at all
        {"selection": "abc"},  # a str would be iterated per character downstream
        {"selection": 7},
        None,
        # Element checks: every persisted id crosses the same JSON/String(id)
        # boundary as an option id, so it goes through the same _validate_id
        # gate. A Decimal or date is not JSON-serializable — Streamlit's
        # serializer swallows the TypeError and ships str(data), blanking the
        # widget with no Python error; a bool renders as "true" and matches no
        # row; 2**53 + 1 rounds on the frontend; a float spells its row
        # differently than Python does.
        {"selection": [Decimal("7")]},
        {"selection": [datetime.date(2026, 9, 2)]},
        {"selection": [True]},
        {"selection": [2**53 + 1]},
        {"selection": [1.0]},
        {"selection": [None]},
        {"selection": ["a", Decimal("7")]},  # whole list or nothing, not filtered
    ],
)
def test_state_selection_is_none_for_malformed_persisted_state(
    listview_mod, monkeypatch, state
):
    # st.session_state[key] is user-writable, so the persisted value can be
    # anything; only a dict with a list of boundary-safe ids under "selection"
    # is trusted.
    import streamlit as st

    mod, fake = listview_mod
    monkeypatch.setattr(st, "session_state", {"lv": state})
    call(mod, key="lv")
    assert fake.last["data"]["state_selection"] is None


def test_mount_seeds_default_selection(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="multi", default=["a", "c"])
    assert fake.last["default"] == {"selection": ["a", "c"]}


def test_mount_default_selection_empty_when_no_default(listview_mod):
    mod, fake = listview_mod
    call(mod, default=None)
    assert fake.last["default"] == {"selection": []}


def test_first_render_returns_mapped_default(listview_mod):
    # With no explicit frontend result set, the fake mirrors the V2 runtime: on
    # first render it echoes the seeded default= state. This exercises the real
    # default -> selection round-trip + map_selection mapping that a fake which
    # always returned {"selection": []} verbatim would silently bypass — so a
    # regression dropping first-render default seeding is now caught.
    mod, fake = listview_mod
    result = call(mod, selection_mode="multi", default=["a", "c"])
    assert result == ["a", "c"]


def test_first_render_single_returns_mapped_default(listview_mod):
    mod, fake = listview_mod
    result = call(mod, selection_mode="single", default="b")
    assert result == "b"


def test_on_selection_change_always_registered(listview_mod):
    mod, fake = listview_mod
    call(mod, on_change=None)
    cb = fake.last["on_selection_change"]
    assert callable(cb)
    # No-op callback takes no args and returns None.
    assert cb() is None


def test_on_selection_change_wraps_user_callback_with_args_kwargs(listview_mod):
    mod, fake = listview_mod
    received = {}

    def my_cb(*a, **k):
        received["args"] = a
        received["kwargs"] = k

    call(
        mod,
        on_change=my_cb,
        args=(1, 2),
        kwargs={"x": 9},
    )
    cb = fake.last["on_selection_change"]
    # V2 invokes the registered callback with zero arguments.
    cb()
    assert received["args"] == (1, 2)
    assert received["kwargs"] == {"x": 9}


def test_on_selection_change_wrapper_handles_missing_args_kwargs(listview_mod):
    mod, fake = listview_mod
    calls = []

    call(mod, on_change=lambda: calls.append(True))
    fake.last["on_selection_change"]()
    assert calls == [True]


def test_data_payload_has_exact_listview_data_keys(listview_mod):
    mod, fake = listview_mod
    call(mod)
    expected_keys = {
        "label", "help", "items", "selection_mode", "default_ids",
        "state_selection",
        "enable_search", "pin_search", "search_placeholder", "collapsible_groups",
        "collapsed_groups", "accept_new_options", "max_selections",
        "placeholder", "height", "item_height", "content_font_size",
        "width", "show_grid_lines", "select_all", "disabled", "label_visibility",
    }
    assert set(fake.last["data"].keys()) == expected_keys


def _ts_interface_fields(source: str, name: str) -> set[str]:
    """Field names declared in the TypeScript ``interface <name>`` block.

    A regex rather than a real parser: the interface is a flat list of
    ``field: type;`` lines, so pulling a TypeScript toolchain into the Python
    suite would cost far more than it guards. Kept strict about the block
    delimiters so a restructured types.ts fails loudly instead of matching
    nothing and passing vacuously.
    """
    block = re.search(
        rf"^export interface {name} \{{$(.*?)^\}}$",
        source,
        re.DOTALL | re.MULTILINE,
    )
    assert block, f"interface {name} not found in {TYPES_TS.name}"
    fields = set()
    for line in block.group(1).splitlines():
        declaration = line.split("//", 1)[0].strip()  # drop trailing comments
        match = re.match(r"(\w+)\??\s*:", declaration)
        if match:
            fields.add(match.group(1))
    return fields


def test_data_payload_matches_the_frontend_listview_data_interface(listview_mod):
    """Cross-language drift guard for the payload contract.

    The `data` dict and the TS `ListviewData` interface describe the same object
    on either side of a JSON boundary that no compiler crosses, and each language's
    key-set test only re-states its own copy — so renaming a key on one side (say
    `pin_search`) leaves pytest, tsc and both of those tests green while the widget
    reads `undefined` at runtime. Deriving the expectation from the *other*
    language's source is what makes that impossible.
    """
    mod, fake = listview_mod
    call(mod)

    declared = _ts_interface_fields(
        TYPES_TS.read_text(encoding="utf-8"), "ListviewData"
    )
    assert "pin_search" in declared, "sanity: failed to parse ListviewData's fields"

    sent = set(fake.last["data"])
    assert sent == declared, (
        "the Python payload and ListviewData have drifted — "
        f"sent but not declared in types.ts: {sorted(sent - declared)}; "
        f"declared but never sent: {sorted(declared - sent)}"
    )


def test_v2_width_height_not_passed_layout_is_in_data(listview_mod):
    mod, fake = listview_mod
    call(mod, width=400, height=250)
    # Layout travels inside data, not as V2 mount width/height kwargs.
    assert "width" not in fake.last
    assert "height" not in fake.last
    assert fake.last["data"]["width"] == 400
    assert fake.last["data"]["height"] == 250


# --------------------------------------------------------------------------
# Return-value mapping via map_selection
# --------------------------------------------------------------------------

def test_return_single_maps_to_original_value(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": ["b"]}
    result = call(mod, selection_mode="single")
    assert result == "b"


def test_return_single_none_when_empty(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": []}
    result = call(mod, selection_mode="single")
    assert result is None


def test_return_single_none_when_selection_key_absent(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {}  # e.g. first run / no script context
    result = call(mod, selection_mode="single")
    assert result is None


def test_return_multi_maps_in_selection_order(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": ["c", "a"]}
    result = call(mod, selection_mode="multi")
    assert result == ["c", "a"]


def test_return_multi_empty_list_when_none_selected(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": []}
    result = call(mod, selection_mode="multi")
    assert result == []


def test_return_maps_dict_options_to_originals(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": [2]}
    opts = [
        {"id": 1, "label": "One"},
        {"id": 2, "label": "Two", "group": "G"},
    ]
    result = mod.listview("Pick", opts, selection_mode="single")
    assert result == {"id": 2, "label": "Two", "group": "G"}


def test_return_unknown_id_dropped_when_not_accept_new(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": ["ghost"]}
    result = mod.listview(
        "Pick", ["a", "b"], selection_mode="multi", accept_new_options=False
    )
    assert result == []


def test_return_unknown_id_as_string_when_accept_new(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": ["typed", "a"]}
    result = mod.listview(
        "Pick", ["a", "b"], selection_mode="multi", accept_new_options=True
    )
    assert result == ["typed", "a"]


def test_return_non_list_selection_ignored_multi(listview_mod):
    # A tampered/compromised or buggy frontend could return a non-list selection
    # (the TS type is Id[], but that is not a runtime guarantee). It must be
    # treated as "no selection", never iterated char-by-char (a string "ab"
    # would otherwise map to ["a", "b"]).
    mod, fake = listview_mod
    fake.return_value = {"selection": "ab"}
    result = mod.listview("Pick", ["a", "b"], selection_mode="multi")
    assert result == []


def test_return_non_list_selection_ignored_single(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": {"a": 1}}  # dict, not a list
    result = mod.listview("Pick", ["a", "b"], selection_mode="single")
    assert result is None


def test_return_truncated_to_max_selections(listview_mod):
    # max_selections must be a real postcondition, not just a check on `default=`.
    # This is the rerun that lowers the cap: the frontend still holds the selection
    # made under the old one, clamps it and commits the correction — but that
    # commit only arrives on the NEXT rerun, so the state read here is over-cap.
    # Truncating (never raising: a keyed widget carrying stale state is not the app
    # author's error) keeps len(result) <= max_selections on every rerun.
    mod, fake = listview_mod
    fake.return_value = {"selection": ["c", "a", "b"]}
    result = mod.listview(
        "Pick", ["a", "b", "c"], selection_mode="multi", max_selections=2
    )
    # Earliest-selected survive, matching which ids the frontend keeps.
    assert result == ["c", "a"]


def test_return_within_max_selections_untouched(listview_mod):
    mod, fake = listview_mod
    fake.return_value = {"selection": ["a", "b"]}
    result = mod.listview(
        "Pick", ["a", "b", "c"], selection_mode="multi", max_selections=2
    )
    assert result == ["a", "b"]


# --------------------------------------------------------------------------
# Empty-options placeholder default + auto-disable
# --------------------------------------------------------------------------

def test_no_options_no_add_defaults_placeholder_and_disables(listview_mod):
    mod, fake = listview_mod
    call(mod, options=[], accept_new_options=False, placeholder=None)
    assert fake.last["data"]["placeholder"] == "No options to select"
    assert fake.last["data"]["disabled"] is True


def test_no_options_no_add_keeps_custom_placeholder_but_still_disables(listview_mod):
    mod, fake = listview_mod
    call(mod, options=[], accept_new_options=False, placeholder="Pick a city")
    assert fake.last["data"]["placeholder"] == "Pick a city"
    assert fake.last["data"]["disabled"] is True


def test_no_options_but_accept_new_options_is_not_disabled(listview_mod):
    mod, fake = listview_mod
    call(mod, options=[], accept_new_options=True, placeholder=None)
    # adding is allowed, so the widget stays usable and the placeholder is untouched
    assert fake.last["data"]["disabled"] is False
    assert fake.last["data"]["placeholder"] is None


def test_options_present_leaves_placeholder_and_disabled_untouched(listview_mod):
    mod, fake = listview_mod
    call(mod, placeholder=None)  # default options ["a", "b", "c"]
    assert fake.last["data"]["disabled"] is False
    assert fake.last["data"]["placeholder"] is None


def test_select_all_not_in_default_state(listview_mod):
    mod, fake = listview_mod
    call(mod, selection_mode="multi", default=["a", "c"], select_all=True)
    assert fake.last["default"] == {"selection": ["a", "c"]}
    assert "select_all" not in fake.last["default"]


# --------------------------------------------------------------------------
# Validation: collapsed_groups
# --------------------------------------------------------------------------

def test_collapsed_groups_none_ok(listview_mod):
    mod, fake = listview_mod
    # None must not raise.
    call(mod, collapsible_groups=True, collapsed_groups=None)


def test_collapsed_groups_all_ok(listview_mod):
    mod, fake = listview_mod
    # The "all" sentinel must not raise.
    call(mod, collapsible_groups=True, collapsed_groups="all")


def test_collapsed_groups_list_of_str_ok(listview_mod):
    mod, fake = listview_mod
    # A list of group-name strings must not raise.
    call(mod, collapsible_groups=True, collapsed_groups=["Germany"])


def test_collapsed_groups_bare_string_raises(listview_mod):
    mod, fake = listview_mod
    # A bare string that is not "all" is a common mistake (forgetting the list).
    # It must be rejected at the boundary, never forwarded to the frontend (which
    # calls .filter on it and crashes the whole widget during render).
    with pytest.raises(ValueError, match="collapsed_groups"):
        call(mod, collapsible_groups=True, collapsed_groups="Germany")


def test_collapsed_groups_wrong_type_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="collapsed_groups"):
        call(mod, collapsible_groups=True, collapsed_groups=123)


def test_collapsed_groups_non_str_element_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="collapsed_groups"):
        call(mod, collapsible_groups=True, collapsed_groups=["Germany", 7])


# --------------------------------------------------------------------------
# Validation: sort / sort_ascending
# --------------------------------------------------------------------------

def test_invalid_sort_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="sort"):
        call(mod, sort="alphabetical")


def test_sort_ascending_must_be_bool_raises(listview_mod):
    mod, fake = listview_mod
    with pytest.raises(ValueError, match="sort_ascending"):
        call(mod, sort_ascending="yes")


def test_sort_none_with_ascending_false_allowed(listview_mod):
    mod, fake = listview_mod
    # sort_ascending is ignored when sort is None; must not raise.
    call(mod, sort=None, sort_ascending=False)


@pytest.mark.parametrize("mode", ["items", "groups", "both"])
def test_valid_sort_modes_accepted(listview_mod, mode):
    mod, fake = listview_mod
    call(mod, sort=mode)


# --------------------------------------------------------------------------
# Payload: sort reorders data["items"] but adds no data key
# --------------------------------------------------------------------------

def test_payload_items_sorted_with_sort_both(listview_mod):
    mod, fake = listview_mod
    call(
        mod,
        options=[
            {"id": "carrot", "label": "Carrot", "group": "Veg"},
            {"id": "beet", "label": "Beet", "group": "Veg"},
            {"id": "banana", "label": "Banana", "group": "Fruit"},
        ],
        sort="both",
    )
    items = fake.last["data"]["items"]
    # Groups sorted (Fruit, Veg); items sorted within.
    assert [it["id"] for it in items] == ["banana", "beet", "carrot"]


def test_payload_items_unsorted_by_default(listview_mod):
    mod, fake = listview_mod
    call(
        mod,
        options=[
            {"id": "carrot", "label": "Carrot", "group": "Veg"},
            {"id": "banana", "label": "Banana", "group": "Fruit"},
        ],
    )
    items = fake.last["data"]["items"]
    assert [it["id"] for it in items] == ["carrot", "banana"]


def test_sort_params_not_in_data_payload(listview_mod):
    mod, fake = listview_mod
    call(mod, sort="items", sort_ascending=False)
    assert "sort" not in fake.last["data"]
    assert "sort_ascending" not in fake.last["data"]
