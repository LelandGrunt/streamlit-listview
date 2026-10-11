import { describe, it, expect, vi } from "vitest";
import type { Mock } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { GroupNode, useKeyboardNav } from "./useKeyboardNav";
import type { NavNode } from "./useKeyboardNav";
import type { GroupKey } from "./useCollapse";
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
 * A keydown as the list really sees it: dispatched AT the listbox or tree,
 * because neither rows nor headers are focusable, so the list itself is what
 * holds DOM focus.
 */
function keyEvent(key: string): FakeKeyEvent {
  return {
    key,
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
  } as unknown as FakeKeyEvent;
}

describe("useKeyboardNav", () => {
  it("starts with no focused item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    expect(result.current.focusedId).toBeNull();
  });

  it("ArrowDown focuses the first focusable item, then skips disabled ones", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
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
      useKeyboardNav({ nodes: items, onSelect }),
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
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe(4);
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(result.current.focusedId).toBe(4);
  });

  it("Home focuses the first focusable item; End focuses the last focusable item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe(4);
    act(() => result.current.onKeyDown(keyEvent("Home")));
    expect(result.current.focusedId).toBe("a");
  });

  it("Enter selects the focused item", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    act(() => result.current.onKeyDown(keyEvent("Enter")));
    expect(onSelect).toHaveBeenCalledWith("a");
  });

  it("Space selects the focused item and is treated the same as Enter", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    act(() => result.current.onKeyDown(keyEvent(" ")));
    expect(onSelect).toHaveBeenCalledWith(4);
  });

  it("Enter/Space with nothing focused does not call onSelect", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("Enter")));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("ignores unrelated keys without calling onSelect", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    act(() => result.current.onKeyDown(keyEvent("a")));
    expect(result.current.focusedId).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("navigation keys are inert when there are no focusable items", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({
        nodes: [{ id: "x", label: "X", disabled: true }],
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
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    expect(result.current.focusedId).toBeNull();
    act(() => result.current.onKeyDown(keyEvent("ArrowUp")));
    expect(result.current.focusedId).toBe(4);
  });

  it("clamps a stale focus index when the items list shrinks", () => {
    const onSelect = vi.fn();
    const { result, rerender } = renderHook(
      ({ list }) => useKeyboardNav({ nodes: list, onSelect }),
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
      ({ list }) => useKeyboardNav({ nodes: list, onSelect }),
      { initialProps: { list: items } },
    );
    act(() => result.current.onKeyDown(keyEvent("End")));
    expect(result.current.focusedId).toBe(4);
    // shrink so the previously focused row no longer exists
    rerender({
      list: [
        { id: "a", label: "A" },
        { id: "c", label: "C" },
      ],
    });
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
      ({ list }) => useKeyboardNav({ nodes: list, onSelect }),
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
      useKeyboardNav({ nodes: items, onSelect }),
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
      useKeyboardNav({ nodes: items, onSelect }),
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
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect }),
    );
    act(() => result.current.setFocusToId("c"));
    act(() => result.current.onKeyDown(keyEvent("ArrowDown")));
    expect(result.current.focusedId).toBe(4);
  });
});

describe("slash and escape", () => {
  const items = [
    { id: "a", label: "A" },
    { id: "b", label: "B" },
  ];

  it('"/" calls onSlash and prevents default', () => {
    const onSlash = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect: vi.fn(), onSlash }),
    );
    const event = keyEvent("/");
    act(() => result.current.onKeyDown(event));
    expect(onSlash).toHaveBeenCalledTimes(1);
    expect(event.preventDefault).toHaveBeenCalled();
  });

  it("Escape calls onEscape", () => {
    const onEscape = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect: vi.fn(), onEscape }),
    );
    act(() => result.current.onKeyDown(keyEvent("Escape")));
    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it("Escape without an onEscape handler does nothing (no throw)", () => {
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect: vi.fn() }),
    );
    const event = keyEvent("Escape");
    act(() => result.current.onKeyDown(event));
    expect(event.preventDefault).not.toHaveBeenCalled();
  });

  it('"/" without an onSlash handler does nothing (no throw)', () => {
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect: vi.fn() }),
    );
    const event = keyEvent("/");
    act(() => result.current.onKeyDown(event));
    expect(event.preventDefault).not.toHaveBeenCalled();
  });
});

describe("group headers in a tree", () => {
  // With collapsible_groups the list is a tree: each group header is a node of
  // its own, between the rows, and a collapsed group contributes its header
  // only. Rows name no header; a row's header is the closest one above it.
  const fruit = new GroupNode("Fruit", true);
  const veg = new GroupNode("Veg", false); // collapsed: no rows follow
  const loose = new GroupNode(null, true); // the block without a group
  const nodes: NavNode[] = [
    fruit,
    { id: "apple", label: "Apple", group: "Fruit" },
    { id: "banana", label: "Banana", group: "Fruit", disabled: true },
    { id: "cherry", label: "Cherry", group: "Fruit" },
    veg,
    loose,
    { id: "x", label: "X" },
  ];

  // The node the ring is on: a row id, or for a header its group together
  // with the row field, which must then read null.
  function focusOf(nav: ReturnType<typeof useKeyboardNav>) {
    return nav.focusedGroup === undefined
      ? nav.focusedId
      : { group: nav.focusedGroup, row: nav.focusedId };
  }
  const header = (group: GroupKey) => ({ group, row: null });

  function setup(
    list: NavNode[] = nodes,
    extra: Partial<Parameters<typeof useKeyboardNav>[0]> = {},
  ) {
    const onSelect = vi.fn();
    const onToggleGroup = vi.fn();
    const scrollToId = vi.fn();
    const scrollToGroup = vi.fn();
    const { result, rerender } = renderHook(
      ({ current }) =>
        useKeyboardNav({
          nodes: current,
          onSelect,
          onToggleGroup,
          scrollToId,
          scrollToGroup,
          ...extra,
        }),
      { initialProps: { current: list } },
    );
    const press = (key: string) => {
      const event = keyEvent(key);
      act(() => result.current.onKeyDown(event));
      return event;
    };
    return {
      result,
      rerender,
      press,
      onSelect,
      onToggleGroup,
      scrollToId,
      scrollToGroup,
    };
  }

  it("moves through headers and rows in render order, skipping disabled rows", () => {
    const { result, press } = setup();
    const seen = [];
    for (let step = 0; step < 6; step += 1) {
      press("ArrowDown");
      seen.push(focusOf(result.current));
    }
    expect(seen).toEqual([
      header("Fruit"),
      "apple",
      "cherry",
      header("Veg"),
      header(null),
      "x",
    ]);
    press("Home");
    expect(focusOf(result.current)).toEqual(header("Fruit"));
    press("ArrowUp");
    expect(focusOf(result.current)).toEqual(header("Fruit"));
    press("End");
    expect(focusOf(result.current)).toBe("x");
  });

  it("scrolls a header a key lands on through scrollToGroup", () => {
    const { press, scrollToId, scrollToGroup } = setup();
    press("ArrowDown");
    expect(scrollToGroup).toHaveBeenLastCalledWith("Fruit");
    expect(scrollToId).not.toHaveBeenCalled();
    press("End");
    press("ArrowUp");
    expect(scrollToGroup).toHaveBeenLastCalledWith(null);
  });

  it("toggles a focused header with Enter or Space and selects nothing", () => {
    const { result, press, onSelect, onToggleGroup } = setup();
    act(() => result.current.setFocusToGroup("Veg"));
    for (const key of ["Enter", " "]) {
      expect(press(key).preventDefault).toHaveBeenCalled();
    }
    expect(onToggleGroup.mock.calls).toEqual([["Veg"], ["Veg"]]);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("ArrowRight opens a collapsed header and keeps the focus on it", () => {
    const { result, press, onToggleGroup } = setup();
    act(() => result.current.setFocusToGroup("Veg"));
    expect(press("ArrowRight").preventDefault).toHaveBeenCalled();
    expect(onToggleGroup).toHaveBeenCalledWith("Veg");
    expect(focusOf(result.current)).toEqual(header("Veg"));
  });

  it("ArrowRight on an open header moves to its first row", () => {
    const { result, press, onToggleGroup, scrollToId } = setup();
    act(() => result.current.setFocusToGroup(null));
    press("ArrowRight");
    expect(focusOf(result.current)).toBe("x");
    expect(scrollToId).toHaveBeenLastCalledWith("x");
    expect(onToggleGroup).not.toHaveBeenCalled();
  });

  it("ArrowRight does nothing on a row or on an open header without rows", () => {
    // Every row of "Empty" is disabled, so the next node is another header.
    const empty = new GroupNode("Empty", true);
    const { result, press, onToggleGroup } = setup([empty, veg]);
    act(() => result.current.setFocusToGroup("Empty"));
    expect(press("ArrowRight").preventDefault).not.toHaveBeenCalled();
    expect(focusOf(result.current)).toEqual(header("Empty"));
    const rows = setup();
    act(() => rows.result.current.setFocusToId("cherry"));
    expect(rows.press("ArrowRight").preventDefault).not.toHaveBeenCalled();
    expect(focusOf(rows.result.current)).toBe("cherry");
    expect(onToggleGroup).not.toHaveBeenCalled();
    expect(rows.onToggleGroup).not.toHaveBeenCalled();
  });

  it("ArrowLeft closes an open header and does nothing on a closed one", () => {
    const { result, press, onToggleGroup } = setup();
    act(() => result.current.setFocusToGroup("Fruit"));
    expect(press("ArrowLeft").preventDefault).toHaveBeenCalled();
    expect(onToggleGroup).toHaveBeenCalledWith("Fruit");
    act(() => result.current.setFocusToGroup("Veg"));
    expect(press("ArrowLeft").preventDefault).not.toHaveBeenCalled();
    expect(onToggleGroup).toHaveBeenCalledTimes(1);
  });

  it("ArrowLeft on a row moves to its header", () => {
    const { result, press, onToggleGroup, scrollToGroup } = setup();
    act(() => result.current.setFocusToId("cherry"));
    expect(press("ArrowLeft").preventDefault).toHaveBeenCalled();
    expect(focusOf(result.current)).toEqual(header("Fruit"));
    expect(scrollToGroup).toHaveBeenLastCalledWith("Fruit");
    expect(onToggleGroup).not.toHaveBeenCalled();
  });

  it("ArrowLeft and ArrowRight do nothing in a list without headers", () => {
    const { result, press, onToggleGroup } = setup(items);
    act(() => result.current.setFocusToId("c"));
    for (const key of ["ArrowLeft", "ArrowRight"]) {
      expect(press(key).preventDefault).not.toHaveBeenCalled();
    }
    expect(focusOf(result.current)).toBe("c");
    expect(onToggleGroup).not.toHaveBeenCalled();
  });

  it("ArrowLeft, ArrowRight and Enter on a header need no toggle handler", () => {
    const { result, press } = setup(nodes, { onToggleGroup: undefined });
    act(() => result.current.setFocusToGroup("Veg"));
    for (const key of ["ArrowRight", "Enter"]) {
      press(key);
    }
    act(() => result.current.setFocusToGroup("Fruit"));
    press("ArrowLeft");
    expect(focusOf(result.current)).toEqual(header("Fruit"));
  });

  it("setFocusToGroup focuses a header and ignores a group it does not list", () => {
    const { result } = setup();
    act(() => result.current.setFocusToGroup(null));
    expect(focusOf(result.current)).toEqual(header(null));
    act(() => result.current.setFocusToGroup("Meat"));
    expect(focusOf(result.current)).toEqual(header(null));
    const flat = setup(items);
    act(() => flat.result.current.setFocusToGroup(null));
    expect(flat.result.current.focusedGroup).toBeUndefined();
  });

  it("hides the ring while a search hides the focused header and restores it after", () => {
    const { result, rerender } = setup();
    act(() => result.current.setFocusToGroup("Veg"));
    rerender({ current: nodes.filter((node) => node !== veg) });
    expect(result.current.focusedGroup).toBeUndefined();
    expect(result.current.focusedId).toBeNull();
    rerender({ current: nodes });
    expect(focusOf(result.current)).toEqual(header("Veg"));
  });

  it("follows a header whose node object a render rebuilt", () => {
    // Listview builds the header nodes afresh whenever the blocks change, so
    // the focus must name the group, not the node object.
    const { result, rerender, press, onToggleGroup } = setup();
    act(() => result.current.setFocusToGroup("Fruit"));
    rerender({
      current: nodes.map((node) =>
        node === fruit ? new GroupNode("Fruit", false) : node,
      ),
    });
    expect(focusOf(result.current)).toEqual(header("Fruit"));
    // now closed: ArrowLeft has nothing to close, ArrowRight opens it
    press("ArrowLeft");
    expect(onToggleGroup).not.toHaveBeenCalled();
    press("ArrowRight");
    expect(onToggleGroup).toHaveBeenCalledWith("Fruit");
  });
});

describe("scrolling the keyboard-focused row into view", () => {
  it("scrolls the row every focus-moving key lands on", () => {
    const scrollToId = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNav({ nodes: items, onSelect: vi.fn(), scrollToId }),
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
      useKeyboardNav({ nodes: items, onSelect: vi.fn(), onEscape, scrollToId }),
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
        const nav = useKeyboardNav({ nodes: current, onSelect });
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
