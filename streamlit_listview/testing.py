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
from streamlit.testing.v1 import AppTestError
from streamlit.testing.v1.element_tree import UnknownElement

from . import _COMPONENT_NAME
from ._options import _id_key, _validate_id

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

    def set_selection(
        self, ids: str | int | list[str | int] | tuple[str | int, ...] | None
    ) -> ListviewElement:
        """Store a selection that a browser user could make, for the next run.

        ``ids`` is one id, a list or a tuple of ids, or ``None`` to clear the
        selection. Each id is written in its option's own spelling. Raises
        ``AppTestError`` for a selection no browser user can make, and
        ``ValueError`` for an id that is not a ``str`` or an ``int``. Call
        ``run()`` next; the stored selection fires no ``on_change``.
        """
        if self.disabled:
            raise AppTestError(
                f"Cannot change the disabled listview {self.key!r}: a browser "
                "user cannot interact with it."
            )
        chosen = self._options_for(_as_ids(ids))
        self._check_count(len(chosen))
        self._at.session_state[self.key] = {
            "selection": [option.id for option in chosen]
        }
        return self

    def run(self, *, timeout: float | None = None) -> AppTest:
        """Run the app again, as ``at.run()`` does, and return the AppTest."""
        return self._at.run(timeout=timeout)

    def _options_for(self, ids: list[Any]) -> list[Option]:
        """The option of each id, or AppTestError for an id no user can pick.

        Ids match options by ``_id_key``, the row identity of the frontend. A
        disabled option may stay when the stored selection holds it: the
        browser locks such a row instead of dropping it.
        """
        by_key = {_id_key(option.id): option for option in self.options}
        held = {_id_key(item_id) for item_id in self.selection}
        chosen: list[Option] = []
        for item_id in ids:
            _validate_id(item_id, kind="selected")
            option = by_key.get(_id_key(item_id))
            if option is None:
                raise AppTestError(self._unknown(item_id))
            if option in chosen:
                raise AppTestError(
                    f"Listview {self.key!r} got the option {item_id!r} twice."
                )
            if option.disabled and _id_key(option.id) not in held:
                raise AppTestError(
                    f"Cannot select the disabled option {item_id!r} in listview "
                    f"{self.key!r}: a browser user cannot pick it."
                )
            chosen.append(option)
        return chosen

    def _unknown(self, item_id: Any) -> str:
        """The message for an id that names no option."""
        message = f"Listview {self.key!r} has no option {item_id!r}."
        if self.accept_new_options:
            message += (
                " set_selection adds no new entries, even with accept_new_options."
            )
        return message

    def _check_count(self, count: int) -> None:
        """Raise AppTestError when the mode allows fewer ids than ``count``."""
        if self.selection_mode == "single" and count > 1:
            raise AppTestError(
                f"Listview {self.key!r} has selection_mode='single' and takes one "
                f"id, got {count}."
            )
        if self.max_selections is not None and count > self.max_selections:
            raise AppTestError(
                f"Listview {self.key!r} allows max_selections={self.max_selections} "
                f"ids, got {count}."
            )


def _as_ids(ids: Any) -> list[Any]:
    """``ids`` as a list: ``None`` is empty, a list or a tuple is its items."""
    if ids is None:
        return []
    if isinstance(ids, (list, tuple)):
        return list(ids)
    return [ids]


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
