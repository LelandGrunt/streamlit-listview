"""Parse the Data text area into a list of listview options."""
import json


def parse_options_text(text):
    """Return a list of options parsed from the text area.

    - Empty/whitespace/None -> [] (caller falls back to the built-in dataset).
    - Valid JSON array -> that list.
    - Valid JSON object/scalar -> wrapped in a single-element list.
    - Anything else -> one option per non-empty line.

    Shape validation (e.g. dicts missing "id") is left to listview, which raises
    a ValueError the app surfaces via st.error.
    """
    if not text or not text.strip():
        return []
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return [line.strip() for line in stripped.splitlines() if line.strip()]
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def option_ids(options):
    """Return the selectable ids for the option list.

    A scalar option is its own id; a dict option contributes its ``id``. Dict
    options missing ``id`` are skipped rather than raising, so the demo's
    Default picker keeps working and the downstream ``listview(...)`` call is
    the one that surfaces the friendly ``ValueError`` (via ``st.error``) for the
    malformed option.
    """
    ids = []
    for option in options:
        if isinstance(option, dict):
            if "id" in option:
                ids.append(option["id"])
        else:
            ids.append(option)
    return ids


def group_names(options):
    """Ordered, unique ``group`` names of the dict options.

    Scalar options and dicts without ``group`` contribute nothing; a group's
    position is fixed by its first occurrence. The one spelling of the rule —
    ``data.GROUPS`` and ``dataset.resolve_dataset``'s groups both come from here.
    """
    return list(
        dict.fromkeys(
            o["group"] for o in options if isinstance(o, dict) and "group" in o
        )
    )


def coerce_single_default(default, ids):
    """Normalize a configured default to a single valid id, or ``None``.

    A list default (carried over from multi mode) contributes its first entry.
    Validity is membership in ``ids`` — not truthiness — so a falsy id like
    ``0`` or ``""`` survives.
    """
    if isinstance(default, list):
        default = default[0] if default else None
    return default if default in ids else None


def coerce_multi_default(default, ids):
    """Normalize a configured default to a list of valid ids.

    A scalar default (carried over from single mode) becomes a one-item list
    instead of iterating its characters; ``None`` becomes ``[]``. Entries are
    kept by membership in ``ids`` — not truthiness — so a falsy id survives.
    """
    if not isinstance(default, list):
        default = [] if default is None else [default]
    if not default:
        # The common case with the Large dataset. Nothing to validate, so don't
        # pay for indexing up to 10,000 ids.
        return []
    try:
        valid = set(ids)
        return [d for d in default if d in valid]
    except TypeError:
        # A pasted Custom option (or an id carried over from one) can be
        # unhashable — e.g. a nested JSON array. listview() is what rejects that,
        # with a message the demo surfaces via st.error, but this runs first: fall
        # back to the O(n) scan rather than crashing on a raw TypeError.
        return [d for d in default if d in ids]


def has_selection(selected):
    """True when ``listview(...)`` returned an actual selection.

    Single mode returns the option itself (which may be falsy — id ``0`` or an
    empty-string id), so a plain truthiness test would wrongly report "nothing
    selected" for those. Multi mode returns a list, empty when nothing is
    selected. A selection exists iff the value is not ``None`` and not the empty
    list.
    """
    return selected is not None and selected != []
