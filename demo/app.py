"""listview interactive demo — run with: streamlit run demo/app.py"""

import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd
import streamlit as st

# Make sibling modules importable regardless of the working directory.
DEMO_DIR = Path(__file__).resolve().parent
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

import data  # noqa: E402
from codegen import DEPENDENT_PARAMS, build_snippet  # noqa: E402
from parsing import coerce_multi_default, coerce_single_default, has_selection  # noqa: E402

import dataset  # noqa: E402

from streamlit_listview import listview  # noqa: E402

try:
    LISTVIEW_VERSION = version("streamlit-listview")
except PackageNotFoundError:  # running from source without an installed dist
    LISTVIEW_VERSION = "dev"

st.set_page_config(
    page_title="Listview · Component Demo",
    page_icon=":material/list:",
    layout="wide",
)

# Streamlit's main content area carries a large default top padding (6rem / 96px
# in wide layout), leaving a tall empty band above the title even though the
# fixed top header is only ~60px tall. There's no config.toml option for
# block-container padding, so trim it with a small CSS rule. 3rem still clears
# the header comfortably without the wasted space.
st.html("<style>.stMainBlockContainer { padding-top: 3rem; }</style>")

DEFAULT_CONFIG = {
    "data_source": "Built-in cities",
    "options_text": "",
    "large_size": 1000,
    "label": "Cities",
    "selection_mode": "single",
    "default": None,
    "placeholder": "",
    "help": "Pick from the list of cities.",
    "label_visibility": "visible",
    "width": "stretch",
    "height": 300,
    "item_height": None,
    "content_font_size": None,
    "show_grid_lines": True,
    "sidebar": False,
    "disabled": False,
    "accept_new_options": False,
    "max_selections": None,
    "select_all": False,
    "enable_search": True,
    "pin_search": False,
    "search_placeholder": "Search cities…",
    "collapsible_groups": False,
    "collapsed_groups": None,
    "sort": None,
    "sort_ascending": True,
    "format_preset": "None",
    "on_change": False,
}

cfg = st.session_state.setdefault("demo_config", dict(DEFAULT_CONFIG))
# Backfill keys added to DEFAULT_CONFIG after a session was first created, so a
# pre-existing session_state dict (e.g. surviving a hot-reload) never misses a
# key the code now reads — notably "options_text", consumed by resolve_dataset.
for _key, _value in DEFAULT_CONFIG.items():
    cfg.setdefault(_key, _value)
st.session_state.setdefault("demo_change_count", 0)
# Bumped by "Reset selection" to force a fresh widget key (see render_demo).
st.session_state.setdefault("demo_reset_nonce", 0)
# True for the one run right after a reset, so the demo can explain a re-seeded
# Default (the list won't be empty when a Default is configured).
st.session_state.setdefault("demo_just_reset", False)

SIGNATURE = """def listview(
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
) -> dict | str | int | list | None"""

PARAMS = [
    {
        "Parameter": "label",
        "Type": "str",
        "Default": "required",
        "Description": "Label above the widget. Supports inline Markdown (bold, italics, code, links, colors, :material/icons:).",
    },
    {
        "Parameter": "options",
        "Type": "Iterable | None",
        "Default": "None",
        "Description": "Scalars (id == label) or dicts with id (required), label, group, disabled. None/empty -> empty list.",
    },
    {
        "Parameter": "selection_mode",
        "Type": '"single" | "multi"',
        "Default": '"single"',
        "Description": "Single or multiple selection.",
    },
    {
        "Parameter": "default",
        "Type": "Any | list | None",
        "Default": "None",
        "Description": "Pre-selected id (single) or list of ids (multi).",
    },
    {
        "Parameter": "format_func",
        "Type": "Callable[[Any], str] | None",
        "Default": "None",
        "Description": "Maps an option (the dict, or the scalar itself) -> display label. Only consulted for options without a usable label; None labels by str(id).",
    },
    {
        "Parameter": "enable_search",
        "Type": "bool",
        "Default": "False",
        "Description": "Show a live label filter.",
    },
    {
        "Parameter": "pin_search",
        "Type": "bool",
        "Default": "False",
        "Description": "Keep the search field sticky while the list scrolls. Requires enable_search=True.",
    },
    {
        "Parameter": "search_placeholder",
        "Type": "str",
        "Default": '"Search"',
        "Description": "Placeholder for the search field.",
    },
    {
        "Parameter": "collapsible_groups",
        "Type": "bool",
        "Default": "False",
        "Description": "Let group headers collapse/expand.",
    },
    {
        "Parameter": "collapsed_groups",
        "Type": 'list[str] | "all" | None',
        "Default": "None",
        "Description": "Groups collapsed on first render (initial state only).",
    },
    {
        "Parameter": "sort",
        "Type": '"items" | "groups" | "both" | None',
        "Default": "None",
        "Description": "Alphabetically sort items, group headers, or both (by displayed label / group name, case-insensitive). None = input order.",
    },
    {
        "Parameter": "sort_ascending",
        "Type": "bool",
        "Default": "True",
        "Description": "Sort direction when sort is set: True = A→Z, False = Z→A. Ungrouped items always render last when groups are sorted.",
    },
    {
        "Parameter": "accept_new_options",
        "Type": "bool",
        "Default": "False",
        "Description": "Let users add entries not in options; returned as the plain typed string.",
    },
    {
        "Parameter": "max_selections",
        "Type": "int | None",
        "Default": "None",
        "Description": "Cap on selections in multi mode.",
    },
    {
        "Parameter": "select_all",
        "Type": "bool",
        "Default": "False",
        "Description": "Show a Select all / Deselect all toggle in the header (multi mode only; raises in single mode). Acts on the rows matching the current search — including rows inside collapsed groups (collapse is visual, not a filter), excluding disabled rows — up to max_selections.",
    },
    {
        "Parameter": "placeholder",
        "Type": "str | None",
        "Default": "None",
        "Description": "Text shown when options is empty.",
    },
    {
        "Parameter": "height",
        "Type": "int",
        "Default": "300",
        "Description": "List height in px (>= 100).",
    },
    {
        "Parameter": "item_height",
        "Type": "int | None",
        "Default": "None",
        "Description": "Minimum row height in px (>= 1; floor). None = auto.",
    },
    {
        "Parameter": "content_font_size",
        "Type": "int | None",
        "Default": "None",
        "Description": "Font size (px) of list content — option rows and group headers. None = theme default.",
    },
    {
        "Parameter": "width",
        "Type": '"stretch" | int',
        "Default": '"stretch"',
        "Description": "Widget width: stretch or pixels.",
    },
    {
        "Parameter": "show_grid_lines",
        "Type": "bool",
        "Default": "True",
        "Description": "Show divider lines between option rows. False for a more compact look.",
    },
    {
        "Parameter": "help",
        "Type": "str | None",
        "Default": "None",
        "Description": "Tooltip (full GFM Markdown). Shown only when the label is visible.",
    },
    {
        "Parameter": "disabled",
        "Type": "bool",
        "Default": "False",
        "Description": "Disable the widget.",
    },
    {
        "Parameter": "label_visibility",
        "Type": '"visible" | "hidden" | "collapsed"',
        "Default": '"visible"',
        "Description": "Show, space-reserve, or fully hide the label.",
    },
    {
        "Parameter": "on_change",
        "Type": "Callable | None",
        "Default": "None",
        "Description": "Native callback fired before the rerun when the selection changes.",
    },
    {
        "Parameter": "args / kwargs",
        "Type": "tuple | dict | None",
        "Default": "None",
        "Description": "Positional/keyword args forwarded to on_change.",
    },
    {
        "Parameter": "key",
        "Type": "str | None",
        "Default": "None",
        "Description": "Strongly recommended: preserves frontend state across parameter changes.",
    },
]

RETURNS_MD = """\
**Type:** `dict | str | int | list | None`

- **single** → the selected option exactly as passed (dict or scalar), or `None`.
- **multi** → a list of the selected options in selection order; `[]` if none.
- Entries added via `accept_new_options` come back as the plain string the user typed.
"""

# Seed shown in the Custom-data text area placeholder and inserted by the
# "Insert example" button, so users can start from a valid row instead of a
# blank field.
CUSTOM_EXAMPLE = '[\n  {"id": "berlin", "label": "Berlin", "group": "Germany"}\n]'

# A richer row inserted by the "Insert example with Payload" button. It adds a
# per-option `disabled` flag and an arbitrary `Payload`. The widget ignores
# unknown keys when rendering, but the *whole* original dict is returned in the
# selection result — so this demonstrates round-tripping your own metadata back
# out of a selection.
CUSTOM_EXAMPLE_PAYLOAD = (
    "[\n"
    "  {\n"
    '    "id": "berlin",\n'
    '    "label": "Berlin",\n'
    '    "group": "Germany",\n'
    '    "disabled": false,\n'
    '    "Payload": {\n'
    '      "FederalState": "Berlin"\n'
    "    }\n"
    "  }\n"
    "]"
)

# Rows inserted by the "Insert example with fields" button. Deliberately carry NO
# `label`: an explicit label wins over format_func, so a labelled row would make
# every preset inert. These feed the "Type badge (custom field)" preset, which
# builds the label out of `text` and `type` — fields the widget never renders.
CUSTOM_EXAMPLE_FIELDS = (
    "[\n"
    '  {"id": 1, "text": "Orders", "type": "Table"},\n'
    '  {"id": 2, "text": "OrdersView", "type": "View"}\n'
    "]"
)


def _insert_custom_example(text):
    """Fill the Custom options text area with an example row (button callback)."""
    st.session_state["cfg_options_text"] = text


def _set_multi_default(values):
    """Pre-fill the multi-mode Default multiselect with a sample list (button cb)."""
    st.session_state["cfg_default_multi"] = list(values)


def _section_header(icon, title):
    """Render the active config section's bold icon + title header."""
    st.markdown(f"**:material/{icon}: {title}**")


def render_data(cfg):
    cfg["data_source"] = st.segmented_control(
        "Data source",
        list(dataset.DATA_SOURCES),
        default=cfg["data_source"],
        required=True,
        help=(
            "Built-in city dataset, your own pasted options, an empty list "
            "to see the placeholder, or a large generated dataset to feel "
            "render performance."
        ),
        key="cfg_data_source",
    )
    source = dataset.DATA_SOURCES[cfg["data_source"]]
    if source.options_editor:
        ex_col, ex_payload_col, ex_fields_col = st.columns(3)
        ex_col.button(
            "Insert example",
            icon=":material/content_paste:",
            on_click=_insert_custom_example,
            args=(CUSTOM_EXAMPLE,),
            help=(
                "Fill the field with a one-row example you can edit and "
                "extend, so you don't have to type the first entry."
            ),
            width="stretch",
            key="cfg_insert_example",
        )
        ex_payload_col.button(
            "Insert example with Payload",
            icon=":material/data_object:",
            on_click=_insert_custom_example,
            args=(CUSTOM_EXAMPLE_PAYLOAD,),
            help=(
                "Like the example, but the row also carries a `disabled` "
                "flag and a custom `Payload`. Extra keys aren't shown in "
                "the list, yet the whole dict comes back in the selection "
                "result — handy for attaching your own metadata."
            ),
            width="stretch",
            key="cfg_insert_example_payload",
        )
        ex_fields_col.button(
            "Insert example with fields",
            icon=":material/label:",
            on_click=_insert_custom_example,
            args=(CUSTOM_EXAMPLE_FIELDS,),
            help=(
                "Rows with no `label`, carrying their own `text` and `type` "
                "fields. Pick **Formatting → Type badge (custom field)** to see "
                "`format_func` build each label out of those fields."
            ),
            width="stretch",
            key="cfg_insert_example_fields",
        )
        # CHANGE: re-seed the text area from the persisted value only when its key
        # was cleared (returning to the Data section). setdefault leaves a present
        # key untouched, so live edits and the insert-example buttons still work.
        st.session_state.setdefault("cfg_options_text", cfg["options_text"])
        cfg["options_text"] = st.text_area(
            "Options",
            height=200,
            key="cfg_options_text",
            help="JSON array of option dicts, or one option per line.",
            placeholder=CUSTOM_EXAMPLE,
        )
    elif source.sized:
        cfg["large_size"] = st.select_slider(
            "Items",
            options=[100, 500, 1000, 2500, 5000, 10000],
            value=cfg["large_size"],
            help=(
                "Number of generated options. The list isn't virtualized, "
                "so larger sizes show the component's render/scroll cost."
            ),
            key="cfg_large_size",
        )


def render_basic(cfg, ids, groups):
    cfg["label"] = st.text_input(
        "Label",
        cfg["label"],
        help="Text shown above the list. Renders inline Markdown — **bold**, *italics*, `code`, links, colored text (`:red[…]`), and Material icons (`:material/star:`).",
        key="cfg_label",
    )
    cfg["selection_mode"] = st.segmented_control(
        "Selection mode",
        ["single", "multi"],
        default=cfg["selection_mode"],
        required=True,
        help="Single returns one option (or None); multi returns a list of options.",
        key="cfg_selection_mode",
    )
    if cfg["selection_mode"] == "single":
        # None itself is the "no default" choice — kept out of the id namespace
        # (rather than an in-band string sentinel) so a pasted Custom option
        # whose id is literally "— none —" stays a normal, pickable default.
        choices = [None, *ids]
        prior = coerce_single_default(cfg["default"], ids)
        cfg["default"] = st.selectbox(
            "Default",
            choices,
            index=choices.index(prior),
            # str(v), not v: ids need not be strings, and selectbox's default
            # format_func (str) is what rendered them before None joined the list.
            format_func=lambda v: "— none —" if v is None else str(v),
            help="Option pre-selected when the widget first mounts.",
            key="cfg_default_single",
        )
    else:
        # Drive the multiselect through its key: seed from the persistent cfg
        # default when the key was cleared while the Basic section was
        # off-screen (preserves a configured multi default and the "Use sample
        # defaults" value), and keep only ids still in the option set.
        prior = st.session_state.get("cfg_default_multi", cfg["default"])
        st.session_state["cfg_default_multi"] = coerce_multi_default(prior, ids)
        sample = ids[: min(3, cfg["max_selections"] or 3)]
        st.button(
            "Use sample defaults",
            icon=":material/checklist:",
            on_click=_set_multi_default,
            args=(sample,),
            disabled=len(sample) < 2,
            help=(
                "Pre-fill several pre-selected options to try a "
                "multi-value (list) default."
            ),
            key="cfg_default_multi_sample",
        )
        cfg["default"] = st.multiselect(
            "Default",
            ids,
            help="Options pre-selected when the widget first mounts.",
            key="cfg_default_multi",
        )
    cfg["placeholder"] = st.text_input(
        "Placeholder",
        cfg["placeholder"],
        help="Text shown when there are no options to display. Empty uses the built-in default.",
        key="cfg_placeholder",
    )
    cfg["help"] = st.text_input(
        "Help",
        cfg["help"],
        help="Tooltip shown next to the label (full Markdown). Only appears when label visibility is 'visible'.",
        key="cfg_help",
    )


def render_appearance(cfg, ids, groups):
    cfg["label_visibility"] = st.segmented_control(
        "Label visibility",
        ["visible", "hidden", "collapsed"],
        default=cfg["label_visibility"],
        required=True,
        help="Show the label, reserve its space but hide it, or collapse it entirely.",
        key="cfg_label_visibility",
    )
    width_choice = st.segmented_control(
        "Width",
        ["stretch", "300", "500", "700"],
        default="stretch" if cfg["width"] == "stretch" else str(cfg["width"]),
        required=True,
        help="Stretch fills the container; a pixel value sets a fixed width.",
        key="cfg_width",
    )
    cfg["width"] = "stretch" if width_choice == "stretch" else int(width_choice)
    cfg["height"] = st.slider(
        "Height (px)",
        100,
        600,
        cfg["height"],
        step=20,
        help="Height of the scrollable list area in pixels (minimum 100).",
        key="cfg_height",
    )
    if st.toggle(
        "Custom item height",
        cfg["item_height"] is not None,
        help="Set a minimum row height instead of auto-sizing to content.",
        key="cfg_use_item_height",
    ):
        cfg["item_height"] = st.slider(
            "Item height (px)",
            1,
            100,
            cfg["item_height"] or 40,
            step=4,
            help=(
                "Minimum row height in px. Rows never shrink below their "
                "content, so values under a row's natural height have no "
                "visible effect."
            ),
            key="cfg_item_height",
        )
    else:
        cfg["item_height"] = None
    if st.toggle(
        "Custom content font size",
        cfg["content_font_size"] is not None,
        help="Set the font size of option rows and group headers; smaller = more compact.",
        key="cfg_use_content_font_size",
    ):
        cfg["content_font_size"] = st.slider(
            "Content font size (px)",
            8,
            24,
            cfg["content_font_size"] or 12,
            step=1,
            help=(
                "Font size (px) of the list content (rows + group "
                "headers). Rows shrink to fit. None = theme default."
            ),
            key="cfg_content_font_size",
        )
    else:
        cfg["content_font_size"] = None
    cfg["show_grid_lines"] = st.toggle(
        "Show grid lines",
        cfg["show_grid_lines"],
        help="Divider lines between option rows. Turn off for a more compact list.",
        key="cfg_show_grid_lines",
    )


def render_layout(cfg, ids, groups):
    cfg["sidebar"] = st.toggle(
        "Render widget in sidebar",
        cfg["sidebar"],
        help=(
            "Render the live listview in Streamlit's sidebar instead "
            'of the main area. The sidebar is narrow, so width="stretch" '
            "fits best."
        ),
        key="cfg_sidebar",
    )


def render_behavior(cfg, ids, groups):
    cfg["disabled"] = st.toggle(
        "Disabled",
        cfg["disabled"],
        help="Render the list greyed-out and non-interactive.",
        key="cfg_disabled",
    )
    cfg["accept_new_options"] = st.toggle(
        "Accept new options",
        cfg["accept_new_options"],
        help="Let users add entries not in the list; they come back as the typed string.",
        key="cfg_accept_new",
    )
    if cfg["selection_mode"] == "multi":
        if st.toggle(
            "Limit max selections",
            cfg["max_selections"] is not None,
            help="Cap how many options can be selected at once (multi mode).",
            key="cfg_use_max",
        ):
            cfg["max_selections"] = st.number_input(
                "Max selections",
                1,
                20,
                cfg["max_selections"] or 3,
                help="Maximum number of options the user may select.",
                key="cfg_max",
            )
        else:
            cfg["max_selections"] = None
        cfg["select_all"] = st.toggle(
            "Select all toggle",
            cfg["select_all"],
            help="Add a Select all / Deselect all action to the header (multi mode).",
            key="cfg_select_all",
        )
    else:
        # The single-mode reset of max_selections/select_all lives in render_demo's
        # post-dispatch reconciliation (it must run even when this section is
        # off-screen). Here we only explain why the controls are hidden.
        st.caption("Max selections and Select all apply in multi-selection mode.")


def render_search(cfg, ids, groups):
    cfg["enable_search"] = st.toggle(
        "Enable search",
        cfg["enable_search"],
        help="Show a search box that filters items by label as you type.",
        key="cfg_enable_search",
    )
    cfg["pin_search"] = st.toggle(
        "Pin search (sticky)",
        cfg["pin_search"],
        disabled=not cfg["enable_search"],
        help="Keep the search box fixed at the top while the list scrolls. Requires enable_search.",
        key="cfg_pin_search",
    )
    cfg["search_placeholder"] = st.text_input(
        "Search placeholder",
        cfg["search_placeholder"],
        disabled=not cfg["enable_search"],
        help="Placeholder text shown inside the search box.",
        key="cfg_search_ph",
    )


def render_groups(cfg, ids, groups):
    if not groups:
        st.caption("The current options have no `group` fields.")
    cfg["collapsible_groups"] = st.toggle(
        "Collapsible groups",
        cfg["collapsible_groups"],
        help="Let users collapse and expand each group header.",
        key="cfg_collapsible",
    )
    collapse_disabled = not cfg["collapsible_groups"]
    if st.toggle(
        "Start with all groups collapsed",
        cfg["collapsed_groups"] == "all",
        disabled=collapse_disabled,
        help="Render every group collapsed on first load. Requires collapsible groups.",
        key="cfg_collapse_all",
    ):
        cfg["collapsed_groups"] = "all"
    else:
        prev = (
            cfg["collapsed_groups"]
            if isinstance(cfg["collapsed_groups"], list)
            else []
        )
        prev = [g for g in prev if g in groups]
        chosen = st.multiselect(
            "Initially collapsed groups",
            groups,
            default=prev,
            disabled=collapse_disabled,
            help="Groups that start collapsed on first load; the rest start expanded. Requires collapsible groups.",
            key="cfg_collapsed_groups",
        )
        cfg["collapsed_groups"] = chosen or None
    if cfg["collapsible_groups"]:
        st.caption(
            "`collapsed_groups` applies only at mount, so changing it "
            "remounts the widget here (clearing the current selection)."
        )


def render_sorting(cfg, ids, groups):
    sort_choices = [None, "items", "groups", "both"]
    cfg["sort"] = st.selectbox(
        "Sort",
        sort_choices,
        index=sort_choices.index(cfg["sort"]),
        format_func=lambda v: "— none —" if v is None else v,
        help=(
            "Alphabetically sort items, group headers, or both "
            "(by displayed label / group name, case-insensitive). "
            "None keeps input order."
        ),
        key="cfg_sort",
    )
    if cfg["sort"] is not None:
        cfg["sort_ascending"] = st.toggle(
            "Ascending (A→Z)",
            cfg["sort_ascending"],
            help=(
                "Sort direction. Off = Z→A. Ungrouped items always "
                "render last when groups are sorted."
            ),
            key="cfg_sort_ascending",
        )


def render_formatting(cfg, ids, groups):
    preset_names = list(data.FORMAT_PRESETS)
    cfg["format_preset"] = st.selectbox(
        "Label formatting (format_func)",
        preset_names,
        index=preset_names.index(cfg["format_preset"]),
        format_func=lambda name: "— none —" if name == "None" else name,
        help=(
            "Transform how each option's label is displayed; the underlying value "
            "is unchanged. `format_func` receives the **whole option** — the dict "
            "for dict options, the scalar itself for plain values — so it can "
            "build a label from any field the option carries. An explicit `label` "
            "always wins over it, so a preset only shows on options that carry no "
            "label of their own."
        ),
        key="cfg_format_preset",
    )
    # Every option in the built-in and generated datasets carries an explicit
    # `label`, which takes precedence over format_func — so a preset chosen there
    # changes nothing on screen. Say so, rather than letting the control look broken.
    if (
        cfg["format_preset"] != "None"
        and dataset.DATA_SOURCES[cfg["data_source"]].labels_explicit
    ):
        st.caption(
            ":material/info: This dataset gives every option an explicit `label`, "
            "which wins over `format_func`. Switch **Data → Custom** and paste "
            "plain lines (or dicts without a `label`) to see the preset take effect."
        )
    cfg["on_change"] = st.toggle(
        "Change callback (on_change)",
        cfg["on_change"],
        help="Run a callback when the selection changes — here a toast plus a change counter.",
        key="cfg_on_change",
    )
    if not cfg["on_change"]:
        st.session_state["demo_change_count"] = 0


# Config section name -> (Material icon, renderer). Single source for the pill
# labels, the section headers AND the dispatch, so a section can no longer be
# added to the switcher and then render a header above an empty panel. Every
# renderer takes the same (cfg, ids, groups) triple even where it needs only cfg,
# which is what lets render_demo call them through this table.
#
# "Data" is the exception with no renderer here: its controls decide *what* gets
# resolved, so it has to render before resolution rather than after it, and
# render_demo calls it there explicitly.
SECTIONS = {
    "Basic": ("tune", render_basic),
    "Data": ("dataset", None),
    "Appearance": ("palette", render_appearance),
    "Layout": ("view_sidebar", render_layout),
    "Behavior": ("settings", render_behavior),
    "Search": ("search", render_search),
    "Groups": ("folder", render_groups),
    "Sorting": ("sort", render_sorting),
    "Formatting": ("bolt", render_formatting),
}


def render_demo():
    demo_col, config_col = st.columns([2, 1], gap="large")

    # Render configuration first so the demo column knows the option ids/groups.
    with config_col:
        st.subheader(":material/tune: Configuration")
        section = st.pills(
            "Configuration section",
            list(SECTIONS),
            default="Basic",
            selection_mode="single",
            required=True,
            key="cfg_section",
            label_visibility="collapsed",
        )
        icon, render_section = SECTIONS[section]
        _section_header(icon, section)

        # Render Data controls before resolving, so a fresh source/paste takes
        # effect this run. When another section is active they are not rendered
        # and resolution reads the persisted cfg values instead.
        if section == "Data":
            render_data(cfg)

        source = dataset.DATA_SOURCES[cfg["data_source"]]
        _t0 = time.perf_counter()
        options, ids, groups, builtin = dataset.resolve_dataset(cfg)
        large_build_ms = (
            (time.perf_counter() - _t0) * 1000 if source.timed else None
        )

        if render_section is not None:
            render_section(cfg, ids, groups)

    # Reconcile cfg for the live call AFTER the active section has rendered, so
    # selection_mode / search / groups reflect THIS run (their toggles live in
    # render_basic / render_search / render_groups; an off-screen section can't
    # self-correct). Running it here — not before the dispatch — is what lets a
    # multi->single switch clear the multi-only params with the new mode, and a
    # data-source change drop ids/groups that no longer exist, before the API
    # call and the remount key read them.
    if cfg["selection_mode"] == "multi":
        cfg["default"] = coerce_multi_default(cfg["default"], ids)
    else:
        cfg["default"] = coerce_single_default(cfg["default"], ids)
    # The multi-only / search-only params reset through the same table codegen's
    # skip rules derive from, so the live call and the emitted snippet cannot
    # encode the dependency rules in opposite polarity and drift apart.
    for name, (enabled, reset) in DEPENDENT_PARAMS.items():
        if not enabled(cfg):
            cfg[name] = reset
    if isinstance(cfg["collapsed_groups"], list):
        cfg["collapsed_groups"] = [
            g for g in cfg["collapsed_groups"] if g in groups
        ] or None

    target = st.sidebar if cfg["sidebar"] else demo_col

    # The selection lives in the component's frontend React state, so it
    # only clears/re-seeds on remount — and a v2 component remounts when its
    # key changes. Three mount-time things therefore fold into the key:
    #   * collapsed_groups — initial-state-only, so changing it re-applies.
    #   * default — seeds the frontend selection at mount only; on a keyed
    #     instance a later default change re-seeds NEITHER the display NOR
    #     the returned value, so remounting is the only way a new default
    #     gets applied.
    #   * demo_reset_nonce — bumped by "Reset selection" to force a clean
    #     remount; popping session_state alone clears the Python-side value
    #     but leaves the frontend rows highlighted.
    # Every other control keeps the stable prefix and updates in place.
    # !r, not str(): values str() collapses (None vs the option id "None",
    # 1 vs "1") must still render distinct keys, or the remount never fires
    # and the picked default is silently never applied.
    widget_key = (
        f"demo_listview::{cfg['collapsed_groups']!r}::{cfg['default']!r}"
        f"::r{st.session_state['demo_reset_nonce']}"
    )
    fmt = data.FORMAT_PRESETS[cfg["format_preset"]]

    # The live widget (and its "Live component" label) render into the chosen
    # target — the sidebar or the main demo column. Placement is NOT folded
    # into widget_key: a keyed v2 component drops its container from the
    # element id, so the Python-side widget state survives moving between
    # sidebar and main, and the wrapper ships that persisted selection
    # (data.state_selection) for the remounted frontend to re-seed from — the
    # rows AND the returned value both carry over; only frontend-local UI
    # state (search text, scroll, collapse) resets with the remount. The
    # selection result, Reset, and generated code always stay in the main
    # demo column below.
    with target:
        st.subheader(":material/play_circle: Live component")
        try:
            selected = listview(
                cfg["label"],
                options,
                selection_mode=cfg["selection_mode"],
                default=cfg["default"],
                format_func=fmt,
                enable_search=cfg["enable_search"],
                pin_search=cfg["pin_search"],
                search_placeholder=cfg["search_placeholder"] or "Search",
                collapsible_groups=cfg["collapsible_groups"],
                collapsed_groups=cfg["collapsed_groups"],
                sort=cfg["sort"],
                sort_ascending=cfg["sort_ascending"],
                accept_new_options=cfg["accept_new_options"],
                max_selections=cfg["max_selections"],
                select_all=cfg["select_all"],
                placeholder=cfg["placeholder"] or None,
                height=cfg["height"],
                item_height=cfg["item_height"],
                content_font_size=cfg["content_font_size"],
                width=cfg["width"],
                show_grid_lines=cfg["show_grid_lines"],
                help=cfg["help"] or None,
                disabled=cfg["disabled"],
                label_visibility=cfg["label_visibility"],
                on_change=data.make_on_change() if cfg["on_change"] else None,
                key=widget_key,
            )
        except ValueError as exc:
            st.error(f"listview raised: {exc}", icon=":material/error:")
            st.stop()

    with demo_col:
        if cfg["sidebar"]:
            st.caption("↩ The live widget is rendered in the sidebar.")

        if source.empty_caption:
            st.caption(
                "No options → the list shows the **placeholder** text "
                "(set it under Basic ▸ Placeholder)."
            )

        if large_build_ms is not None:
            st.caption(
                f"Built and indexed {len(options):,} items in {large_build_ms:.1f} ms "
                "(server-side: generate + derive ids/groups, cached per size — only "
                "the first rerun at a given size pays the full cost). Scroll, "
                "search, and select to feel the frontend response."
            )

        if cfg["on_change"]:
            st.caption(
                f"on_change fired {st.session_state['demo_change_count']} time(s)."
            )

        if has_selection(selected):
            count = len(selected) if isinstance(selected, list) else 1
            st.success(f"{count} selected", icon=":material/check_circle:")
            if isinstance(selected, (dict, list)):
                st.json(selected)
            else:
                # Single mode returns the option itself; a new option (added via
                # accept_new_options) comes back as the plain typed string.
                # st.json() treats a bare string as serialized JSON and tries to
                # parse it on the frontend, so render scalars with st.write.
                st.write(selected)
            # Reset sits with the result so it reads as an action on the current
            # selection, and only shows once something is selected.
            if st.button(
                "Reset selection",
                icon=":material/restart_alt:",
                help="Clears the live selection. If a Default is configured, the widget re-seeds to it.",
                key="cfg_reset",
            ):
                # Bump the nonce so the widget key changes and the component
                # remounts — the only way to clear its frontend-held selection.
                # (Popping the key clears the stale Python-side value too.)
                st.session_state.pop(widget_key, None)
                st.session_state["demo_reset_nonce"] += 1
                st.session_state["demo_change_count"] = 0
                # Flag the reset so the next run can explain a re-seeded Default.
                st.session_state["demo_just_reset"] = True
                st.rerun()
        else:
            st.caption("Nothing selected yet.")

        # After a reset, the widget re-seeds to its configured Default, so the
        # list won't be empty if one is set. Explain that here so the lingering
        # selection doesn't look like the reset failed.
        if st.session_state.get("demo_just_reset"):
            st.session_state["demo_just_reset"] = False
            d = cfg["default"]
            # Same "is this a real value, not just a falsy one" question the
            # selection above asks, and the same falsy-id trap (id 0 / "") — so
            # reuse the one helper that encodes it.
            if has_selection(d):
                shown = ", ".join(map(str, d)) if isinstance(d, list) else str(d)
                st.info(
                    "Reset re-seeded the list to the configured **Default** "
                    f"(`{shown}`), so it isn't empty. Clear the Default under "
                    "**Basic ▸ Default** to reset to nothing.",
                    icon=":material/info:",
                )

        st.subheader(":material/code: Generated code")
        st.code(build_snippet(cfg, options, builtin), language="python")


def render_api():
    st.subheader(":material/menu_book: API reference")

    st.markdown("#### Function signature")
    st.code(SIGNATURE, language="python")

    st.markdown("#### Parameters")
    st.dataframe(
        pd.DataFrame(PARAMS),
        column_config={
            "Parameter": st.column_config.TextColumn(width="small"),
            "Type": st.column_config.TextColumn(width="small"),
            "Default": st.column_config.TextColumn(width="small"),
            "Description": st.column_config.TextColumn(width="large"),
        },
        hide_index=True,
        width="stretch",
        # "content" sizes the frame to fit every row, so the whole parameter list
        # is visible without an inner scrollbar (the "auto" default caps the
        # table at ten rows).
        height="content",
    )

    st.markdown("#### Return value")
    st.markdown(RETURNS_MD)

    st.markdown("#### Examples")
    examples = [
        (
            ":material/radio_button_checked: Basic single selection",
            "single.py",
            "The simplest case: a list of strings, single selection.",
        ),
        (
            ":material/settings: Behavior: limits, new options & disabled",
            "behavior.py",
            "Cap picks with max_selections, let users add their own with "
            "accept_new_options, and lock the list with disabled.",
        ),
        (
            ":material/account_tree: Groups, search & collapsing",
            "grouped.py",
            "Multi-select with grouped, searchable, collapsible options and a pinned search field.",
        ),
        (
            ":material/bolt: Formatting & Events",
            "events.py",
            "Transform labels with format_func and react to changes with a native callback.",
        ),
    ]
    for title, fname, desc in examples:
        with st.expander(title):
            st.caption(desc)
            st.code(
                (DEMO_DIR / "examples" / fname).read_text(encoding="utf-8"),
                language="python",
            )


st.title(f":material/list: Listview Demo :primary-badge[v{LISTVIEW_VERSION}]")
st.caption("An interactive, themeable selection list for Streamlit.")

demo_tab, api_tab = st.tabs(
    [":material/play_circle: Demo", ":material/menu_book: API reference"],
    on_change="rerun",
)
if demo_tab.open:
    with demo_tab:
        render_demo()
if api_tab.open:
    with api_tab:
        render_api()
