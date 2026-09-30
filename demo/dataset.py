"""Resolve the configured data source into options for the live listview.

Side-effect-free apart from the ``st.cache_data`` memo below, so it can be
unit-tested and reused while the Data section is off-screen in the demo's section
switcher.
"""
from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st

import data
from parsing import group_names, option_ids, parse_options_text


def _derived(options):
    """The ``(options, ids, groups)`` triple a resolver returns."""
    return options, option_ids(options), group_names(options)


@st.cache_data(show_spinner=False)
def _large_dataset(n):
    """Build the Large dataset plus its derived ids/groups, memoized on ``n``.

    resolve_dataset runs on every rerun, and at the size slider's 10,000 max this
    is the demo's dominant server-side cost: 10k dicts and ~30k f-strings, then
    two more full walks to derive the ids and the group names. All three are pure
    functions of ``n``, so build them once per size. ``st.cache_data`` hands back a
    fresh copy on every call, so nothing downstream can poison the cache.
    """
    return _derived(data.make_large_dataset(n))


@dataclass(frozen=True)
class DataSource:
    """One demo data source: its resolver plus the traits consumers branch on.

    ``resolve`` maps the config to the ``(options, ids, groups)`` triple. Each
    trait exists because a consumer used to compare source *names* there; the
    traits are what those branches actually meant:

    - ``builtin``: the built-in city dataset — resolve_dataset's 4th element,
      which drives codegen's options-block abbreviation.
    - ``options_editor``: render_data shows the paste-your-own text area and
      example buttons.
    - ``sized``: render_data shows the item-count slider.
    - ``timed``: render_demo times the (cached) server-side build and reports it.
    - ``empty_caption``: render_demo points at the placeholder text.
    - ``snippet_comprehension``: codegen emits the generating comprehension
      instead of option literals.
    """

    resolve: Callable[[dict], tuple]
    builtin: bool = False
    options_editor: bool = False
    sized: bool = False
    timed: bool = False
    empty_caption: bool = False
    snippet_comprehension: bool = False


# Source name -> DataSource, in the order the Data section's segmented control
# offers them. This dict is the one dispatch: app.py builds the control's
# choices from its keys and reads the traits, and codegen branches on a trait —
# so an unknown name is a KeyError at the lookup, never a silent fallback
# (unreachable via the UI, whose choices come from this same dict).
DATA_SOURCES = {
    "Built-in cities": DataSource(
        resolve=lambda cfg: _derived(data.CITIES),
        builtin=True,
    ),
    "Custom": DataSource(
        resolve=lambda cfg: _derived(parse_options_text(cfg["options_text"])),
        options_editor=True,
    ),
    "Empty": DataSource(
        resolve=lambda cfg: _derived([]),
        empty_caption=True,
    ),
    "Large": DataSource(
        # Options and derivations come from one memo, so a rerun that only moved
        # an unrelated control doesn't rebuild them.
        resolve=lambda cfg: _large_dataset(cfg["large_size"]),
        sized=True,
        timed=True,
        snippet_comprehension=True,
    ),
}


def resolve_dataset(cfg):
    """Return ``(options, ids, groups, builtin)`` for the current config.

    ``ids`` are the selectable option ids; ``groups`` is the ordered, unique list
    of dict-option group names; ``builtin`` is ``True`` only for the built-in
    dataset (drives the generated-snippet abbreviation).
    """
    source = DATA_SOURCES[cfg["data_source"]]
    return *source.resolve(cfg), source.builtin
