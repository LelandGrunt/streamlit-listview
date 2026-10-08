# Python wrapper (`streamlit_listview/`)

These rules extend the root `CLAUDE.md`. The comments in `__init__.py` and `_options.py` give the reasons in more detail.

## Files
- `__init__.py` declares the component at import time and defines `listview(...)`. `_validate_params` checks the parameters; the function then normalizes the options, resolves the defaults, ships a `data` dict to the frontend and maps the returned ids back to the original objects.
- `_options.py` holds `normalize_options` (id, label, group and disabled validation), `map_selection` (ids to original objects) and `sort_items`.
- `pyproject.toml` ships in the wheel. Streamlit reads it at runtime to resolve the asset globs (`asset_dir = "frontend/build"`). Its `name` must match the distribution name.

## Ids
- **An id is exactly a `str` or an `int`.** `float`, `None` and everything else are refused, and so is `bool`, explicitly, because it subclasses `int`. An `int` id satisfies `abs(id) <= 2**53 - 1`. Ids must be unique as rendered.
- **All three rules have one cause:** the frontend keys rows by JavaScript `String(id)`, and the payload crosses a JSON boundary. An id that shares its string with another, spells differently in JavaScript or loses precision as a double would render ambiguously. An id that JSON cannot carry blanks the widget, because Streamlit's serializer swallows the `TypeError`.
- **`_validate_id` is the one per-id gate.** It checks option ids, `default` ids and the ids `_persisted_selection` reads back from `st.session_state[key]`: a default or a persisted id seeds the frontend selection directly, so it crosses the same boundary. A malformed persisted list degrades to `None` as a whole; it never raises.

## Row identity
- **`_id_key` mirrors the frontend's `idKey`.** `str()` agrees with JavaScript `String()` for exactly the ids above. Every Python question about row identity goes through `_id_key`: the collision guard, `_resolve_default_ids` (membership and de-duplication) and `map_selection`. Python `==` calls `"1"` and `1` distinct, while the frontend renders and counts them as one row. **Never write a second `str(id)` for identity.**
- **`_resolve_default_ids` ships each matched default in the option's own spelling** (`default="1"` against the int option `1` ships `1`). The frontend canonicalizes its selection on the first render and commits any difference, so a seed in another spelling costs an extra rerun and a spurious `on_change` at mount.
- **`map_selection` applies the frontend's reconciliation on the way out** (root `CLAUDE.md`, *Invariants that span both languages*). It resolves each id by `_id_key` to its option, drops unknown ids (or keeps them as new entries under `accept_new_options`), collapses duplicate row keys, and truncates a multi selection to `max_selections`, keeping the earliest-selected ids. It must agree with `reconcileSelection` in `frontend/src/hooks/useSelection.ts`.

## New entries (`accept_new_options`)
- **A new entry comes back in the type of the other options.** `new_option_kind` infers that type from the options as passed: `"dict"` when all are dicts, `"int"` when all are ints, `"str"` otherwise (strings, mixed or none). `listview()` computes it only when adding is on and ships it as `data["new_option_kind"]`. `_new_entry` builds the value: `{"id": x, "label": str(x)}` (the frontend's synthetic row), an `int`, or `str(x)`.
- **A string becomes an `int` only through `_parse_new_int_id`**, the canonical-integer rule. It uses `re.fullmatch`, because `$` admits a trailing newline; `[0-9]`, because `\d` matches every Unicode digit; and at most 16 digits before `int()`, which raises past 4,300 digits. The frontend's `parseNewIntId` is the other copy, and both suites run the same input table. With int options the add field refuses anything else, and `_resolve_default_ids` raises on an unknown `default` that fails the rule.

## The `format_func` contract
- **It maps an option to its display label and receives the option as passed:** the dict for a dict option, the scalar for a `str` or `int` option. A label can therefore use any field the option carries, which the id alone cannot reach.
- **It runs only when an option has no usable `label`;** an explicit `label` wins. **`{"label": None}` and `{"label": nan}` still reach the formatter**, because `_is_usable_label` rejects them. That is the shape `df.to_dict("records")` gives a NULL cell, the most likely real-world dict option. A formatter written for plain values (`str.upper`, `LABELS.get`, anything `@lru_cache`d) raises on such a dict; `_label_for` wraps the failure in a `ValueError` that names the option.
- **The default is `None`, not `str`,** which would render a dict's repr. `None` labels by `str(id)`. That `str(item_id)` in `_label_for` is display, and deliberately not `_id_key`: routing it through `_id_key` would tie the default label to the row-key spelling forever.
- **The formatter receives the caller's own object, not a copy,** and `_label_for` runs before `group` and `disabled` are read. A formatter that mutates the option could therefore change the rendered row; the README calls the option read-only instead of defending against it.
