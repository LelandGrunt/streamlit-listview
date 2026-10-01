"""Built-in demo dataset + format_func presets/probe + on_change callback factory."""
from parsing import group_names

CITIES = [
    {"id": "berlin", "label": "Berlin", "group": "Germany"},
    {"id": "munich", "label": "Munich", "group": "Germany"},
    {"id": "hamburg", "label": "Hamburg", "group": "Germany"},
    {"id": "cologne", "label": "Cologne", "group": "Germany"},
    {"id": "frankfurt", "label": "Frankfurt", "group": "Germany"},
    {"id": "paris", "label": "Paris", "group": "France"},
    {"id": "lyon", "label": "Lyon", "group": "France"},
    {"id": "marseille", "label": "Marseille", "group": "France"},
    {"id": "nice", "label": "Nice", "group": "France"},
    {"id": "rome", "label": "Rome", "group": "Italy"},
    {"id": "milan", "label": "Milan", "group": "Italy"},
    {"id": "venice", "label": "Venice", "group": "Italy"},
    {"id": "florence", "label": "Florence", "group": "Italy"},
    {"id": "madrid", "label": "Madrid", "group": "Spain"},
    {"id": "barcelona", "label": "Barcelona", "group": "Spain"},
    {"id": "seville", "label": "Seville", "group": "Spain"},
    {"id": "vienna", "label": "Vienna", "group": "Austria"},
    {"id": "salzburg", "label": "Salzburg", "group": "Austria"},
    {"id": "graz", "label": "Graz", "group": "Austria"},
    {"id": "amsterdam", "label": "Amsterdam", "group": "Netherlands"},
    {"id": "rotterdam", "label": "Rotterdam", "group": "Netherlands"},
    {"id": "the_hague", "label": "The Hague", "group": "Netherlands"},
    {"id": "tokyo", "label": "Tokyo", "group": "Japan"},
    {"id": "osaka", "label": "Osaka", "group": "Japan"},
    {"id": "kyoto", "label": "Kyoto", "group": "Japan", "disabled": True},
    {"id": "nagoya", "label": "Nagoya", "group": "Japan"},
    {"id": "new_york", "label": "New York", "group": "United States"},
    {"id": "los_angeles", "label": "Los Angeles", "group": "United States"},
    {"id": "chicago", "label": "Chicago", "group": "United States"},
    {"id": "san_francisco", "label": "San Francisco", "group": "United States"},
    {"id": "seattle", "label": "Seattle", "group": "United States"},
    {"id": "sao_paulo", "label": "São Paulo", "group": "Brazil"},
    {"id": "rio", "label": "Rio de Janeiro", "group": "Brazil"},
    {"id": "brasilia", "label": "Brasília", "group": "Brazil"},
    {"id": "sydney", "label": "Sydney", "group": "Australia"},
    {"id": "melbourne", "label": "Melbourne", "group": "Australia"},
    {"id": "brisbane", "label": "Brisbane", "group": "Australia", "disabled": True},
]

# Ordered, de-duplicated group names of the built-in dataset. The demo derives
# its live groups via dataset.resolve_dataset; this constant exists for the
# tests, which pin resolve_dataset's built-in groups against it.
GROUPS = group_names(CITIES)


def make_large_dataset(n):
    """Generate a deterministic list of n grouped options for the performance demo.

    Ids are zero-padded so they sort and search predictably; items are grouped in
    contiguous batches of 100 (~ n/100 groups) so the Groups controls have
    something to act on. Labels are plain ``Item NNNNN`` so search-by-substring
    works and the demo's generated snippet stays a one-line comprehension.
    """
    return [
        {"id": f"item-{i:05d}", "label": f"Item {i:05d}", "group": f"Batch {i // 100:03d}"}
        for i in range(n)
    ]


# format_func presets. listview hands format_func the whole option — the dict for
# dict options, the scalar itself for plain values — and only consults it for
# options with no explicit `label` of their own.
#
# Each preset must be SELF-CONTAINED: codegen emits `inspect.getsource(func)` and
# nothing else, so a preset delegating to a shared helper would NameError both in
# the generated snippet and in the test that execs it. That rules out factoring
# the dict unwrap into one place — but it is not licence to reproduce listview's
# own "label, else id" precedence rule here; the library already applies it, and
# a demo-side copy of it is what the `_base_label` helper used to be.
#
# The unwrap is a conditional *expression* on purpose: as an if/else statement it
# would add branch arms to demo/data.py that only a dict-fed test could cover.
def fmt_upper(option):
    return str(option["id"] if isinstance(option, dict) else option).upper()


def fmt_title(option):
    return str(option["id"] if isinstance(option, dict) else option).title()


def fmt_bullet(option):
    return f"● {option['id'] if isinstance(option, dict) else option}"


def fmt_truncate(option):
    text = str(option["id"] if isinstance(option, dict) else option)
    return text if len(text) <= 10 else text[:9] + "…"


def fmt_type_badge(option):
    """Build the label from the option's own extra fields.

    This is what the option contract buys: `type` and `text` never reach the
    widget, yet they decide what the row says. Total by construction — a scalar
    option, a missing `text` and a missing `type` must all degrade rather than
    raise, because any exception inside format_func becomes a ValueError that
    app.py turns into st.error + st.stop(), blanking the result panel, and this
    preset is reachable by clicking against whatever the user pasted.
    """
    if not isinstance(option, dict):
        return str(option)
    # `text: null` is absent, not the text "None" — the same rule listview applies
    # to `label`, and JSON pasted into the demo is exactly where a null turns up.
    # Writing it as .get("text", option["id"]) would both miss that and look the
    # id up on every call.
    text = option.get("text")
    text = option["id"] if text is None else text
    return str(text) if option.get("type") == "Table" else f"{text} 👓"


# "No formatter" is not an entry: it is the Formatting picker's empty state
# (None), which is also listview's own default (the label is str(id)). Names
# must stay stable: codegen emits the source of the chosen function, so the
# function name appears in the snippet. The KEYS are persisted in
# st.session_state and looked up with .get(), so a dropped or renamed key
# degrades a live session to no formatter rather than raising.
FORMAT_PRESETS = {
    "UPPERCASE": fmt_upper,
    "Title Case": fmt_title,
    "Bullet prefix": fmt_bullet,
    "Truncate (10)": fmt_truncate,
    "Type badge (custom field)": fmt_type_badge,
}


class FormatProbe:
    """A format_func preset that counts how often listview actually calls it.

    listview consults format_func only for options without a usable `label`, so
    a preset can be accepted and still change nothing on screen. Zero calls over
    a non-empty option list is how the demo detects that — by asking the library
    rather than inspecting the options, which would re-derive the label rule
    demo-side (see the preset notes above).
    """

    def __init__(self, func):
        self.func = func
        self.calls = 0

    def __call__(self, option):
        self.calls += 1
        return self.func(option)


def make_on_change():
    """Build an on_change callback that toasts and bumps a session counter."""

    def _on_change():
        import streamlit as st

        st.session_state["demo_change_count"] = (
            st.session_state.get("demo_change_count", 0) + 1
        )
        st.toast("Selection changed", icon=":material/bolt:")

    return _on_change
