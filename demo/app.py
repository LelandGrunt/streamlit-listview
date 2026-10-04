"""listview interactive demo — run with: streamlit run demo/app.py"""

import os
import re
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd
import streamlit as st

# Make sibling modules importable regardless of the working directory.
DEMO_DIR = Path(__file__).resolve().parent
LOGO_DIR = DEMO_DIR.parent / "assets" / "logo"
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

import data  # noqa: E402
from codegen import DEPENDENT_PARAMS, build_snippet  # noqa: E402
from parsing import coerce_multi_default, coerce_single_default, has_selection  # noqa: E402

import dataset  # noqa: E402
import themes  # noqa: E402

from streamlit_listview import listview  # noqa: E402

try:
    LISTVIEW_VERSION = version("streamlit-listview")
except PackageNotFoundError:  # running from source without an installed dist
    LISTVIEW_VERSION = "dev"

CHANGELOG_URL = "https://github.com/LelandGrunt/streamlit-listview/blob/main/CHANGELOG.md"

st.set_page_config(
    page_title="Listview · Component Demo",
    # The SVG favicon switches between its light and dark colors by itself,
    # following the browser's color-scheme preference.
    page_icon=str(LOGO_DIR / "favicon.svg"),
    layout="wide",
)

# Streamlit's main content area carries a large default top padding (6rem / 96px
# in wide layout), leaving a tall empty band above the title even though the
# fixed top header is only ~60px tall. There's no config.toml option for
# block-container padding, so trim it with a small CSS rule. 3rem still clears
# the header comfortably without the wasted space.
st.html("<style>.stMainBlockContainer { padding-top: 3rem; }</style>")


def adaptive_logo(name):
    """The light SVG, given the dark variant's fills under a dark color scheme.

    The two variants differ only in their fills. An SVG shown as an image takes
    its prefers-color-scheme from the color-scheme Streamlit sets on the app
    root, so the logo follows a theme change in the browser at once.
    st.context.theme cannot: a rerun the script starts itself (the Theme
    picker's) reuses the browser's previous report.
    """
    light = (LOGO_DIR / f"{name}.svg").read_text(encoding="utf-8")
    dark = (LOGO_DIR / f"{name}-dark.svg").read_text(encoding="utf-8")
    fill = re.compile(r'fill="(#[0-9A-Fa-f]+)"')
    swaps = dict(zip(fill.findall(light), fill.findall(dark)))
    rules = "".join(f'[fill="{a}"]{{fill:{b}}}' for a, b in swaps.items() if a != b)
    style = f"<style>@media (prefers-color-scheme:dark){{{rules}}}</style>"
    return light.replace("<defs>", style + "<defs>", 1)


st.logo(
    adaptive_logo("listview-logo"),
    icon_image=adaptive_logo("listview-mark"),
    link="https://github.com/LelandGrunt/streamlit-listview",
)

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
    "format_preset": None,
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

# The switchable themes: every demo/.streamlit/config_theme_<name>.toml, shown
# under its display name from config_themes.json (or its bare name without one).
THEMES = themes.discover_themes(DEMO_DIR / ".streamlit")
THEME_LABELS = themes.theme_labels(DEMO_DIR / ".streamlit")
# The Theme picker's entry for "no theme file". A real option, not None: a
# selectbox renders a None value as an empty field, not as an entry.
DEFAULT_THEME = "Streamlit default"
# A deployment can switch the picker off (LISTVIEW_DEMO_THEME_SWITCHER=0, e.g. as
# a Community Cloud secret). Read on every rerun, so a changed secret applies
# without a restart.
THEME_SWITCHER = themes.switcher_enabled(os.environ)

# Streamlit sends a run's theme before the script (and its widget callbacks) has
# run, so a theme switched during this run reaches the browser only with the
# next one: either this session's own pick (_switch_theme) or the server theme
# falling back to the default, THEME_TTL after the last switch or at once when
# the picker was switched off.
if themes.SERVER_THEME.expire(
    now=datetime.now(timezone.utc), enabled=THEME_SWITCHER
):
    st.rerun()
if st.session_state.pop("demo_theme_switched", False):
    st.rerun()

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

# Rows inserted by the "Insert example with fields" button, and loaded by the
# "Load an example without labels" button an inert preset offers. Deliberately
# carry NO `label`: an explicit label wins over format_func, so a labelled row
# would make every preset inert. `text` and `type` feed the "Type badge (custom
# field)" preset, which builds the label out of fields the widget never renders;
# the ids are words, not numbers, because the other presets transform the id —
# and UPPERCASE, Title Case or Truncate of the id 1 all still read "1".
CUSTOM_EXAMPLE_FIELDS = (
    "[\n"
    '  {"id": "orders", "text": "Orders", "type": "Table"},\n'
    '  {"id": "orders_view", "text": "OrdersView", "type": "View"}\n'
    "]"
)


def _insert_custom_example(text):
    """Fill the Custom options text area with an example row (button callback)."""
    st.session_state["cfg_options_text"] = text


def _load_label_free_example():
    """Switch Data to Custom with the label-less rows (button callback).

    Offered next to the live widget, usually while the Data section is
    off-screen, so it writes the persisted cfg values resolve_dataset reads
    rather than relying on the Data widgets to carry them over.
    """
    cfg = st.session_state["demo_config"]
    cfg["data_source"] = "Custom"
    cfg["options_text"] = CUSTOM_EXAMPLE_FIELDS
    # Drop both Data widgets' own state so each re-seeds from cfg when it next
    # renders. Assigning the keys instead does not work: the source control
    # seeds from default=cfg[...] (Streamlit warns about a widget given both),
    # and a text-area key assigned while its widget is off-screen reaches the
    # browser as the widget default — an EMPTY field on returning to Data —
    # because only a value set in the same run as the render is pushed to the
    # frontend. render_data's setdefault is such a same-run write.
    st.session_state.pop("cfg_data_source", None)
    st.session_state.pop("cfg_options_text", None)


def _set_multi_default(values):
    """Pre-fill the multi-mode Default multiselect with a sample list (button cb)."""
    st.session_state["cfg_default_multi"] = list(values)


def _switch_theme():
    """Apply the Theme picker's choice to the whole server (selectbox callback)."""
    # Callbacks see the raw client value before the selectbox validates it, so
    # switch only to a theme this deployment offers.
    name = st.session_state["cfg_theme"]
    if not THEME_SWITCHER or (name != DEFAULT_THEME and name not in THEMES):
        return
    if name == DEFAULT_THEME:
        themes.SERVER_THEME.reset()
    else:
        options = themes.flatten_theme(THEMES[name].read_text(encoding="utf-8"))
        themes.SERVER_THEME.apply(name, options, now=datetime.now(timezone.utc))
    st.session_state["demo_theme_switched"] = True


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
                "Rows with no `label`, so every **Formatting** preset labels "
                "them. They carry their own `text` and `type` fields: pick "
                "**Type badge (custom field)** to see `format_func` build each "
                "label out of those fields."
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
        # "No default" is the selectbox's own empty state — index=None, shown as
        # the placeholder and cleared with its x — not a None entry among the
        # options. Streamlit serializes a None *value* as "no selection", so a
        # None option rendered as an EMPTY field whenever Streamlit pushed it:
        # resetting an id that left the options (the "Load an example without
        # labels" button swaps them while this section is on screen) or a key
        # assigned below. Keeping None out of the options also keeps it out of
        # the id namespace, so a pasted id "— none —" is a normal default.
        #
        # Driven through its key, like the multiselect below: seed from the
        # persistent cfg default when the key was cleared while the section was
        # off-screen, and drop an id that is no longer an option.
        prior = st.session_state.get("cfg_default_single", cfg["default"])
        st.session_state["cfg_default_single"] = coerce_single_default(prior, ids)
        cfg["default"] = st.selectbox(
            "Default",
            ids,
            index=None,
            placeholder="— none —",
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


def render_theme(cfg, ids, groups):
    server = themes.SERVER_THEME
    st.info(
        "**A showcase, not part of the listview API.** Switching the theme "
        "doesn't change the generated code: it only shows that the listview is "
        "themeable, and how its style adapts to the theme Streamlit is "
        "configured with.",
        icon=":material/info:",
    )
    # The picker shows the SERVER's theme, never this session's last pick:
    # another session may have switched since, and a stale pick must not read as
    # the theme on screen. Only a change made here (on_change) switches it.
    st.session_state["cfg_theme"] = (
        DEFAULT_THEME if server.active is None else server.active
    )
    st.selectbox(
        "Theme",
        [DEFAULT_THEME, *THEMES],
        format_func=lambda name: THEME_LABELS.get(name, name),
        help=(
            "A theme file from `demo/.streamlit/` (`config_theme_<name>.toml`), "
            "named in `config_themes.json`. "
            "The listview has no theme parameter: it inherits the theme Streamlit "
            "is configured with."
        ),
        key="cfg_theme",
        on_change=_switch_theme,
    )
    st.caption(
        ":material/public: Applies to the **whole server**: every open session "
        "picks it up on its next rerun, because a Streamlit theme is server "
        "config, not session state."
    )
    if server.active is None:
        st.caption(
            "Streamlit's built-in theme, plus whatever `.streamlit/config.toml` "
            "sets. Pick a theme file to re-theme the app and watch the listview "
            "follow."
        )
        return

    st.caption(
        f":material/schedule: Falls back to *Streamlit default* on "
        f"{server.expires_at:%Y-%m-%d %H:%M} UTC, "
        f"{themes.THEME_TTL.total_seconds() / 3600:g}\u00a0h after the last switch."
    )
    text = THEMES[server.active].read_text(encoding="utf-8")
    if themes.theme_variants(themes.flatten_theme(text)) == ["light", "dark"]:
        st.caption(
            ":material/contrast: This theme defines a light and a dark variant: "
            "switch between them in the app menu (**⋮**, top right)."
        )
    st.markdown("Saved as `.streamlit/config.toml`, this file is the whole setup:")
    st.code(text, language="toml")


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
    # "No sort" is the selectbox's own empty state, as for the single-mode
    # Default picker (see render_basic): an empty field is sort=None. A None
    # option misrendered here as well — Streamlit treats a keyed selectbox whose
    # stored value is None as index=None on the next rerun, so "— none —" grew
    # a clear x that emptied the field to "Choose an option" for the same value.
    #
    # Always index=None, so the x stays available to clear a chosen sort; the
    # key carries the value, seeded from cfg when it was cleared while the
    # section was off-screen. Assigned on EVERY run, as the Default picker does,
    # not setdefault-ed: only an assigned key is pushed to the browser, and with
    # index=None nothing else tells a remounted field its value. Seeded once,
    # quick section switches dropped that one push — the field came back empty
    # while cfg kept the sort, and the next run read the empty field back.
    sort_choices = ["items", "groups", "both"]
    prior = st.session_state.get("cfg_sort", cfg["sort"])
    st.session_state["cfg_sort"] = prior if prior in sort_choices else None
    cfg["sort"] = st.selectbox(
        "Sort",
        sort_choices,
        index=None,
        placeholder="— none —",
        help=(
            "Alphabetically sort items, group headers, or both "
            "(by displayed label / group name, case-insensitive). "
            "Clear it to keep input order."
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
    # Same empty state, driven the same way, as Sort (see render_sorting): an
    # empty field is format_func=None, listview's default. A name a live session
    # kept from an earlier preset list (the old "None" entry) seeds the empty
    # state rather than an unknown value.
    preset_names = list(data.FORMAT_PRESETS)
    prior = st.session_state.get("cfg_format_preset", cfg["format_preset"])
    st.session_state["cfg_format_preset"] = (
        prior if prior in preset_names else None
    )
    cfg["format_preset"] = st.selectbox(
        "Label formatting (format_func)",
        preset_names,
        index=None,
        placeholder="— none —",
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
    # Whether the chosen preset changes anything is only known once listview
    # has run, so render_demo reports an inert preset next to the live widget.
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
    "Theme": ("format_paint", render_theme),
}


def render_demo():
    demo_col, config_col = st.columns([2, 1], gap="large")

    # Render configuration first so the demo column knows the option ids/groups.
    #
    # The inner st.container() is load-bearing. Since Streamlit 1.63, st.pills
    # and st.segmented_control placed *directly* in a column default to
    # wrap=False: one row that scrolls horizontally with its scrollbar hidden,
    # so on a narrow screen the trailing section pills are simply cut off with
    # nothing hinting that they exist. Nested one container deeper they wrap
    # again — every control in the panel at once, and unlike passing wrap=True
    # (a 1.63+ parameter) it keeps the demo running on the Streamlit >= 1.51
    # floor.
    with config_col, st.container():
        st.subheader(":material/tune: Configuration")
        # A switched-off Theme picker drops out of the pills; a session still
        # on it falls back to the default section (st.pills resets a value
        # that is no longer among its options).
        section = st.pills(
            "Configuration section",
            [name for name in SECTIONS if THEME_SWITCHER or name != "Theme"],
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
    # .get: None is "no formatter", and so is a name no longer in the presets.
    fmt = data.FORMAT_PRESETS.get(cfg["format_preset"])
    # The live call gets the preset wrapped, so the demo learns whether listview
    # consulted it for any option (codegen still emits the bare preset).
    fmt_probe = None if fmt is None else data.FormatProbe(fmt)

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
                format_func=fmt_probe,
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

        # A preset listview never called changed nothing on screen: every option
        # carried its own label. Say so, rather than letting the control look
        # broken, and offer rows it can label.
        if fmt_probe is not None and options and fmt_probe.calls == 0:
            st.warning(
                f"The **{cfg['format_preset']}** preset has no effect here: every "
                "option carries its own `label`, and an explicit label always wins "
                "over `format_func`. The formatter only labels options without one.",
                icon=":material/label_off:",
            )
            st.button(
                "Load an example without labels",
                icon=":material/dataset:",
                on_click=_load_label_free_example,
                help=(
                    "Switch **Data** to **Custom** with rows that carry no "
                    "`label`, so the preset labels them."
                ),
                key="demo_load_label_free_example",
            )

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


st.title(
    f":material/list: Listview Demo [:primary-badge[v{LISTVIEW_VERSION}]]({CHANGELOG_URL})"
)
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
