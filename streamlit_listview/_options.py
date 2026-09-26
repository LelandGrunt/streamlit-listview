from collections.abc import Mapping
from typing import Any, Callable, Iterable

# JavaScript's Number.MAX_SAFE_INTEGER. The payload crosses a JSON boundary, so
# every number arrives on the frontend as an IEEE-754 double; ints beyond this
# magnitude are silently rounded (see the guard in normalize_options).
MAX_SAFE_JS_INT = 2**53 - 1


def _id_key(item_id: Any) -> str:
    """The row-identity key for an option id — the Python mirror of ``idKey``.

    The frontend keys every row (React key, DOM id, "is this the same row?"
    comparison) by JavaScript ``String(id)``, so anything Python asks about row
    identity has to ask it the same way. ``str()`` agrees with ``String()`` for
    exactly the ids the boundary admits — ``str`` and ``int`` within
    ``MAX_SAFE_JS_INT``, which ``normalize_options`` enforces — which is what makes
    this a faithful mirror rather than a coincidence.

    One definition, so the collision guard below, the ``default`` membership and
    de-duplication in ``_resolve_default_ids``, and the way-out resolution in
    ``map_selection`` cannot disagree about when two ids are one row.
    """
    return str(item_id)


def _validate_id(item_id: Any, *, kind: str, context: str = "") -> None:
    """Reject an id the JSON / ``String(id)`` boundary cannot carry faithfully.

    THE per-id gate, shared by ``normalize_options`` (option ids),
    ``_resolve_default_ids`` (default ids) and ``_persisted_selection`` (the ids
    read back from ``st.session_state[key]``): a default or persisted id is
    seeded straight into the frontend selection, so it crosses the same boundary
    as an option id and every rule below applies to it for exactly the same
    reasons. ``kind`` names the id's role in the message ("option" / "default" /
    "persisted"); ``context`` is appended verbatim after the offending value
    (e.g. ``" (from option ...)"``).

    Ids are restricted to exactly str or int, positively. The frontend
    identifies rows by JavaScript ``String(id)``, which diverges from Python
    ``str()`` for every other type, so anything else renders ambiguously or does
    not survive the JSON round-trip:
      * float — str(1.0) == '1.0' but String(1.0) === '1', so a float 1.0 and an
        int 1 / str '1' collapse to one row yet spell their row differently on
        the two sides; non-finite floats (NaN/Infinity) also break the selection
        round-trip and serialize to non-standard JSON.
      * bool — str(True) == 'True' but String(true) === 'true', the same
        as-rendered divergence (and True == 1, so raw equality tests confuse it
        with an int id).
      * None — str(None) == 'None' vs String(null) === 'null'.
      * anything else (date, Decimal, UUID, ...) is not JSON-serializable, and
        Streamlit's serializer swallows that TypeError and ships
        json.dumps(str(data)) instead, so the frontend gets a string where it
        expects the payload object and the widget renders BLANK with no
        Python-side error at all.
    bool is an int subclass, hence the explicit isinstance(..., bool) arm.

    Ints also have an upper bound: the frontend receives them as IEEE-754
    doubles, so anything past Number.MAX_SAFE_INTEGER is rounded. That is not
    academic — a BIGINT primary key or a snowflake id (spacing 256 near 1.2e18)
    rounds two neighbouring ids onto the same JS Number, which both renders them
    as one row and makes the id coming back from the frontend a value that no
    longer exists in id_to_original, so the selection is dropped on every rerun
    while the row still looks selected.
    """
    if isinstance(item_id, bool) or not isinstance(item_id, (str, int)):
        raise ValueError(
            f"{kind} id must be a str or int, not {type(item_id).__name__}: "
            f"{item_id!r}{context}. The frontend renders rows by JavaScript "
            "String(id), which diverges from Python str() for other types, and "
            "a non-str/int id may not even be JSON-serializable — so such an id "
            "would render ambiguously, break the selection round-trip, or blank "
            "the widget entirely."
        )

    if isinstance(item_id, int) and abs(item_id) > MAX_SAFE_JS_INT:
        raise ValueError(
            f"{kind} id {item_id!r} exceeds JavaScript's safe integer range "
            f"(abs(id) must be <= {MAX_SAFE_JS_INT}). Ids cross a JSON "
            "boundary and become IEEE-754 doubles on the frontend, which "
            "cannot represent this int exactly, so it would render "
            "ambiguously and never map back to its option. Use the string "
            f'form instead: "{item_id}".'
        )


def _is_usable_label(value: Any) -> bool:
    """True when a dict option's ``label`` can serve as display text.

    ``None`` and NaN mean "no label", not the literal text "None"/"nan": both are
    what ``df.to_dict("records")`` produces for a NULL label cell (pandas yields
    ``None`` for string dtype and ``nan`` for object dtype), and neither is
    something the caller asked to see. NaN is recognised by its self-inequality so
    this package stays dependency-free (no pandas/numpy import).
    """
    return value is not None and not (isinstance(value, float) and value != value)


def _label_for(
    option: Any, item_id: Any, format_func: Callable[[Any], str] | None
) -> str:
    """Compute an option's display label.

    A dict option's explicit ``label`` wins outright. ``format_func`` supplies the
    label for scalar options and for dict options whose ``label`` is absent or
    unusable, and it receives **the option as passed** — the dict for dict
    options, the scalar itself for ``str``/``int`` options — so a formatter can
    build the label out of fields the option carries and the id alone cannot
    reach. ``format_func=None`` means "no formatter": the label is ``str(id)``.

    Note which options actually reach the formatter: ``{"label": None}`` and
    ``{"label": nan}`` *carry* a ``label`` key and still route here, because
    ``_is_usable_label`` rejects them — that is the ``df.to_dict("records")``
    NULL-cell shape, so a formatter must handle it.

    A failure is re-raised as a friendly ValueError naming the offending option.
    """
    # EVERY arm is guarded. A ValueError naming the offending option is this
    # module's contract for a bad option, and __str__ can raise on any of the
    # three things that can produce a label — an explicit label, a format_func
    # result, or the id itself — so none of them may sit outside a guard.
    if isinstance(option, dict) and _is_usable_label(option.get("label")):
        try:
            return str(option["label"])
        except Exception as exc:
            raise ValueError(
                f"str(label) failed for option {option!r}: {exc}"
            ) from exc
    # str(item_id), not _id_key(item_id): this is the DISPLAY label, not row
    # identity. They spell the same today; routing it through _id_key would
    # freeze the default label to the row-key spelling forever.
    try:
        return str(item_id if format_func is None else format_func(option))
    except Exception as exc:
        source = "str(id)" if format_func is None else "format_func"
        raise ValueError(
            f"{source} failed for option {option!r}: {exc}"
        ) from exc


def normalize_options(
    options: Iterable[Any] | None,
    format_func: Callable[[Any], str] | None,
) -> tuple[list[dict[str, Any]], dict[Any, Any]]:
    if options is None:
        return [], {}

    # A str, bytes or mapping IS iterable, so iter() below would not object — but
    # none of them is a collection of options: a str splits into one-character
    # rows, bytes into int rows (97, 98, ... — which even pass _validate_id) and a
    # dict into its keys, silently dropping the single option the caller meant to
    # pass. The same rule the returned selection and the persisted state already
    # apply ("a str would be iterated per character downstream"); reject it at
    # the boundary instead of rendering a wrong widget with no error.
    if isinstance(options, (str, bytes, bytearray, Mapping)):
        raise ValueError(
            "options must be None or an iterable of options (str/int values or "
            f"dicts), not a bare {type(options).__name__}: {options!r}. Wrap a "
            "single option in a list."
        )

    try:
        iterator = iter(options)
    except TypeError as exc:
        raise ValueError(
            f"options must be iterable or None, got {type(options).__name__}"
        ) from exc

    items: list[dict[str, Any]] = []
    id_to_original: dict[Any, Any] = {}
    # Track str(id) too: the frontend identifies rows by String(id) (React keys,
    # DOM ids, the jump-to-default scroll selector, aria-activedescendant), so two
    # ids that collapse to the same string (e.g. 1 and "1") would render as
    # indistinguishable rows. Reject that at the boundary instead of shipping
    # ambiguous data the frontend cannot disambiguate.
    seen_str_ids: set[str] = set()

    for option in iterator:
        if isinstance(option, dict):
            if "id" not in option:
                raise ValueError(f"dict option missing 'id': {option!r}")
            item_id = option["id"]
            label = _label_for(option, item_id, format_func)

            item: dict[str, Any] = {"id": item_id, "label": label}
            if "group" in option:
                group = option["group"]
                if not isinstance(group, str):
                    raise ValueError(
                        f"'group' must be a str, got {type(group).__name__} "
                        f"in option {option!r}"
                    )
                item["group"] = group
            if "disabled" in option:
                disabled = option["disabled"]
                if not isinstance(disabled, bool):
                    raise ValueError(
                        f"'disabled' must be a bool, got {type(disabled).__name__} "
                        f"in option {option!r}"
                    )
                item["disabled"] = disabled
        else:
            item_id = option
            label = _label_for(option, item_id, format_func)
            item = {"id": item_id, "label": label}

        try:
            hash(item_id)
        except TypeError as exc:
            raise ValueError(
                f"option id is unhashable: {item_id!r} "
                f"(from option {option!r})"
            ) from exc

        # The per-id boundary gate (exactly str/int, bool rejected, |int| within
        # the JS safe range) — shared with _resolve_default_ids; _validate_id's
        # docstring carries the reasons for each rule.
        _validate_id(item_id, kind="option", context=f" (from option {option!r})")

        if item_id in id_to_original:
            raise ValueError(f"duplicate option id: {item_id!r}")

        str_id = _id_key(item_id)
        if str_id in seen_str_ids:
            raise ValueError(
                f"option id {item_id!r} collides with another option after "
                f"string conversion (str(id) == {str_id!r}); option ids must be "
                "unique as rendered."
            )
        seen_str_ids.add(str_id)

        items.append(item)
        id_to_original[item_id] = option

    return items, id_to_original


def map_selection(
    selected_ids: list[Any],
    id_to_original: dict[Any, Any],
    selection_mode: str,
    accept_new_options: bool,
    max_selections: int | None = None,
) -> Any:
    """Turn the ids the frontend returned into the value ``listview()`` returns.

    Ids are resolved by rendered row identity (``_id_key``), not by raw Python
    equality: the frontend keys rows by ``String(id)``, so a selected id that
    spells an option's row differently — a typed ``"7"`` against the int option
    ``7``, or a stored selection surviving a dtype flip of the options column —
    maps back to that option object immediately, on the same rerun. An id
    matching no row becomes its string form when ``accept_new_options`` is on
    and is dropped otherwise. Duplicate row keys collapse to one entry (earliest
    survivor) *before* any truncation, mirroring the frontend's
    ``reconcileSelection``, so a duplicate never consumes a cap slot. single
    mode returns the first survivor (or None), multi mode the list in selection
    order.

    ``max_selections`` caps the multi-mode list. This is a *defensive* clamp, not
    the primary enforcement: the cap is enforced on the frontend, which clamps an
    over-cap selection and commits the correction. But that commit only arrives on
    the *next* rerun, so on the very rerun that lowers ``max_selections`` the state
    read here is still the un-reconciled one — and without this, ``listview()``
    would hand back more options than the caller allows, even though the identical
    condition is a hard ValueError on the way in via ``default=``. Keeping the
    first N agrees with the frontend, which keeps the earliest-selected survivors
    when it clamps, so the two can never disagree about *which* ids survive. It
    truncates rather than raising: a keyed widget carrying selection state made
    against a looser cap is not the app author's error, and an exception would take
    down a running app for a condition the frontend is already converging on.
    """
    # Row identity -> the original option, the Python mirror of the frontend's
    # itemIdByKey map. Collision-free by construction: normalize_options rejects
    # two option ids that collapse to one rendered key. Built only when there is
    # a selection to resolve: the nothing-selected rerun must not pay a full
    # pass over the options just to fall through to the fixed empty answer.
    mapped: list[Any] = []
    if selected_ids:
        original_by_key = {
            _id_key(item_id): original
            for item_id, original in id_to_original.items()
        }
        seen_keys: set[str] = set()
        for selected_id in selected_ids:
            key = _id_key(selected_id)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if key in original_by_key:
                mapped.append(original_by_key[key])
            elif accept_new_options:
                mapped.append(str(selected_id))
            # else: drop silently

    if selection_mode == "single":
        # single mode is a cap of one (Python rejects any other max_selections
        # there), so it needs no separate truncation.
        return mapped[0] if mapped else None
    if max_selections is not None:
        return mapped[:max_selections]
    return mapped


def sort_items(
    items: list[dict[str, Any]],
    sort: str | None,
    sort_ascending: bool,
) -> list[dict[str, Any]]:
    """Reorder normalized items for the ``sort`` / ``sort_ascending`` params.

    ``sort`` is one of None | "items" | "groups" | "both":
      * None     -> no-op; the input list is returned unchanged.
      * "items"  -> sort items within each group by casefolded label; group
                    order (first-appearance) is preserved.
      * "groups" -> sort named groups by casefolded name; items within a group
                    keep their order. The ungrouped (no-``group``) block goes last.
      * "both"   -> sort items within each group AND sort group order; ungrouped
                    block last.

    ``sort_ascending`` reverses both comparisons when False; the ungrouped block
    stays last regardless of direction. The sort is stable. Input dicts are not
    mutated.
    """
    if sort is None:
        return items

    reverse = not sort_ascending
    sort_within = sort in ("items", "both")
    sort_groups = sort in ("groups", "both")

    # Partition into blocks, preserving first-appearance order. A None name is
    # the ungrouped block.
    blocks: list[tuple[str | None, list[dict[str, Any]]]] = []
    index_by_name: dict[str | None, int] = {}
    for item in items:
        name = item.get("group")
        idx = index_by_name.get(name)
        if idx is None:
            idx = len(blocks)
            index_by_name[name] = idx
            blocks.append((name, []))
        blocks[idx][1].append(item)

    if sort_within:
        for _name, block_items in blocks:
            block_items.sort(key=lambda it: it["label"].casefold(), reverse=reverse)

    if sort_groups:
        named = [b for b in blocks if b[0] is not None]
        ungrouped = [b for b in blocks if b[0] is None]
        named.sort(key=lambda b: b[0].casefold(), reverse=reverse)
        blocks = named + ungrouped

    return [it for _name, block_items in blocks for it in block_items]
