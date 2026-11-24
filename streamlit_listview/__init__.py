from __future__ import annotations

import reprlib
import threading
from collections.abc import Callable, Iterable
from typing import Any, Literal, TypeGuard

import streamlit as st

from ._options import (
    NewOptionKind,
    _id_key,
    _parse_new_int_id,
    _validate_id,
    map_selection,
    new_option_kind,
    normalize_options,
    sort_items,
)

_COMPONENT_NAME = "streamlit_listview.listview"

_component: Callable[..., Any] | None = None
_component_lock = threading.Lock()


def _get_component() -> Callable[..., Any]:
    """The component callable, declared on the first call.

    The declaration resolves the js= and css= globs through the component
    manifests, which only a Streamlit runtime (a server or an AppTest run) has
    read. Outside one it raises StreamlitAPIException, and an app's tests import
    their modules, and with them this package, before any AppTest runs. So the
    declaration waits for the first listview() call, which runs inside a
    script. The lock keeps two sessions that render their first listview at the
    same moment from declaring the name twice.
    """
    global _component
    with _component_lock:
        if _component is None:
            _component = st.components.v2.component(
                _COMPONENT_NAME,
                js="index-*.js",
                css="index-*.css",
                html='<div class="listview-root"></div>',
            )
        return _component


_SELECTION_MODES = ("single", "multi")
_LABEL_VISIBILITIES = ("visible", "hidden", "collapsed")
_SORT_MODES = ("items", "groups", "both")


def _is_real_int(value: Any) -> TypeGuard[int]:
    """True for genuine ints, rejecting bool (a subclass of int)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_int_at_least(value: Any, minimum: int) -> bool:
    """True for a genuine int at or above ``minimum``.

    THE int-parameter contract, shared by ``_validate_int`` and by ``width`` (whose
    message differs only because it also accepts ``"stretch"``). Widening what
    counts as an int — a numpy integer from ``df.shape[0]``, say — has to widen it
    for every numeric parameter at once, which two copies of the predicate could
    not guarantee.
    """
    return _is_real_int(value) and value >= minimum


def _validate_bool(name: str, value: Any) -> None:
    """Reject a non-bool value for one flag parameter.

    The flags differ only in their name, so one check serves them all — see
    ``_validate_str`` on why the message text is spelled out rather than derived.
    """
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a bool, got {type(value).__name__}.")


def _validate_str(name: str, value: Any, *, allow_none: bool) -> None:
    """Reject a non-str value for one text parameter.

    The text params differ only in their name and in whether None is a legal
    "not shown", so one check serves them all. The message wording is part of the
    public contract (the suite matches on it), hence the fixed " or None" suffix
    rather than anything derived from the type.
    """
    if allow_none and value is None:
        return
    if not isinstance(value, str):
        expected = "a str or None" if allow_none else "a str"
        raise ValueError(f"{name} must be {expected}, got {type(value).__name__}.")


def _validate_int(name: str, value: Any, *, minimum: int, allow_none: bool) -> None:
    """Reject a non-int or out-of-range value for one numeric parameter.

    The numeric params differ only in their name, their floor and whether None
    means "unset", so one check serves them all — see `_validate_str` on why the
    message text is spelled out rather than derived.
    """
    if allow_none and value is None:
        return
    if not _is_int_at_least(value, minimum):
        expected = (
            f"None or an int >= {minimum}" if allow_none else f"an int >= {minimum}"
        )
        raise ValueError(f"{name} must be {expected}, got {value!r}.")


def _validate_params(  # noqa: C901 -- older than the complexity limit; split it when you next change it
    *,
    label: Any,
    help: Any,
    placeholder: Any,
    search_placeholder: Any,
    ungrouped_label: Any,
    selection_mode: str,
    label_visibility: str,
    width: Any,
    height: Any,
    item_height: Any,
    content_font_size: Any,
    max_selections: Any,
    enable_search: Any,
    pin_search: Any,
    collapsible_groups: Any,
    accept_new_options: Any,
    show_grid_lines: Any,
    disabled: Any,
    format_func: Any,
    on_change: Any,
    args: Any,
    kwargs: Any,
    select_all: Any,
    sort: Any,
    sort_ascending: Any,
    collapsed_groups: Any,
) -> None:
    """Validate scalar parameters per spec §7. Raises ValueError."""
    # The five text params are handed to the frontend verbatim — `label` and
    # `help` as Markdown source, the two placeholders as <input>/empty-state
    # text, and `ungrouped_label` as the plain-text header of the options
    # without a group.
    # A non-str `label` reaches escapeLabelSource, which calls .replace() on it and
    # throws during React render; like the collapsed_groups shape below, that
    # crashes the whole widget with nothing to show for it on the Python side (no
    # traceback, just an empty component). So the type is checked here.
    #
    # None-ness deliberately mirrors the signature defaults *and* the frontend's
    # ListviewData contract: `label`, `search_placeholder` and `ungrouped_label`
    # are non-nullable strings there, while `help: string | null` and
    # `placeholder: string | null` use null to mean "not shown". Only wrong types
    # are rejected; which params accept None is unchanged.
    _validate_str("label", label, allow_none=False)
    _validate_str("help", help, allow_none=True)
    _validate_str("placeholder", placeholder, allow_none=True)
    _validate_str("search_placeholder", search_placeholder, allow_none=False)
    _validate_str("ungrouped_label", ungrouped_label, allow_none=False)

    if selection_mode not in _SELECTION_MODES:
        raise ValueError(
            f"selection_mode must be one of {_SELECTION_MODES!r}, got {selection_mode!r}."
        )

    if label_visibility not in _LABEL_VISIBILITIES:
        raise ValueError(
            "label_visibility must be one of "
            f"{_LABEL_VISIBILITIES!r}, got {label_visibility!r}."
        )

    if width != "stretch" and not _is_int_at_least(width, 1):
        raise ValueError(f'width must be "stretch" or an int >= 1, got {width!r}.')

    _validate_int("height", height, minimum=100, allow_none=False)
    _validate_int("item_height", item_height, minimum=1, allow_none=True)
    _validate_int("content_font_size", content_font_size, minimum=1, allow_none=True)
    _validate_int("max_selections", max_selections, minimum=1, allow_none=True)

    if (
        max_selections is not None
        and selection_mode == "single"
        and max_selections != 1
    ):
        raise ValueError(
            'max_selections must be None or 1 when selection_mode="single", '
            f"got {max_selections!r}."
        )

    # The eight flag params are forwarded to the frontend verbatim and judged by
    # JS truthiness there, so a non-bool never fails loudly on its own:
    # enable_search="no" ENABLES the search box, accept_new_options="false"
    # ENABLES adding, and a truthy non-JSON-serializable value blanks the whole
    # widget (Streamlit's serializer swallows the TypeError — see
    # collapsed_groups below). The type checks run before the flag cross-checks
    # so a wrong type is named as such, never reported as a spurious
    # combination error.
    _validate_bool("enable_search", enable_search)
    _validate_bool("pin_search", pin_search)
    _validate_bool("collapsible_groups", collapsible_groups)
    _validate_bool("accept_new_options", accept_new_options)
    _validate_bool("show_grid_lines", show_grid_lines)
    _validate_bool("disabled", disabled)
    _validate_bool("select_all", select_all)
    _validate_bool("sort_ascending", sort_ascending)

    if pin_search and not enable_search:
        raise ValueError("pin_search=True requires enable_search=True.")

    if selection_mode == "single" and select_all:
        raise ValueError('select_all=True not allowed for selection_mode="single"')

    if sort is not None and sort not in _SORT_MODES:
        raise ValueError(f"sort must be one of {_SORT_MODES!r} or None, got {sort!r}.")

    # collapsed_groups: None | "all" | list[str]. Validate the shape here so a
    # common mistake (passing a bare group name instead of a one-element list,
    # e.g. collapsed_groups="Germany") is rejected at the boundary rather than
    # forwarded to the frontend, where it would reach `collapsedGroups.filter`
    # and throw, crashing the whole widget at render time.
    if (
        collapsed_groups is not None
        and collapsed_groups != "all"
        and not (
            isinstance(collapsed_groups, list)
            and all(isinstance(name, str) for name in collapsed_groups)
        )
    ):
        raise ValueError(
            'collapsed_groups must be None, "all", or a list of group-name '
            f"strings, got {collapsed_groups!r}."
        )

    if format_func is not None and not callable(format_func):
        raise ValueError("format_func must be callable or None.")

    if on_change is not None and not callable(on_change):
        raise ValueError("on_change must be callable or None.")

    # args and kwargs reach on_change only when the user changes the selection,
    # so a wrong type would surface at the first click instead of here. The
    # accepted shapes are Streamlit's own (WidgetArgs, WidgetKwargs).
    if args is not None and not isinstance(args, (tuple, list)):
        raise ValueError(f"args must be a tuple, a list or None, got {args!r}.")
    if kwargs is not None and not (
        isinstance(kwargs, dict) and all(isinstance(name, str) for name in kwargs)
    ):
        raise ValueError(
            f"kwargs must be a dict with str keys or None, got {kwargs!r}."
        )


def _resolve_default_ids(  # noqa: C901 -- older than the complexity limit; split it when you next change it
    default: Any,
    selection_mode: str,
    id_to_original: dict[Any, Any],
    kind: NewOptionKind | None,
) -> list[Any]:
    """Resolve the `default` argument to a list of option ids.

    single: a scalar (non-list) default d -> [d] (or [] when None).
    multi:  a list default -> that list (or [] when None).
    Shape mismatches raise ValueError. Every id must pass the same boundary gate
    as an option id (``_validate_id``: str or int, bool rejected, ints
    within the JS safe range) — a default is seeded straight into the frontend
    selection, so it crosses the same JSON/``String(id)`` boundary. When
    ``kind`` is None (``accept_new_options`` off), every resolved id must
    additionally name a row of the options, membership judged by ``_id_key``
    rendered row identity. When ``kind`` is "int", an id naming no row must be
    a whole number — an int, or a str that ``_parse_new_int_id`` accepts —
    because it comes back as an int.
    """
    if selection_mode == "single":
        if isinstance(default, (list, tuple, set)):
            raise ValueError(
                'default must not be a list when selection_mode="single"; '
                f"got {default!r}."
            )
        default_ids: list[Any] = [] if default is None else [default]
    else:  # multi
        if default is None:
            default_ids = []
        elif isinstance(default, list):
            default_ids = list(default)
        else:
            raise ValueError(
                f'default must be a list when selection_mode="multi"; got {default!r}.'
            )

    # The unhashable check runs BEFORE the shared gate so the natural way to hit
    # it — round-tripping what listview() returned (default=OPTS[0], where
    # OPTS[0] is a dict option) — gets this targeted hint instead of the gate's
    # generic "must be a str or int". Then every id goes through the same
    # boundary gate as an option id, regardless of accept_new_options: an
    # unknown-but-unrepresentable id is not a "new option", it is an id the
    # JSON/String(id) boundary cannot carry (a bool desyncs the UI from the
    # value, a Decimal blanks the widget, 2**53 + 1 rounds — see _validate_id).
    for did in default_ids:
        try:
            hash(did)
        except TypeError as exc:
            raise ValueError(
                f"default id is unhashable: {did!r}. Pass the option's id, not "
                "the option itself — a dict option comes back whole in the "
                "selection, but only its 'id' can seed the default."
            ) from exc
        _validate_id(did, kind="default")

    # De-duplicate while preserving order, first occurrence winning: a repeated
    # default id is a single selection, so it must not inflate the max_selections
    # count (checked by the caller) nor seed a duplicate id into the frontend
    # selection.
    #
    # Keyed by _id_key — the rendered row identity — and NOT by Python equality,
    # which is a weaker notion of "the same row" than the frontend's: with
    # accept_new_options a default may name one row two ways (`["1", 1]`), and the
    # frontend renders and counts that as the one row it is. Keying by equality let
    # the pair through as two entries, so `max_selections=1` rejected a default
    # that selects a single row, and reconciliation had to collapse a duplicate the
    # producer should never have emitted. First-wins matches the survivor the
    # frontend keeps. The same collapse holds with accept_new_options off: the
    # membership check below judges by this same key, so a default spelling one
    # option's row two ways (`["1", 1]` against the int option 1) is a single
    # valid selection there too, not two entries.
    by_key: dict[str, Any] = {}
    for did in default_ids:
        by_key.setdefault(_id_key(did), did)
    default_ids = list(by_key.values())

    if default_ids:
        # Membership is a row-identity question, so it is asked by _id_key like
        # every other one: a default spelling a row differently than its option
        # ("1" for the int option 1) names a row the frontend renders, so it is
        # accepted — while raw Python ==, besides refusing that spelling, also
        # admitted ids that merely compare equal without rendering as any row
        # (Decimal('7') == 7 seeded an id the payload cannot even carry).
        # Gated on default_ids: option_by_key is a full pass over the options,
        # which the common default=None call must not pay on every rerun.
        option_by_key = {_id_key(item_id): item_id for item_id in id_to_original}
        if kind is None:
            for did in default_ids:
                if _id_key(did) not in option_by_key:
                    raise ValueError(
                        f"default id {did!r} is not present in options "
                        "(set accept_new_options=True to allow unknown defaults)."
                    )
        elif kind == "int":
            # With int options a new entry must be a whole number — the rule the
            # frontend's add field applies to typed text — because it comes back
            # as an int; an unknown "abc" would come back as a str instead. A
            # bool never gets here: _validate_id rejected it above.
            for did in default_ids:
                if _id_key(did) not in option_by_key and not (
                    isinstance(did, int) or _parse_new_int_id(did) is not None
                ):
                    raise ValueError(
                        f"default id {did!r} is not a whole number written "
                        "plainly. With int options, a new entry must be a whole "
                        "number such as 42 or -5: no leading zero, plus sign or "
                        "separator, and an absolute value of at most 2**53 - 1."
                    )
        # Ship each matched default in the OPTION's own spelling, not the
        # caller's. The seed is both the mount display and the V2 `default=`
        # state, and the frontend canonicalizes the selection to the option's
        # spelling on its first render — so a default that named the row
        # differently ("1" for the int option 1) was corrected by a write-back
        # that is indistinguishable from a click: an extra rerun and a spurious
        # on_change at mount, with no user action (and on EVERY remount of an
        # unkeyed instance). Canonicalizing here keeps the seed byte-equal to
        # what the frontend would commit, so mount stays quiet. An id with no
        # matching row (accept_new_options) is kept as given.
        default_ids = [option_by_key.get(_id_key(did), did) for did in default_ids]

    return default_ids


def _persisted_selection(key: str | None) -> list[Any] | None:
    """The selection persisted in ``st.session_state[key]``, or None.

    A keyed V2 component's element id drops the container, so moving the widget
    between ``st.sidebar`` and the main body keeps the Python-side widget state
    while the frontend remounts from scratch. The remounted frontend seeds from
    this value (shipped as ``data["state_selection"]``) when it is present,
    falling back to ``default_ids`` — without the channel, such a move re-seeded
    the rows from ``default`` while ``listview()`` kept returning the persisted
    selection, and the next click silently overwrote it.

    None means "nothing persisted; seed from default_ids": no ``key``, or a
    first run where the widget state does not exist yet (KeyError). An
    environment with no Streamlit runtime at all answers the same — the unit
    suite imports real streamlit without a script run context, where the read
    hits the bare-mode mock session state and raises KeyError too.

    Any other value must be a well-shaped state — a dict with a list under
    "selection" whose every element passes ``_validate_id`` — or this raises
    ValueError before the widget mounts. The key is user-writable, and an app
    that pre-seeds it (or assigns the selection from data) can put anything
    there: a Decimal, a date or a numpy int in the list, or no list at all. The
    component reads that value back as its state, so ``listview()`` would map
    it to a return value while the rows showed ``default``: ``[1.0]`` against
    the options "1.0" and "fallback" showed "fallback" and returned "1.0", on
    every rerun, with no error. Degrading to None therefore cannot keep the two
    in step, and neither can filtering out single elements.
    """
    if key is None:
        return None
    try:
        state = st.session_state[key]
    except KeyError:
        return None
    remedy = (
        f"st.session_state[{key!r}] must hold the state of a listview: a dict "
        "whose 'selection' is a list of str or int ids. Keep your own data "
        f"under another key, or delete this one (del st.session_state[{key!r}]) "
        "before the listview renders; pass default= to preselect rows."
    )
    selection = state.get("selection") if isinstance(state, dict) else None
    if not isinstance(selection, list):
        # reprlib: the value can be anything, a million-element list included.
        raise ValueError(f"{remedy} It holds {reprlib.repr(state)}.")
    try:
        for item_id in selection:
            _validate_id(
                item_id, kind="persisted", context=f" in st.session_state[{key!r}]"
            )
    except ValueError as exc:
        raise ValueError(f"{exc} {remedy}") from None
    # A copy: the V2 presenter hands out a live write-through view of the
    # widget state, and the payload must not alias it.
    return list(selection)


def listview(
    label: str,
    options: Iterable[Any] | None = None,
    *,
    selection_mode: Literal["single", "multi"] = "single",
    default: Any | list[Any] | None = None,
    format_func: Callable[[Any], str] | None = None,
    enable_search: bool = False,
    pin_search: bool = False,
    search_placeholder: str = "Search",
    collapsible_groups: bool = False,
    collapsed_groups: list[str] | Literal["all"] | None = None,
    ungrouped_label: str = "Other",
    sort: Literal["items", "groups", "both"] | None = None,
    sort_ascending: bool = True,
    accept_new_options: bool = False,
    max_selections: int | None = None,
    select_all: bool = False,
    placeholder: str | None = None,
    height: int = 300,
    item_height: int | None = None,
    content_font_size: int | None = None,
    width: Literal["stretch"] | int = "stretch",
    show_grid_lines: bool = True,
    help: str | None = None,
    disabled: bool = False,
    label_visibility: Literal["visible", "hidden", "collapsed"] = "visible",
    on_change: Callable[..., None] | None = None,
    args: tuple[Any, ...] | list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    key: str | None = None,
) -> dict[str, Any] | str | int | list[Any] | None:
    """Display a listview widget.

    The listview shows the options as the rows of a scrollable list, which can
    group them under headers. The user selects one row or several, depending on
    ``selection_mode``.

    Parameters
    ----------
    label : str
        A short label that tells the user what the list is for. The label can
        contain GitHub-flavored Markdown of these inline types: bold, italics,
        strikethrough, inline code, links and images. It also renders
        Streamlit's colored text (``:red[...]``), background colors
        (``:red-background[...]``), badges (``:red-badge[...]``),
        ``:small[...]``, Material icons (``:material/thumb_up:``) and emoji
        shortcodes. Headings, lists and blockquotes display as literal text.
        LaTeX and the ``rainbow`` and ``primary`` colors display as literal text
        too, and raw HTML stays escaped.

        For accessibility, never set an empty label; hide it with
        ``label_visibility`` instead.

    options : Iterable of str, int, or dict, or None
        The options to list, in order. Each option is one of the following:

        - A ``str`` or an ``int``: the value is both the id and the label.
        - A dict with the key ``"id"`` and these optional keys:

          - ``"label"``: the text of the row. If the key is missing, ``None``
            or NaN, ``format_func`` supplies the label.
          - ``"group"``: a ``str``. Options with the same group render under
            one header.
          - ``"disabled"``: a ``bool``. The row of a disabled option shows but
            takes no selection.

          Other keys, such as a payload of your own, never render and come
          back with the option in the selection.

        An id is a ``str`` or an ``int``, an enum member of either included;
        ``bool``, ``float`` and other types raise ``ValueError``. An ``int`` id
        must satisfy ``abs(id) <= 2**53 - 1``; pass larger keys as strings. Ids
        must be unique as rendered: ``1`` and ``"1"`` collide. Labels and group
        names display as plain text, not Markdown.

        Pass a list or another iterable; a bare ``str`` or ``dict`` raises
        ``ValueError``. If this is ``None`` (default) or empty, the list has no
        rows (see ``placeholder``).

    selection_mode : "single" or "multi"
        How many options the user can select. If this is ``"single"``
        (default), a click on a row selects it in place of the earlier
        selection, and a click on the selected row clears it. If this is
        ``"multi"``, each click adds or removes one row.

    default : str, int, list of str or int, or None
        The ids of the options selected at mount: one id in single mode, a list
        of ids in multi mode. Pass an option's id, not the dict option. Each id
        must name an option, unless ``accept_new_options=True``. If this is
        ``None`` (default), the widget starts with no selection.

        The widget applies ``default`` once, at mount, and calls no
        ``on_change`` for it. On a keyed widget, a new ``default`` only scrolls
        its row into view; change ``key`` to apply it. Every call still checks
        ``default`` against ``options``, ``selection_mode`` and
        ``max_selections``.

    format_func : callable or None
        A function that returns the label of an option. It receives the option
        as passed (the dict, or the ``str`` or ``int`` itself), so it can build
        the label from any key of a dict option. The widget calls it only for
        an option without a usable ``"label"``; an explicit label wins. A
        ``"label"`` of ``None`` or NaN, as ``df.to_dict("records")`` yields for
        a NULL cell, reaches the function too. If this is ``None`` (default),
        the label is ``str(id)``. Avoid ``str``: it would show the repr of a
        dict option.

        The function has no effect on the return value. It receives your own
        object, not a copy, so treat the option as read-only. If it raises,
        ``listview()`` raises ``ValueError`` and names the option.

    enable_search : bool
        Whether a search field filters the rows. The list keeps the rows whose
        label contains the search text, ignoring case. The ``/`` key moves the
        focus to the field. The default is ``False``.

    pin_search : bool
        Whether the search field stays in view while the list scrolls. It
        requires ``enable_search=True``. The default is ``False``.

    search_placeholder : str
        The text of the empty search field. The default is ``"Search"``.

    collapsible_groups : bool
        Whether a click on a group header, or the right and left arrow keys,
        opens and closes the group. The default is ``False``.

    collapsed_groups : list of str, "all", or None
        The groups that start collapsed while ``collapsible_groups=True``: a
        list of group names, or ``"all"``. A name equal to ``ungrouped_label``
        collapses the options without a group. If this is ``None`` (default),
        every group starts open.

        The widget applies this value to each group once, when the group first
        appears; from then on the user opens and closes it. With ``"all"``, a
        group that first appears after mount starts collapsed too. Change
        ``key`` to apply a new value to the groups already shown.

    ungrouped_label : str
        The header of the options without a group. The header shows once any
        option has a ``"group"``. The options without a group then render
        last, below every group, followed by the entries added through
        ``accept_new_options``. The options of a group with this name share the
        block. The default is ``"Other"``.

    sort : "items", "groups", "both", or None
        How the list orders its rows, by label and group name, ignoring case:

        - ``None`` (default): the order of ``options``. Each group appears
          where its first option stands and holds its options in their order.
        - ``"items"``: sort the options within each group.
        - ``"groups"``: sort the groups.
        - ``"both"``: sort the groups and the options within each group.

        The options without a group render last in every case, and added
        entries follow them unsorted.

    sort_ascending : bool
        Whether ``sort`` orders the rows from A to Z (``True``, default) or from
        Z to A (``False``). It has no effect while ``sort`` is ``None``.

    accept_new_options : bool
        Whether the user can add an entry that is not in ``options``. If this
        is ``True``, an input field below the list takes the new entry. If this
        is ``False`` (default), the user selects only from ``options``.

        Text that names a row selects that row: its id written as text, its
        label ignoring case, or its id ignoring case, in this order. Other text
        becomes a new entry, which comes back in the type of the other options:

        - All options are dicts: ``{"id": text, "label": text}``.
        - All options are ``int``: an ``int``. The field then accepts only a
          whole number, such as ``42`` or ``-5``.
        - All options are ``str``, mixed, or absent: the text as a ``str``.

        An unknown ``default`` follows the same rule; with ``int`` options, it
        must be a whole number. The entry stays a row of the widget while the
        widget keeps its state; ``listview()`` never adds it to ``options``.
        ``max_selections`` still applies.

    max_selections : int or None
        The most options the user can select at a time in multi mode. If this
        is ``None`` (default), the selection has no limit. At the limit, the
        unselected rows are muted until the user deselects one. Single mode
        accepts only ``None`` or ``1``. A ``default`` with more ids raises
        ``ValueError``.

    select_all : bool
        Whether multi mode shows a "Select all" toggle above the list. It
        selects the rows that match the search, rows of collapsed groups
        included and disabled rows excluded, from the top down until
        ``max_selections`` is reached. Once those rows are selected or the
        limit is reached, it reads "Deselect all" and clears them. Single mode
        raises ``ValueError`` for ``True``. The default is ``False``.

    placeholder : str or None
        The text shown in place of the rows while the list has none. Without
        options and with ``accept_new_options=False``, the widget is disabled,
        and ``None`` (default) shows "No options to select". In every other
        case, ``None`` shows an empty list.

    height : int
        The height of the scrolling list in pixels, at least ``100``. A pinned
        search field, the "Select all" toggle and the input field of
        ``accept_new_options`` add their own height. The default is ``300``.

    item_height : int or None
        The minimum height of a row in pixels, at least ``1``. A row grows to
        fit its content, so a label never clips, and a value below the row's
        natural height has no effect. Use it to make rows taller, such as for
        touch targets. If this is ``None`` (default), each row takes the height
        of its content.

    content_font_size : int or None
        The font size of the rows and group headers in pixels, at least ``1``.
        A smaller font lowers the natural height of each row, which makes the
        list more compact; ``item_height`` still sets the minimum. The label,
        the search field, the input field and the placeholder keep the theme's
        size. If this is ``None`` (default), the rows take 0.875 times the
        theme's base font size.

    width : "stretch" or int
        The width of the widget. This can be one of the following:

        - ``"stretch"`` (default): the width of the parent container.
        - An ``int``: a fixed width in pixels, at least ``1``.

    show_grid_lines : bool
        Whether lines divide the rows. Set it to ``False`` for a compact list;
        group headers keep their own separator. The default is ``True``.

    help : str or None
        A tooltip next to the label. It shows only while
        ``label_visibility="visible"``. If this is ``None`` (default), no
        tooltip shows. The tooltip renders GitHub-flavored Markdown, headings,
        lists, tables and code blocks included, with the extras that ``label``
        lists.

    disabled : bool
        Whether the whole widget is disabled. The default is ``False``. Without
        options and with ``accept_new_options=False``, the widget is always
        disabled.

    label_visibility : "visible", "hidden", or "collapsed"
        The visibility of the label. If this is ``"visible"`` (default), the
        label shows above the list. If this is ``"hidden"``, an empty spacer
        takes the label's place and keeps the widget aligned with others. If
        this is ``"collapsed"``, neither label nor spacer shows.

    on_change : callable or None
        A function to call when the selection changes. Streamlit calls it as
        ``on_change(*args, **kwargs)`` at the start of the rerun that the change
        triggers, before the rest of the script. If this is ``None`` (default),
        the change only reruns the app.

        It also runs once when the widget corrects a keyed selection that no
        longer fits a change of ``options``, ``max_selections`` or
        ``selection_mode``. That call comes one rerun after the change. The
        README shows how to tell such a correction from user input.

    args : list, tuple, or None
        The positional arguments for ``on_change``.

    kwargs : dict or None
        The keyword arguments for ``on_change``, with ``str`` keys.

    key : str or None
        A unique key for the widget; no two widgets may share one. Set it in
        any app that changes the parameters between runs. With a key, the
        selection and the state of the list (open groups, search text, scroll
        position) survive a change of the other parameters. Without one, any
        parameter change remounts the widget and resets both. Change the key
        to reset the widget on purpose.

        ``st.session_state[key]`` holds the widget's state: a dict whose
        ``"selection"`` lists the selected ids. Keep data of your own under
        another key; any other value under this one raises ``ValueError``. If a
        run of the script does not call ``listview()`` for the key, Streamlit
        deletes the state, and the next call starts again from ``default``.

    Returns
    -------
    any, list, or None
        In single mode, the selected option, or ``None`` if nothing is
        selected. In multi mode, a list of the selected options in the order
        the user selected them, or ``[]``.

        Each option comes back as you passed it: the dict, or the ``str`` or
        ``int`` itself. It is the object from ``options``, not a copy. A new
        entry comes back as ``accept_new_options`` describes.

    Raises
    ------
    ValueError
        If an argument is invalid, a wrong type included; if ``format_func``
        raises for an option; or if ``st.session_state[key]`` holds a value
        that is not the state of a listview.

    Examples
    --------
    **Example 1: Select one option**

    >>> import streamlit as st
    >>> from streamlit_listview import listview
    >>>
    >>> fruit = listview(
    ...     "Pick a fruit",
    ...     ["Apple", "Banana", "Cherry"],
    ...     key="fruit",
    ... )
    >>>
    >>> st.write("You picked:", fruit)

    **Example 2: Select several options in groups**

    Dict options carry a group, and a disabled option shows but takes no
    selection. ``max_selections`` limits the selection, and ``enable_search``
    adds a search field.

    >>> import streamlit as st
    >>> from streamlit_listview import listview
    >>>
    >>> ingredients = listview(
    ...     "Pick ingredients",
    ...     [
    ...         {"id": "apple", "label": "Apple", "group": "Fruit"},
    ...         {"id": "carrot", "label": "Carrot", "group": "Vegetable"},
    ...         {"id": "salmon", "label": "Salmon", "group": "Fish", "disabled": True},
    ...     ],
    ...     selection_mode="multi",
    ...     default=["apple"],
    ...     max_selections=2,
    ...     enable_search=True,
    ...     collapsible_groups=True,
    ...     key="ingredients",
    ... )
    >>>
    >>> st.write("You picked:", ingredients)

    **Example 3: Build the labels from the options**

    ``format_func`` receives the whole option, so the label can use keys that
    the widget never renders.

    >>> import streamlit as st
    >>> from streamlit_listview import listview
    >>>
    >>> table = listview(
    ...     "Pick a table",
    ...     [
    ...         {"id": 1, "name": "Orders", "rows": 1200},
    ...         {"id": 2, "name": "Customers", "rows": 85},
    ...     ],
    ...     format_func=lambda option: f"{option['name']} ({option['rows']} rows)",
    ...     key="table",
    ... )
    >>>
    >>> st.write("You picked:", table)

    **Example 4: Let users add new options**

    With ``accept_new_options=True``, the user can type an entry that is not in
    ``options``. With ``str`` options, the entry comes back as a ``str``.

    >>> import streamlit as st
    >>> from streamlit_listview import listview
    >>>
    >>> tags = listview(
    ...     "Tags",
    ...     ["bug", "docs", "feature"],
    ...     selection_mode="multi",
    ...     accept_new_options=True,
    ...     key="tags",
    ... )
    >>>
    >>> st.write("Your tags:", tags)

    The hosted demo at https://st-listview-demo.streamlit.app/ shows every
    parameter as a live control.
    """
    _validate_params(
        label=label,
        help=help,
        placeholder=placeholder,
        search_placeholder=search_placeholder,
        ungrouped_label=ungrouped_label,
        selection_mode=selection_mode,
        label_visibility=label_visibility,
        width=width,
        height=height,
        item_height=item_height,
        content_font_size=content_font_size,
        max_selections=max_selections,
        enable_search=enable_search,
        pin_search=pin_search,
        collapsible_groups=collapsible_groups,
        accept_new_options=accept_new_options,
        show_grid_lines=show_grid_lines,
        disabled=disabled,
        format_func=format_func,
        on_change=on_change,
        args=args,
        kwargs=kwargs,
        select_all=select_all,
        sort=sort,
        sort_ascending=sort_ascending,
        collapsed_groups=collapsed_groups,
    )

    items, id_to_original = normalize_options(options, format_func)
    items = sort_items(items, sort, sort_ascending, ungrouped_label)

    # The type a new entry comes back as (see new_option_kind). None when adding
    # is off, so the common call skips the pass over the options.
    kind = new_option_kind(id_to_original) if accept_new_options else None

    # No options and no way to add any -> nothing is selectable: default the
    # placeholder prompt to "No options to select" and disable the widget
    # (matching st.multiselect). An explicit placeholder is kept as-is.
    if not items and not accept_new_options:
        disabled = True
        if placeholder is None:
            placeholder = "No options to select"

    default_ids = _resolve_default_ids(default, selection_mode, id_to_original, kind)

    if (
        selection_mode == "multi"
        and max_selections is not None
        and len(default_ids) > max_selections
    ):
        raise ValueError(
            f"default has {len(default_ids)} options but max_selections is "
            f"{max_selections}; reduce the default or raise max_selections."
        )

    data = {
        "label": label,
        "help": help,
        "items": items,
        "selection_mode": selection_mode,
        "default_ids": default_ids,
        "state_selection": _persisted_selection(key),
        "enable_search": enable_search,
        "pin_search": pin_search,
        "search_placeholder": search_placeholder,
        "collapsible_groups": collapsible_groups,
        "collapsed_groups": collapsed_groups,
        "ungrouped_label": ungrouped_label,
        "accept_new_options": accept_new_options,
        "new_option_kind": kind,
        "max_selections": max_selections,
        "placeholder": placeholder,
        "height": height,
        "item_height": item_height,
        "content_font_size": content_font_size,
        "width": width,
        "show_grid_lines": show_grid_lines,
        "select_all": select_all,
        "disabled": disabled,
        "label_visibility": label_visibility,
    }

    if on_change is None:
        on_selection_change = lambda: None
    else:
        cb_args = () if args is None else args
        cb_kwargs = {} if kwargs is None else kwargs

        def on_selection_change() -> None:
            on_change(*cb_args, **cb_kwargs)

    result = _get_component()(
        data=data,
        default={"selection": default_ids},
        on_selection_change=on_selection_change,
        key=key,
    )

    selected_ids = result.get("selection")
    if not isinstance(selected_ids, list):
        # Guard against a tampered/buggy frontend returning a non-list (the V2
        # state is typed Id[] in TypeScript, but that is not a runtime
        # guarantee). Treat anything that is not a list as "no selection"
        # rather than iterating it — a returned string would otherwise be
        # split into per-character ids.
        selected_ids = []
    return map_selection(
        selected_ids,
        id_to_original,
        selection_mode,
        kind=kind,
        max_selections=max_selections,
    )
