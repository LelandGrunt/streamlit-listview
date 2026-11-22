"""Read and set a listview in a test that runs an app through Streamlit's AppTest.

``AppTest`` shows a listview as a generic element without ``set_value()``.
``get_listview(at, key)`` finds a keyed listview after ``at.run()`` and returns a
``ListviewElement``, which reads the listview's options and its selection.

The helper uses public Streamlit API only. It reaches keyed listviews only,
because it works through ``at.session_state[key]``. A selection it sets fires no
``on_change``, unlike ``set_value()`` on Streamlit's own widgets, and it adds no
new entries, even with ``accept_new_options``. It needs Streamlit 1.66: before
that, a selection written to ``at.session_state`` lasts one run only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

import streamlit
from streamlit.testing.v1.element_tree import UnknownElement

from . import _COMPONENT_NAME

if TYPE_CHECKING:
    from streamlit.testing.v1 import AppTest

_MIN_STREAMLIT = (1, 66)


def _streamlit_version(version: str) -> tuple[int, ...]:
    """Major and minor of a Streamlit version, a dev release included."""
    return tuple(int(number) for number in re.findall(r"\d+", version)[:2])


if _streamlit_version(streamlit.__version__) < _MIN_STREAMLIT:
    raise ImportError(
        "streamlit_listview.testing needs Streamlit 1.66 or later; found "
        f"{streamlit.__version__}."
    )


@dataclass(frozen=True)
class Option:
    """One option of a listview, as the listview ships it to the browser."""

    id: str | int
    label: str
    group: str | None
    disabled: bool


class ListviewElement:
    """A keyed listview in an AppTest, as the last run rendered it."""

    def __init__(self, at: AppTest, element: UnknownElement) -> None:
        payload = json.loads(element.proto.json)
        self._at = at
        # get_listview passes keyed elements only.
        self.key: str = cast("str", element.key)
        self.label: str = payload["label"]
        self.disabled: bool = payload["disabled"]
        self.selection_mode: Literal["single", "multi"] = payload["selection_mode"]
        self.max_selections: int | None = payload["max_selections"]
        self.accept_new_options: bool = payload["accept_new_options"]
        self.options: list[Option] = [
            Option(
                id=item["id"],
                label=item["label"],
                group=item.get("group"),
                disabled=item.get("disabled", False),
            )
            for item in payload["items"]
        ]

    @property
    def selection(self) -> list[Any]:
        """The ids stored in ``at.session_state[key]``, read on each access.

        The value ``listview()`` returns can differ: it maps the stored ids to
        the options and corrects them against the current parameters.
        """
        return list(self._at.session_state[self.key]["selection"])


def get_listview(at: AppTest, key: str) -> ListviewElement:
    """The listview with ``key`` in the last run of ``at``.

    Raises ``KeyError`` when the last run rendered no listview with that key.
    """
    listviews = [
        element
        for element in at.get("bidi_component")
        if isinstance(element, UnknownElement)
        and element.proto.component_name == _COMPONENT_NAME
    ]
    for element in listviews:
        if element.key == key:
            return ListviewElement(at, element)
    keys = sorted(element.key for element in listviews if element.key is not None)
    message = f"No listview with key {key!r}; the keyed listviews are {keys}."
    if not listviews:
        message += " Call at.run() before get_listview()."
    raise KeyError(message)
