from __future__ import annotations

from typing import Any, Callable, Iterable, Literal

import streamlit as st

from ._options import (
    _id_key,
    _validate_id,
    map_selection,
    normalize_options,
    sort_items,
)

_component = st.components.v2.component(
    "streamlit_listview.listview",
    js="index-*.js",
    css="index-*.css",
    html='<div class="listview-root"></div>',
)

_SELECTION_MODES = ("single", "multi")
_LABEL_VISIBILITIES = ("visible", "hidden", "collapsed")
_SORT_MODES = ("items", "groups", "both")


def _is_real_int(value: Any) -> bool:
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


def _validate_params(
    *,
    label: Any,
    help: Any,
    placeholder: Any,
    search_placeholder: Any,
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
    select_all: Any,
    sort: Any,
    sort_ascending: Any,
    collapsed_groups: Any,
) -> None:
    """Validate scalar parameters per spec §7. Raises ValueError."""
    # The four text params are handed to the frontend verbatim — `label` and
    # `help` as Markdown source, the two placeholders as <input>/empty-state text.
    # A non-str `label` reaches escapeLabelSource, which calls .replace() on it and
    # throws during React render; like the collapsed_groups shape below, that
    # crashes the whole widget with nothing to show for it on the Python side (no
    # traceback, just an empty component). So the type is checked here.
    #
    # None-ness deliberately mirrors the signature defaults *and* the frontend's
    # ListviewData contract: `label: string` and `search_placeholder: string` are
    # non-nullable there, while `help: string | null` and
    # `placeholder: string | null` use null to mean "not shown". Only wrong types
    # are rejected; which params accept None is unchanged.
    _validate_str("label", label, allow_none=False)
    _validate_str("help", help, allow_none=True)
    _validate_str("placeholder", placeholder, allow_none=True)
    _validate_str("search_placeholder", search_placeholder, allow_none=False)

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
        raise ValueError(
            f'width must be "stretch" or an int >= 1, got {width!r}.'
        )

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
        raise ValueError(
            f"sort must be one of {_SORT_MODES!r} or None, got {sort!r}."
        )

    # collapsed_groups: None | "all" | list[str]. Validate the shape here so a
    # common mistake (passing a bare group name instead of a one-element list,
    # e.g. collapsed_groups="Germany") is rejected at the boundary rather than
    # forwarded to the frontend, where it would reach `collapsedGroups.filter`
    # and throw, crashing the whole widget at render time.
    if collapsed_groups is not None and collapsed_groups != "all":
        if not (
            isinstance(collapsed_groups, list)
            and all(isinstance(name, str) for name in collapsed_groups)
        ):
            raise ValueError(
                'collapsed_groups must be None, "all", or a list of group-name '
                f"strings, got {collapsed_groups!r}."
            )

    if format_func is not None and not callable(format_func):
        raise ValueError("format_func must be callable or None.")

    if on_change is not None and not callable(on_change):
        raise ValueError("on_change must be callable or None.")


def _resolve_default_ids(
    default: Any,
    selection_mode: str,
    id_to_original: dict[Any, Any],
    accept_new_options: bool,
) -> list[Any]:
    """Resolve the `default` argument to a list of option ids.

    single: a scalar (non-list) default d -> [d] (or [] when None).
    multi:  a list default -> that list (or [] when None).
    Shape mismatches raise ValueError. Every id must pass the same boundary gate
    as an option id (``_validate_id``: exactly str or int, bool rejected, ints
    within the JS safe range) — a default is seeded straight into the frontend
    selection, so it crosses the same JSON/``String(id)`` boundary. When
    accept_new_options is False, every resolved id must additionally name a row
    of the options, membership judged by ``_id_key`` rendered row identity.
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
                'default must be a list when selection_mode="multi"; '
                f"got {default!r}."
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
        if not accept_new_options:
            for did in default_ids:
                if _id_key(did) not in option_by_key:
                    raise ValueError(
                        f"default id {did!r} is not present in options "
                        "(set accept_new_options=True to allow unknown defaults)."
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


def _persisted_selection(key: str | None) -> list | None:
    """The selection persisted in ``st.session_state[key]``, or None.

    A keyed V2 component's element id drops the container, so moving the widget
    between ``st.sidebar`` and the main body keeps the Python-side widget state
    while the frontend remounts from scratch. The remounted frontend seeds from
    this value (shipped as ``data["state_selection"]``) when it is present,
    falling back to ``default_ids`` — without the channel, such a move re-seeded
    the rows from ``default`` while ``listview()`` kept returning the persisted
    selection, and the next click silently overwrote it.

    Best-effort by design: anything short of a well-shaped state degrades to
    None ("nothing persisted; seed from default_ids"). That covers no ``key``,
    a first run where the widget state does not exist yet (KeyError), and an
    environment with no Streamlit runtime at all — the unit suite imports real
    streamlit without a script run context, where the read hits the bare-mode
    mock session state and raises KeyError too. The shape check (a dict with a
    list under "selection" whose every element passes ``_validate_id``) guards
    against a caller having overwritten the key with arbitrary user state — the
    key is user-writable, and an app that pre-seeds it (or assigns the selection
    from data) can put a Decimal, a date or a numpy int in the list. Those ids
    cross the same JSON/``String(id)`` boundary as an option id, and an
    unrepresentable one blanks the widget with no Python error (see
    ``_validate_id``), so the list is trusted whole or not at all: filtering
    single elements would be a fourth way for the rendered rows to disagree
    with the returned value.
    """
    if key is None:
        return None
    try:
        state = st.session_state[key]
    except Exception:
        # A missing key raises KeyError; session-state access can also raise
        # StreamlitAPIException for keys it refuses to serve. Every failure
        # means the same thing here: nothing persisted.
        return None
    if not isinstance(state, dict):
        return None
    selection = state.get("selection")
    if not isinstance(selection, list):
        return None
    try:
        for item_id in selection:
            _validate_id(item_id, kind="persisted")
    except ValueError:
        return None
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
    args: tuple | None = None,
    kwargs: dict | None = None,
    key: str | None = None,
) -> dict | str | int | list | None:
    """Display a scrollable, selectable listview widget.

    See the design spec for full behavior. `key` is strongly recommended for
    any dynamic app so that frontend-local UI state and the selection survive
    parameter changes (an unkeyed instance is remounted and reset).

    `item_height` is a *minimum* row height in pixels (CSS ``min-height``), not a
    fixed height: a row always grows to fit its content, so labels are never
    clipped at any value. ``None`` (the default) lets each row size to its
    content. Because it is only a floor, values below a row's natural one-line
    height have no visible effect — the content height wins — so it is mainly
    useful to make rows *taller* (e.g. roomier touch targets). The natural floor
    is computed by the browser at layout time and tracks the active theme's font
    size, which is why no fixed minimum is enforced here beyond ``>= 1``.

    ``content_font_size`` sets the font size (px) of the list *content* — the
    option rows and the group headers — which in turn lowers each row's natural
    height for a more compact list. ``None`` (the default) keeps the theme size
    (``base × 0.875``, theme-tracked). It does **not** change the widget label,
    search box, add-option input, or placeholder (those stay at the native
    theme size), and it composes with ``item_height``: the font sets the natural
    height, while ``item_height`` remains a floor that wins when larger.

    ``show_grid_lines`` (default ``True``) draws divider lines between option
    rows; set it ``False`` for a more compact, line-free list (group headers
    keep their own separator).

    ``format_func`` maps an option to its display label and receives **the option
    as passed** — the dict for dict options, the scalar itself for ``str``/``int``
    options — so a label can be built from fields the option carries (e.g.
    ``lambda o: f"{o['text']} ({o['type']})"``). It is consulted only for options
    without a *usable* ``label``; an explicit one wins outright. Mind that
    ``{"label": None}`` and ``{"label": nan}`` count as unusable and do reach the
    formatter — that is the ``df.to_dict("records")`` NULL-cell shape. ``None``
    (the default) means no formatter: the label is ``str(id)``. The option handed
    over is your own object, not a copy; treat it as read-only.
    """
    _validate_params(
        label=label,
        help=help,
        placeholder=placeholder,
        search_placeholder=search_placeholder,
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
        select_all=select_all,
        sort=sort,
        sort_ascending=sort_ascending,
        collapsed_groups=collapsed_groups,
    )

    items, id_to_original = normalize_options(options, format_func)
    items = sort_items(items, sort, sort_ascending)

    # No options and no way to add any -> nothing is selectable: default the
    # placeholder prompt to "No options to select" and disable the widget
    # (matching st.multiselect). An explicit placeholder is kept as-is.
    if not items and not accept_new_options:
        disabled = True
        if placeholder is None:
            placeholder = "No options to select"

    default_ids = _resolve_default_ids(
        default, selection_mode, id_to_original, accept_new_options
    )

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
        "accept_new_options": accept_new_options,
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
        on_selection_change = lambda: None  # noqa: E731
    else:
        cb_args = args or ()
        cb_kwargs = kwargs or {}

        def on_selection_change() -> None:
            on_change(*cb_args, **cb_kwargs)

    result = _component(
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
        accept_new_options,
        max_selections,
    )
