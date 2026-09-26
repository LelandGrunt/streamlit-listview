"""Generate a clean, runnable listview(...) snippet from the current config.

Deterministic and dependency-free (no `black`): one kwarg per line, four-space
indent, only non-default kwargs included.
"""
import inspect
import json
import math

from streamlit_listview import listview

import data
import dataset

# Parameters the generated call does NOT render as a value literal: the two
# positional args, the two callables emitted as raw identifiers above the call
# (format_func / on_change), on_change's args/kwargs plumbing (not exposed by the
# demo), and `key` (always emitted). Everything else is a value-kwarg.
_NOT_VALUE_KWARGS = frozenset(
    {"label", "options", "format_func", "on_change", "args", "kwargs", "key"}
)

# Defaults read straight off listview()'s signature. A kwarg is emitted only when
# the configured value differs from its default, so a hand-copied default that
# drifted from the real one would make the snippet — the demo's headline feature —
# emit a call that renders a *different* widget than the one on screen. Deriving
# them makes that drift impossible; dicts preserve insertion order, so iterating
# this also puts the kwargs in the signature's own declaration order.
_DEFAULTS = {
    name: param.default
    for name, param in inspect.signature(listview).parameters.items()
    if name not in _NOT_VALUE_KWARGS
}

# Parameters that apply only while another config setting enables them, as
# param -> (enabling predicate over the config, reset value). One table, two
# consumers: build_snippet suppresses the kwarg when the predicate fails (via
# _SKIP_WHEN below), and render_demo resets the cfg entry to the reset value —
# always the param's own listview default, so resetting and skipping describe
# the same call. Encoding the rule once keeps the emitted snippet and the live
# widget from ever disagreeing about a dependent param.
DEPENDENT_PARAMS = {
    "pin_search": (lambda c: bool(c.get("enable_search")), False),
    "max_selections": (lambda c: c.get("selection_mode") == "multi", None),
    "select_all": (lambda c: c.get("selection_mode") == "multi", False),
}

# Kwargs suppressed entirely when their enabling control is off, regardless of
# the configured value (e.g. search_placeholder is irrelevant when
# enable_search=False, so it must never appear even if set to a non-default).
# Each predicate returns True when the kwarg should be skipped. The
# DEPENDENT_PARAMS rules are derived (skip == not enabled); the rest are
# snippet-only — the demo deliberately keeps their cfg values (a disabled
# search-placeholder field stays populated) rather than resetting them.
_SKIP_WHEN = {
    name: (lambda c, enabled=enabled: not enabled(c))
    for name, (enabled, _reset) in DEPENDENT_PARAMS.items()
}
_SKIP_WHEN.update(
    {
        "search_placeholder": lambda c: not c.get("enable_search"),
        "collapsed_groups": lambda c: not c.get("collapsible_groups"),
        "sort_ascending": lambda c: c.get("sort") is None,
    }
)


def _pyval(value):
    """Render a Python literal for a config value."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # double-quoted, literal unicode
    if isinstance(value, list):
        return "[" + ", ".join(_pyval(v) for v in value) + "]"
    if isinstance(value, float):
        # Pasted options can carry non-finite floats — json.loads accepts
        # NaN/Infinity by default (json.dumps of a DataFrame NULL cell emits
        # NaN) — and str() renders them as bare identifiers (nan, inf) that
        # NameError when the snippet runs.
        if math.isnan(value):
            return "float('nan')"
        if math.isinf(value):
            return "float('inf')" if value > 0 else "float('-inf')"
        return repr(value)
    return str(value)  # int


def _pylit(value, indent=0):
    """Render a Python literal: dicts/lists multi-line at 4-space indent.

    Strings/bools/None/ints go through _pyval, so string contents are never
    altered (unlike a JSON dump + token substitution).
    """
    pad = "    " * indent
    pad2 = "    " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = ",\n".join(
            f"{pad2}{json.dumps(k, ensure_ascii=False)}: {_pylit(v, indent + 1)}"
            for k, v in value.items()
        )
        return "{\n" + items + ",\n" + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        items = ",\n".join(pad2 + _pylit(v, indent + 1) for v in value)
        return "[\n" + items + ",\n" + pad + "]"
    return _pyval(value)


def _options_block(options, builtin_dataset, keep_ids=()):
    # The built-in dataset is long, so abbreviate it to the first few options
    # plus a "# …" marker. Custom (user-pasted) options are rendered IN FULL so
    # the snippet reproduces exactly what the demo shows — truncating them would
    # silently drop rows that default= / max_selections may reference.
    #
    # `keep_ids` are option ids the snippet still references (the configured
    # default): any matching option is kept even when past the abbreviation
    # cut-off, so the generated snippet stays runnable — listview() raises
    # "default id ... is not present in options" if a default id is missing.
    if builtin_dataset:
        keep = set(keep_ids)
        shown = [
            opt
            for i, opt in enumerate(options)
            if i < 3 or (opt["id"] if isinstance(opt, dict) else opt) in keep
        ]
    else:
        shown = options
    rendered = _pylit(shown, 0)
    if builtin_dataset and rendered.endswith("\n]"):
        rendered = rendered[:-2] + "\n    # …\n]"
    return f"options = {rendered}"


def _large_options_block(n):
    """Emit a comprehension reproducing data.make_large_dataset(n).

    Kept structurally identical to make_large_dataset so the snippet is truthful;
    tests/test_demo.py executes this block and compares it to the generator.
    """
    return (
        "options = [\n"
        '    {"id": f"item-{i:05d}", "label": f"Item {i:05d}", '
        '"group": f"Batch {i // 100:03d}"}\n'
        f"    for i in range({n})\n"
        "]"
    )


def build_snippet(config, options, builtin_dataset):
    defs = []  # function-definition blocks placed above the call
    head_kwargs = []  # raw-identifier kwargs: format_func, on_change

    preset_name = config.get("format_preset", "None")
    if preset_name != "None":
        func = data.FORMAT_PRESETS[preset_name]
        # The preset's own source is the whole definition — that is a constraint
        # on the presets, not a convenience: only this one def is emitted, so a
        # preset that called a shared helper would NameError in the snippet the
        # user copies out. See the note in demo/data.py.
        defs.append(inspect.getsource(func).rstrip())
        head_kwargs.append(("format_func", func.__name__))

    if config.get("on_change"):
        # Illustrative callback for the snippet; the live demo's own callback also
        # bumps a session counter, omitted here for clarity.
        defs.append('def on_change():\n    st.toast("Selection changed", icon=":material/bolt:")')
        head_kwargs.append(("on_change", "on_change"))

    value_kwargs = []
    for name in _DEFAULTS:
        skip = _SKIP_WHEN.get(name)
        if skip is not None and skip(config):
            continue
        value = config.get(name, _DEFAULTS[name])
        if value == _DEFAULTS[name]:
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, str) and value == "":
            continue
        value_kwargs.append((name, _pyval(value)))

    arg_lines = [f'    {_pyval(config["label"])},', "    options,"]
    arg_lines += [f"    {k}={v}," for k, v in head_kwargs]
    arg_lines += [f"    {k}={v}," for k, v in value_kwargs]
    arg_lines.append('    key="demo_listview",')

    # The listview(...) call block. When the demo renders the widget in the
    # sidebar, wrap just this block in `with st.sidebar:` (indenting it one
    # level); st.write(selected) stays at the top level so the result still
    # renders in the main area. `sidebar` is a demo-layout flag, not a
    # listview kwarg, so it never appears inside the call.
    call_lines = ["selected = listview("] + arg_lines + [")"]
    if config.get("sidebar"):
        call_lines = ["with st.sidebar:"] + ["    " + line for line in call_lines]

    parts = ["import streamlit as st", "from streamlit_listview import listview", ""]
    for block in defs:
        parts.append(block)
        parts.append("")
    if dataset.DATA_SOURCES[config["data_source"]].snippet_comprehension:
        parts.append(_large_options_block(config.get("large_size", 1000)))
    else:
        # Keep any built-in option the default references so the snippet runs.
        default_cfg = config.get("default")
        if default_cfg is None:
            keep_ids = ()
        elif isinstance(default_cfg, list):
            keep_ids = tuple(default_cfg)
        else:
            keep_ids = (default_cfg,)
        parts.append(_options_block(options, builtin_dataset, keep_ids))
    parts.append("")
    parts.extend(call_lines)
    parts.append("")
    parts.append("st.write(selected)")
    return "\n".join(parts) + "\n"
