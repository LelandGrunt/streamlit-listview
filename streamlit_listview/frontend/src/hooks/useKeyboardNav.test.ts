import { describe, it, expect, vi } from "vitest";
import type { Mock } from "vitest";
import { createElement } from "react";
import {
  renderHook,
  act,
  render,
  screen,
  fireEvent,
  createEvent,
} from "@testing-library/react";
import { useKeyboardNav } from "./useKeyboardNav";
import type { Id, ListviewItem } from "../types";

const items: ListviewItem[] = [
  { id: "a", label: "A" },
  { id: "b", label: "B", disabled: true },
  { id: "c", label: "C" },
  { id: 4, label: "Four" },
];

type FakeKeyEvent = React.KeyboardEvent<HTMLDivElement> & {
  preventDefault: Mock;
};

/**
 * A keydown as the listbox really sees it: dispatched AT the listbox, because
 * rows are not focusable and so the listbox itself is what holds DOM focus.
 * Pass `target` to model a keydown that started in a focused descendant control
 * (the collapsible group-header button) and bubbled up.
 */
function keyEvent(key: string, target?: EventTarget): FakeKeyEvent {
  const listbox = document.createElement("div");
  return {
    key,
    target: target ?? listbox,
    currentTarget: listbox,
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
  } as unknown as FakeKeyEvent;
}

describe("useKeyboardNav", () => {
  it("starts with no focused item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    expect(result.current.focusedId).toBeNull();
  });

  it("ArrowDown focuses the first focusable item, then skips disabled ones", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(result.current.focusedId).toBe("a");
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    // "b" is disabled -> skipped -> "c"
    expect(result.current.focusedId).toBe("c");
  });

  it("ArrowUp moves focus backwards and stops at the first focusable item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe(4);
    act(() => result.current.onKeyDown(keyEvent("ArrowUp")));
    expect(result.current.focusedId).toBe("c");
    act(() => result.current.onKeyDown(keyEvent("ArrowUp")));
    expect(result.current.focusedId).toBe("a");
    act(() => result.current.onKeyDown(keyEvent("ArrowUp")));
    // already at first focusable -> stays
    expect(result.current.focusedId).toBe("a");
  });

  it("ArrowDown stops at the last focusable item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() => useKeyboardNav({ items, onSelect }));
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe(4);
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(result.current.focusedId).toBe(4);
  });

  it("Home focuses the first focusable item; End focuses the last focusable item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe(4);
    act(() => result.current.onKeyDown(keyEvent("Home")));
    expect(result.current.focusedId).toBe("a");
  });

  it("Enter selects the focused item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    act(() => result.current.onKeyDown(keyEvent("Enter")));
    expect(onSelect).toHaveBeenCalledWith("a");
  });

  it("Space selects the focused item and is treated the same as Enter", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    act(() => result.current.onKeyDown(keyEvent(" ")));
    expect(onSelect).toHaveBeenCalledWith(4);
  });

  it("Enter/Space with nothing focused does not call onSelect", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("Enter")));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("ignores unrelated keys without calling onSelect", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("a")));
    expect(result.current.focusedId).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("navigation keys are inert when there are no focusable items", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({
        items: [{ id: "x", label: "X", disabled: true }],
        onSelect,
      }),
    );
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(result.current.focusedId).toBeNull();
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("ArrowUp from an unfocused state jumps to the last focusable item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() => useKeyboardNav({ items, onSelect }));
    expect(result.current.focusedId).toBeNull();
    act(() => result.current.onKeyDown(keyEvent("ArrowUp")));
    expect(result.current.focusedId).toBe(4);
  });

  it("clamps a stale focus index when the items list shrinks", () => {
    const onSelect = vi.fn();
    const { result, rerender } = renderHook(
      ({ list }) => useKeyboardNav({ items: list, onSelect }),
      { initialProps: { list: items } },
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe(4);
    rerender({ list: [{ id: "a", label: "A" }] });
    // the focused row is gone -> focusedId resolves safely to null
    expect(result.current.focusedId).toBeNull();
  });

  it("after the focusable list shrinks, ArrowDown resumes from the top (not the stale tail)", () => {
    const onSelect = vi.fn();
    const { result, rerender } = renderHook(
      ({ list }) => useKeyboardNav({ items: list, onSelect }),
      { initialProps: { list: items } },
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe(4);
    // shrink so the previously focused row no longer exists
    rerender({ list: [{ id: "a", label: "A" }, { id: "c", label: "C" }] });
    expect(result.current.focusedId).toBeNull();
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    // resumes from the top, NOT Math.min(staleIndex + 1, last) -> last item
    expect(result.current.focusedId).toBe("a");
  });

  it("keeps roving focus on the same item when filtering removes items above it", () => {
    const onSelect = vi.fn();
    const full: ListviewItem[] = [
      { id: "a", label: "A" },
      { id: "b2", label: "B" },
      { id: "c", label: "C" },
      { id: "d", label: "D" },
      { id: "e", label: "E" },
      { id: "f", label: "F" },
      { id: "g", label: "G" },
    ];
    const { result, rerender } = renderHook(
      ({ list }) => useKeyboardNav({ items: list, onSelect }),
      { initialProps: { list: full } },
    );
    // Focus the 4th item (index 3) = "d".
    act(() => result.current.onKeyDown(keyEvent("ArrowDown"))); // a
    act(() => result.current.onKeyDown(keyEvent("ArrowDown"))); // b2
    act(() => result.current.onKeyDown(keyEvent("ArrowDown"))); // c
    act(() => result.current.onKeyDown(keyEvent("ArrowDown"))); // d
    expect(result.current.focusedId).toBe("d");
    // Filtering removes a, b2 (above d). "d" is still present, now at index 1.
    rerender({ list: full.slice(2) }); // [c, d, e, f, g]
    // Focus must follow the ITEM (d), not the stale index (which now resolves to f).
    expect(result.current.focusedId).toBe("d");
    act(() => result.current.onKeyDown(keyEvent("Enter")));
    expect(onSelect).toHaveBeenCalledWith("d");
  });

  it("setFocusToId sets focus when the id belongs to a focusable item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    expect(result.current.focusedId).toBeNull();
    act(() => result.current.setFocusToId("c"));
    expect(result.current.focusedId).toBe("c");
    // numeric id works too
    act(() => result.current.setFocusToId(4));
    expect(result.current.focusedId).toBe(4);
  });

  it("setFocusToId is a no-op when the id is disabled or does not exist", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect }),
    );
    // first move focus to a known item so we can verify it does not change
    act(() => result.current.setFocusToId("a"));
    expect(result.current.focusedId).toBe("a");

    // "b" is disabled -> not in focusable list -> no-op
    act(() => result.current.setFocusToId("b"));
    expect(result.current.focusedId).toBe("a");

    // completely unknown id -> no-op
    act(() => result.current.setFocusToId("nonexistent"));
    expect(result.current.focusedId).toBe("a");
  });

  it("resumes arrow navigation from a clicked row", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() => useKeyboardNav({ items, onSelect }));
    act(() => result.current.setFocusToId("c"));
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(result.current.focusedId).toBe(4);
  });
});

describe("slash and escape", () => {
  const items = [{ id: "a", label: "A" }, { id: "b", label: "B" }];

  it('"/" calls onSlash and prevents default', () => {
    const onSlash = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect: vi.fn(), onSlash }),
    );
    const event = keyEvent("/");
    act(() => result.current.onKeyDown(event));
    expect(onSlash).toHaveBeenCalledTimes(1);
    expect(event.preventDefault).toHaveBeenCalled();
  });

  it("Escape calls onEscape", () => {
    const onEscape = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect: vi.fn(), onEscape }),
    );
    act(() => result.current.onKeyDown(keyEvent("Escape")));
    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it("Escape without an onEscape handler does nothing (no throw)", () => {
    const { result } = renderHook(() => useKeyboardNav({ items, onSelect: vi.fn() }));
    const event = keyEvent("Escape");
    act(() => result.current.onKeyDown(event));
    expect(event.preventDefault).not.toHaveBeenCalled();
  });

  it('"/" without an onSlash handler does nothing (no throw)', () => {
    const { result } = renderHook(() => useKeyboardNav({ items, onSelect: vi.fn() }));
    const event = keyEvent("/");
    act(() => result.current.onKeyDown(event));
    expect(event.preventDefault).not.toHaveBeenCalled();
  });
});

describe("keys aimed at a focused descendant control", () => {
  /**
   * Mirrors the real DOM: the listbox keydown handler sits on an ANCESTOR of the
   * collapsible group-header <button>, and that button has no key handling of
   * its own — it relies on the browser turning Enter/Space into a click, which
   * a preventDefault() from up here would cancel.
   */
  function Harness({ onSelect }: { onSelect: (id: Id) => void }) {
    const nav = useKeyboardNav({ items, onSelect });
    return createElement(
      "div",
      { role: "listbox", tabIndex: 0, onKeyDown: nav.onKeyDown },
      createElement("button", { type: "button" }, "Fruit"),
    );
  }

  it("leaves Enter/Space on a nested button un-prevented and selects nothing", () => {
    const onSelect = vi.fn();
    render(createElement(Harness, { onSelect }));
    const listbox = screen.getByRole("listbox");
    // Arm the bug: a roving focus exists, so an Enter wrongly claimed by the
    // listbox would be observable as a selection of an unrelated row.
    fireEvent.keyDown(listbox, { key: "ArrowDown" });
    const button = screen.getByRole("button");
    for (const key of ["Enter", " "]) {
      const event = createEvent.keyDown(button, { key });
      fireEvent(button, event);
      // defaultPrevented is the whole mechanism: it is what used to stop the
      // browser from activating the button, so the group never collapsed.
      expect(event.defaultPrevented).toBe(false);
    }
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("ignores arrows, Escape and \"/\" that bubbled up from a nested control", () => {
    const onSelect = vi.fn();
    const onEscape = vi.fn();
    const onSlash = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect, onEscape, onSlash }),
    );
    const button = document.createElement("button");
    act(() => result.current.onKeyDown(keyEvent("ArrowDown", button)));
    expect(result.current.focusedId).toBeNull();
    // Deliberate: Escape must not clear the selection (nor "/" steal focus)
    // while a group-header button is what the user is operating.
    for (const key of ["Escape", "/"]) {
      const event = keyEvent(key, button);
      act(() => result.current.onKeyDown(event));
      expect(event.preventDefault).not.toHaveBeenCalled();
    }
    expect(onEscape).not.toHaveBeenCalled();
    expect(onSlash).not.toHaveBeenCalled();
  });
});

describe("scrolling the keyboard-focused row into view", () => {
  it("scrolls the row every focus-moving key lands on", () => {
    const scrollToId = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect: vi.fn(), scrollToId }),
    );
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(scrollToId).toHaveBeenLastCalledWith("a");
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(scrollToId).toHaveBeenLastCalledWith(4);
    act(() => result.current.onKeyDown(keyEvent("ArrowUp")));
    expect(scrollToId).toHaveBeenLastCalledWith("c");
    act(() => result.current.onKeyDown(keyEvent("Home")));
    expect(scrollToId).toHaveBeenLastCalledWith("a");
    expect(scrollToId).toHaveBeenCalledTimes(4);
  });

  it("does not scroll for a click-driven focus move or for keys that do not move focus", () => {
    const scrollToId = vi.fn();
    const onEscape = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ items, onSelect: vi.fn(), onEscape, scrollToId }),
    );
    // Clicking an already-visible row must not jog the list.
    act(() => result.current.setFocusToId("c"));
    act(() => result.current.onKeyDown(keyEvent("Enter")));
    act(() => result.current.onKeyDown(keyEvent("Escape")));
    act(() => result.current.onKeyDown(keyEvent("x")));
    expect(scrollToId).not.toHaveBeenCalled();
  });
});

describe("focus while the focusable list changes", () => {
  const full: ListviewItem[] = [
    { id: "a", label: "Alpha" },
    { id: "b", label: "Bravo" },
    { id: "c", label: "Charlie" },
    { id: "d", label: "Delta" },
  ];

  function setup(list: ListviewItem[]) {
    const seen: (Id | null)[] = [];
    const onSelect = vi.fn();
    const { result, rerender } = renderHook(
      ({ items: current }) => {
        const nav = useKeyboardNav({ items: current, onSelect });
        seen.push(nav.focusedId);
        return nav;
      },
      { initialProps: { items: list } },
    );
    return { seen, result, rerender, onSelect };
  }

  it("never reports the ring on a row the user did not focus, not even for one render", () => {
    const long: ListviewItem[] = [
      ...full,
      { id: "e", label: "Echo" },
      { id: "f", label: "Foxtrot" },
    ];
    const { seen, result, rerender } = setup(long);
    // Focus the 4th row, "Delta".
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(result.current.focusedId).toBe("d");
    seen.length = 0;
    // A filter (or a collapse toggle) drops the rows above it: "d" moves from
    // index 3 to index 1. An index-based focus reported index 3 of the NEW list
    // ("f") for the render that commits this change — a ring, and an Enter
    // target, on a row the user never focused — and corrected itself only in a
    // post-paint effect, one committed render later.
    rerender({ items: long.slice(2) });
    expect(seen).toEqual(["d"]);
  });

  it("hides the ring while the focused row is filtered away and restores it after", () => {
    const { seen, result, rerender } = setup(full);
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe("d");
    // "Delta" filtered out: nothing is focused, but the id is remembered...
    rerender({ items: full.slice(0, 3) });
    expect(result.current.focusedId).toBeNull();
    // ...so backing the query out puts the ring back where the user left it.
    seen.length = 0;
    rerender({ items: full });
    expect(seen).toEqual(["d"]);
  });

  it("navigating while the focused row is hidden starts over from the top", () => {
    const { result, rerender } = setup(full);
    act(() => result.current.onKeyDown(keyEvent("End")));
    rerender({ items: full.slice(0, 3) });
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(result.current.focusedId).toBe("a");
    // The hidden row is no longer remembered: it lost focus to a real move.
    rerender({ items: full });
    expect(result.current.focusedId).toBe("a");
  });
});
