"""Take, Scenario and the Stage helper that the GIF scenarios drive the page with.

A Scenario describes one capture: the Streamlit page it renders, the steps that
drive it, and its takes (one server run each). A Stage wraps the Playwright page
while one take plays, and records its frames. Playwright is imported for type
checking only, so the capture page (app.py) imports this module without loading
Playwright.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.sync_api import FloatRect, Locator, Page

# Room around the listview's box in every frame, in CSS pixels.
CLIP_PAD = 12
# settle() waits for this many animation frames without a DOM mutation, a
# scroll event or a loading stylesheet in the listview's shadow tree. Five
# frames cover the two-frame forget cycle of useResetChunkHeights and the wait
# of up to four frames in scrollToId.
QUIET_FRAMES = 5
SETTLE_TIMEOUT_MS = 10_000
# rerun() waits this long for the script run to finish: a click on a
# 100,000-row list resends 6.7 MB of options.
RERUN_TIMEOUT_MS = 60_000

# Resolves once the fonts have loaded and the listview's shadow tree has seen no
# DOM mutation, no scroll event and no loading stylesheet for `quietFrames`
# animation frames. A remounted listview gets a new shadow root whose stylesheet
# applies a frame or more after its first render; until then its rows are
# unstyled. A key-change remount also leaves the shadow root without the
# listview for about a frame after its script run ends, so the lookup repeats
# once per frame until the listview appears.
_SETTLE_JS = """
async ([quietFrames, timeoutMs]) => {
  await document.fonts.ready;
  const started = performance.now();
  const findHost = () =>
    [...document.querySelectorAll("*")].find(
      (el) => el.shadowRoot?.querySelector('[data-testid="stListview"]'),
    );
  let host = findHost();
  while (!host) {
    if (performance.now() - started > timeoutMs) {
      throw new Error(`settle: no listview on the page after ${timeoutMs} ms`);
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
    host = findHost();
  }
  const root = host.shadowRoot;
  let dirty = false;
  const mark = () => {
    dirty = true;
  };
  const observer = new MutationObserver(mark);
  observer.observe(root, {
    subtree: true,
    childList: true,
    attributes: true,
    characterData: true,
  });
  root.addEventListener("scroll", mark, true);
  const loading = () =>
    [...root.querySelectorAll('link[rel="stylesheet"]')].some((link) => !link.sheet);
  try {
    let quiet = 0;
    while (quiet < quietFrames) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      quiet = dirty || loading() ? 0 : quiet + 1;
      dirty = false;
      if (performance.now() - started > timeoutMs) {
        throw new Error(`settle: the listview did not go quiet in ${timeoutMs} ms`);
      }
    }
  } finally {
    observer.disconnect();
    root.removeEventListener("scroll", mark, true);
  }
}
"""


# Shows a key in a badge at a page position, or removes the badge for null. The
# badge lives in the page, outside the listview's shadow tree, so settle() does
# not wait for it.
_BADGE_JS = """
([text, right, top]) => {
  let badge = document.getElementById("gif-key-badge");
  if (text === null) {
    badge?.remove();
    return;
  }
  if (!badge) {
    badge = document.createElement("div");
    badge.id = "gif-key-badge";
    Object.assign(badge.style, {
      position: "fixed",
      zIndex: "2147483647",
      transform: "translateX(-100%)",
      padding: "2px 10px",
      borderRadius: "6px",
      background: "rgba(38, 39, 48, 0.88)",
      color: "#ffffff",
      font: "600 14px/20px system-ui, sans-serif",
      pointerEvents: "none",
    });
    document.body.appendChild(badge);
  }
  badge.textContent = text;
  badge.style.left = `${right}px`;
  badge.style.top = `${top}px`;
}
"""

# How the key badge spells a key; any other key shows as itself.
KEY_LABELS = {"ArrowDown": "↓", "ArrowUp": "↑", "Escape": "Esc"}


@dataclass(frozen=True)
class Take:
    """One server run of a scenario.

    ``server_args`` are extra ``streamlit run`` flags, such as a theme.
    ``clip_top`` adds that many CSS pixels above the listview to the frame, for
    content that opens above it, such as the help popover.
    """

    name: str = "main"
    server_args: tuple[str, ...] = ()
    clip_top: int = 0


@dataclass(frozen=True)
class Scenario:
    """One capture: a Streamlit page, the steps that drive it, and its takes.

    ``page(take)`` renders the page for the named take; ``play(stage)`` drives it,
    once per take. A gallery scenario writes ``assets/<gif_file>``; a test
    scenario is only recorded.
    """

    name: str
    title: str
    gallery: bool
    page: Callable[[str], None]
    play: Callable[[Stage], None]
    takes: tuple[Take, ...] = (Take(),)
    page_config: Mapping[str, Any] = field(default_factory=dict)
    gif_name: str = ""

    @property
    def gif_file(self) -> str:
        """The GIF's file name in assets/."""
        return self.gif_name or f"listview-{self.name}.gif"


def clip_for(
    box: Mapping[str, Any],
    *,
    top: int = 0,
    size: tuple[float, float] | None = None,
) -> FloatRect:
    """The screenshot clip around a listview's box.

    ``CLIP_PAD`` pixels on every side and ``top`` more above. The clip never
    starts above or left of the page. ``size`` (an earlier take's) keeps that
    frame size, anchored at this box's corner, so a smaller widget shows a little
    more of the page; a larger one raises ValueError, because the frame would cut
    it off.
    """
    width = box["width"] + 2 * CLIP_PAD
    height = box["height"] + 2 * CLIP_PAD + top
    if size is not None:
        if width > size[0] or height > size[1]:
            raise ValueError(
                f"the frame is {width:g}x{height:g} CSS px, larger than the first "
                f"take's {size[0]:g}x{size[1]:g}; put the take with the largest "
                "widget first"
            )
        width, height = size
    return {
        "x": max(box["x"] - CLIP_PAD, 0),
        "y": max(box["y"] - CLIP_PAD - top, 0),
        "width": width,
        "height": height,
    }


def run_count(page: Page) -> int:
    """The capture page's run counter: how many script runs have finished."""
    return int(page.locator(".gif-run").get_attribute("data-run") or 0)


def settle(page: Page) -> None:
    """Wait for the fonts and the listview, then for QUIET_FRAMES quiet frames.

    Fails when the listview has not appeared and gone quiet in SETTLE_TIMEOUT_MS.
    """
    page.evaluate(_SETTLE_JS, [QUIET_FRAMES, SETTLE_TIMEOUT_MS])


class Stage:
    """Drives one take of a scenario and records its frames.

    ``frames`` is the scenario's manifest: every take appends to the same list,
    and generate.py writes it to frames.json.
    """

    def __init__(
        self,
        page: Page,
        take: Take,
        out_dir: Path,
        frames: list[dict[str, Any]],
        clip: FloatRect,
    ) -> None:
        self.page = page
        self.take = take.name
        self.clip = clip
        self.last_step = "(none)"
        self._out_dir = out_dir
        self._frames = frames
        self._steps: set[str] = set()

    # Locators. They use the component's data-testids and classes; Playwright's
    # CSS engine pierces the shadow root.

    def opt(self, item_id: str | int) -> Locator:
        """The row of the option with this id."""
        return self.page.locator(f'[data-testid="stListviewOption-{item_id}"]')

    def group(self, name: str) -> Locator:
        """The header of the group with this name."""
        return self.page.locator('[data-testid="stListviewGroup"]', has_text=name)

    @property
    def search(self) -> Locator:
        """The search field."""
        return self.page.locator('[data-testid="stListviewSearch"]')

    @property
    def search_clear(self) -> Locator:
        """The search field's clear button."""
        return self.page.locator('[data-testid="stListviewSearchClear"]')

    @property
    def select_all(self) -> Locator:
        """The Select all / Deselect all toggle."""
        return self.page.locator('[data-testid="stListviewSelectAllToggle"]')

    @property
    def new_option(self) -> Locator:
        """The add-option field (accept_new_options)."""
        return self.page.locator('[data-testid="stListviewNewOption"]')

    @property
    def help_icon(self) -> Locator:
        """The help tooltip's trigger beside the label."""
        return self.page.locator(".listview-help-trigger")

    def control(self, label: str) -> Locator:
        """An option of the scenario's preset switch, a horizontal st.radio."""
        return self.page.locator('[data-testid="stRadio"]').get_by_text(
            label, exact=True
        )

    # Waiting.

    def settle(self) -> None:
        """Wait until the listview is quiet; see the module function settle()."""
        settle(self.page)

    @contextmanager
    def rerun(self) -> Generator[None]:
        """Run the enclosed action, then wait until the script run it caused ends."""
        before = run_count(self.page)
        yield
        self.page.wait_for_function(
            "n => Number(document.querySelector('.gif-run')?.dataset.run) > n",
            arg=before,
            timeout=RERUN_TIMEOUT_MS,
        )
        self.settle()

    # Keys.

    def badge(self, text: str | None) -> None:
        """Show ``text`` in a badge at the listview's top-right; None removes it."""
        box = self.page.locator('[data-testid="stListview"]').first.bounding_box()
        if box is None:
            raise RuntimeError("the listview has no box")
        self.page.evaluate(_BADGE_JS, [text, box["x"] + box["width"], box["y"]])

    def press(self, key: str, *, badge: bool = False) -> None:
        """Press ``key``; with ``badge`` show it in the key badge first."""
        if badge:
            self.badge(KEY_LABELS.get(key, key))
        self.page.keyboard.press(key)

    def park_pointer(self) -> None:
        """Move the pointer to the page's top-left corner, away from the listview."""
        self.page.mouse.move(0, 0)

    def scroll_list(self, fraction: float) -> None:
        """Scroll the list to ``fraction`` of its range by setting scrollTop.

        Not the mouse wheel: it scrolls smoothly, so its end state comes late.
        """
        self.page.locator(".listview-body").evaluate(
            "(body, f) => { body.scrollTop = "
            "Math.round(f * (body.scrollHeight - body.clientHeight)); }",
            fraction,
        )

    # Frames.

    def snap(self, step: str, ms: int) -> None:
        """Settle, then screenshot the clip as the frame of ``step``, shown ``ms`` ms."""
        if step in self._steps:
            raise ValueError(f"step {step!r} appears twice in take {self.take!r}")
        self._steps.add(step)
        self.settle()
        name = f"frame_{len(self._frames):03d}.png"
        self.page.screenshot(
            path=str(self._out_dir / name), clip=self.clip, animations="disabled"
        )
        self._frames.append({"file": name, "ms": ms, "take": self.take, "step": step})
        self.last_step = step
