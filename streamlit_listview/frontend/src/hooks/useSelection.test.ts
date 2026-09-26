import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSelection } from "./useSelection";
import type { UseSelectionArgs } from "./useSelection";
import type { ListviewItem } from "../types";

const items: ListviewItem[] = [
  { id: "a", label: "A" },
  { id: "b", label: "B" },
  { id: "c", label: "C", disabled: true },
  { id: 4, label: "Four" },
];

/**
 * Render the hook over test defaults (the `items` fixture, single mode, no cap,
 * empty initial selection) plus a fresh setStateValue spy, so each test spells
 * only the fields it varies. `rerender(next)` merges onto the test's ORIGINAL
 * overrides, so changing one field mid-test keeps the rest of its fixture.
 */
function renderSelection(overrides: Partial<UseSelectionArgs> = {}) {
  const setStateValue = vi.fn();
  const view = renderHook(
    (props: Partial<UseSelectionArgs>) =>
      useSelection({
        items,
        selectionMode: "single",
        maxSelections: null,
        acceptNewOptions: false,
        initialSelection: [],
        setStateValue,
        ...props,
      }),
    { initialProps: overrides },
  );
  return {
    result: view.result,
    setStateValue,
    rerender: (next: Partial<UseSelectionArgs>) =>
      view.rerender({ ...overrides, ...next }),
  };
}

describe("useSelection (single)", () => {
  it("seeds from the initial selection prop", () => {
    const { result, setStateValue } = renderSelection({
      initialSelection: ["a"],
    });
    expect(result.current.selection).toEqual(["a"]);
    expect(result.current.isSelected("a")).toBe(true);
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("selecting a new item replaces the previous and writes state", () => {
    const { result, setStateValue } = renderSelection({
      initialSelection: ["a"],
    });
    act(() => result.current.toggle("b"));
    expect(result.current.selection).toEqual(["b"]);
    expect(setStateValue).toHaveBeenCalledWith("selection", ["b"]);
  });

  it("clicking the selected item deselects it", () => {
    const { result, setStateValue } = renderSelection({
      initialSelection: ["a"],
    });
    act(() => result.current.toggle("a"));
    expect(result.current.selection).toEqual([]);
    expect(setStateValue).toHaveBeenCalledWith("selection", []);
  });

  it("ignores clicks on disabled items", () => {
    const { result, setStateValue } = renderSelection();
    act(() => result.current.toggle("c"));
    expect(result.current.selection).toEqual([]);
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("never reports a muted item in single mode", () => {
    const { result } = renderSelection({ initialSelection: ["a"] });
    expect(result.current.isMuted("b")).toBe(false);
  });
});

describe("useSelection (multi)", () => {
  it("toggles membership and preserves selection order", () => {
    const { result, setStateValue } = renderSelection({
      selectionMode: "multi",
    });
    act(() => result.current.toggle("b"));
    act(() => result.current.toggle("a"));
    expect(result.current.selection).toEqual(["b", "a"]);
    act(() => result.current.toggle("b"));
    expect(result.current.selection).toEqual(["a"]);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["a"]);
  });

  it("ignores adds once max_selections is reached but still allows removals", () => {
    const { result, setStateValue } = renderSelection({
      selectionMode: "multi",
      maxSelections: 2,
      initialSelection: ["a", "b"],
    });
    act(() => result.current.toggle(4));
    expect(result.current.selection).toEqual(["a", "b"]);
    setStateValue.mockClear();
    act(() => result.current.toggle("a"));
    expect(result.current.selection).toEqual(["b"]);
    expect(setStateValue).toHaveBeenCalledWith("selection", ["b"]);
  });

  it("mutes unselected items at the cap; selected items are never muted", () => {
    const { result } = renderSelection({
      selectionMode: "multi",
      maxSelections: 2,
      initialSelection: ["a", "b"],
    });
    expect(result.current.isMuted(4)).toBe(true);
    expect(result.current.isMuted("a")).toBe(false);
  });

  it("does not mute when below the cap or when max_selections is null", () => {
    const { result } = renderSelection({
      selectionMode: "multi",
      maxSelections: 2,
      initialSelection: ["a"],
    });
    expect(result.current.isMuted(4)).toBe(false);
  });

  it("disabled items are inert in multi mode too", () => {
    const { result, setStateValue } = renderSelection({
      selectionMode: "multi",
    });
    act(() => result.current.toggle("c"));
    expect(result.current.selection).toEqual([]);
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("ignores a later initialSelection change: `default` never re-selects", () => {
    // data.default_ids is read at mount only. A keyed instance whose `default`
    // changes at runtime must keep showing its committed selection: echoing the
    // new default into the display without committing it (what this hook used to
    // do) shows a selection listview() does not return, and committing it would
    // fire on_change for a change no user made. A keyless instance remounts, so
    // it picks the new seed up through useState instead.
    const { result, rerender, setStateValue } = renderSelection({
      selectionMode: "multi",
      initialSelection: ["a"],
    });
    expect(result.current.selection).toEqual(["a"]);
    rerender({ initialSelection: ["b", 4] });
    expect(result.current.selection).toEqual(["a"]);
    expect(setStateValue).not.toHaveBeenCalled();
  });
});

describe("add()", () => {
  // The fixtures that add an id absent from `items` ("new") set
  // acceptNewOptions, because that is the only way the container reaches add()
  // with an unknown id — and reconciliation drops unknown ids when it is off.
  it("single mode: add replaces the current selection", () => {
    const { result, setStateValue } = renderSelection({
      items: [{ id: "a", label: "A" }, { id: "b", label: "B" }],
      acceptNewOptions: true,
      initialSelection: ["a"],
    });
    act(() => result.current.add("new"));
    expect(result.current.selection).toEqual(["new"]);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["new"]);
  });

  it("multi mode: add appends when below the cap and not present", () => {
    const { result } = renderSelection({
      items: [{ id: "a", label: "A" }],
      selectionMode: "multi",
      maxSelections: 2,
      acceptNewOptions: true,
      initialSelection: ["a"],
    });
    act(() => result.current.add("new"));
    expect(result.current.selection).toEqual(["a", "new"]);
  });

  it("multi mode: add is a no-op at the cap", () => {
    const { result, setStateValue } = renderSelection({
      items: [{ id: "a", label: "A" }, { id: "b", label: "B" }],
      selectionMode: "multi",
      maxSelections: 2,
      initialSelection: ["a", "b"],
    });
    setStateValue.mockClear();
    act(() => result.current.add("new"));
    expect(result.current.selection).toEqual(["a", "b"]);
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("ignores an add for a disabled id", () => {
    const { result, setStateValue } = renderSelection({
      items: [
        { id: "a", label: "A" },
        { id: "d", label: "D", disabled: true },
      ],
      selectionMode: "multi",
    });
    act(() => result.current.add("d"));
    expect(result.current.selection).toEqual([]);
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("single mode: add is a no-op when the id is already the sole selection", () => {
    const { result, setStateValue } = renderSelection({
      items: [{ id: "a", label: "A" }],
      initialSelection: ["a"],
    });
    setStateValue.mockClear();
    act(() => result.current.add("a"));
    expect(result.current.selection).toEqual(["a"]);
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("add never deselects an already-selected id", () => {
    const { result, setStateValue } = renderSelection({
      items: [{ id: "a", label: "A" }],
      selectionMode: "multi",
      initialSelection: ["a"],
    });
    setStateValue.mockClear();
    act(() => result.current.add("a"));
    expect(result.current.selection).toEqual(["a"]);
    expect(setStateValue).not.toHaveBeenCalled();
  });
});

describe("clear()", () => {
  it("empties the selection and writes state back", () => {
    const { result, setStateValue } = renderSelection({
      items: [{ id: "a", label: "A" }],
      selectionMode: "multi",
      initialSelection: ["a"],
    });
    act(() => result.current.clear());
    expect(result.current.selection).toEqual([]);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", []);
  });

  it("clear on an empty selection does not write state", () => {
    const { result, setStateValue } = renderSelection({
      items: [{ id: "a", label: "A" }],
    });
    act(() => result.current.clear());
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("clear() preserves a disabled (locked) selected item, clearing the rest", () => {
    // A disabled item is inert: toggle and the bulk ops already refuse to remove
    // it, so Escape's clear must not wipe it either (it would otherwise be the
    // ONLY way to remove a locked selection). 'c' is disabled in `items`.
    const { result, setStateValue } = renderSelection({
      selectionMode: "multi",
      initialSelection: ["a", "c"],
    });
    act(() => result.current.clear());
    expect(result.current.selection).toEqual(["c"]);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["c"]);
  });

  it("clear() is a no-op when the only selection is a disabled item", () => {
    const { result, setStateValue } = renderSelection({
      initialSelection: ["c"],
    });
    act(() => result.current.clear());
    expect(result.current.selection).toEqual(["c"]);
    expect(setStateValue).not.toHaveBeenCalled();
  });
});

describe("useSelection (bulk visible ops)", () => {
  // a–d are the "visible" rows the bulk ops below are handed. x/y/z model
  // out-of-view selected rows: search or a collapsed group keeps them out of the
  // visible scope, but they are still options in data.items — which is what
  // makes them survive reconciliation, unlike a phantom id.
  const bulkItems: ListviewItem[] = [
    { id: "a", label: "A" },
    { id: "b", label: "B" },
    { id: "c", label: "C" },
    { id: "d", label: "D", disabled: true },
    { id: "x", label: "X" },
    { id: "y", label: "Y" },
    { id: "z", label: "Z" },
  ];

  it("selectAllVisible adds visible ids in list order in a single commit", () => {
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
    });
    act(() => result.current.selectAllVisible(["a", "b", "c"]));
    expect(setStateValue).toHaveBeenCalledTimes(1);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["a", "b", "c"]);
    expect(result.current.selection).toEqual(["a", "b", "c"]);
  });

  it("selectAllVisible skips disabled and already-selected ids", () => {
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
      initialSelection: ["a"],
    });
    // pass all four including disabled 'd' and already-selected 'a'
    act(() => result.current.selectAllVisible(["a", "b", "c", "d"]));
    expect(setStateValue).toHaveBeenCalledTimes(1);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["a", "b", "c"]);
  });

  it("selectAllVisible stops at max_selections counting the whole selection (worked example)", () => {
    // 1 out-of-view selected id ('z') + cap 3 + visible unselected a,b,c
    // => adds 2 visible ids; total length == cap == 3 => ['z','a','b'].
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
      maxSelections: 3,
      initialSelection: ["z"],
    });
    act(() => result.current.selectAllVisible(["a", "b", "c"]));
    expect(setStateValue).toHaveBeenCalledTimes(1);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["z", "a", "b"]);
    expect(result.current.selection).toHaveLength(3);
  });

  it("selectAllVisible is a no-op (skips commit) when everything is already selected", () => {
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
      initialSelection: ["a", "b", "c"],
    });
    setStateValue.mockClear();
    act(() => result.current.selectAllVisible(["a", "b", "c"]));
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("selectAllVisible is a no-op when already at the cap", () => {
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
      maxSelections: 2,
      initialSelection: ["x", "y"],
    });
    setStateValue.mockClear();
    act(() => result.current.selectAllVisible(["a", "b", "c"]));
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("deselectVisible removes only the given ids and preserves others, single commit", () => {
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
      initialSelection: ["z", "a", "b", "c"],
    });
    act(() => result.current.deselectVisible(["a", "b", "c"]));
    expect(setStateValue).toHaveBeenCalledTimes(1);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["z"]);
    expect(result.current.selection).toEqual(["z"]);
  });

  it("deselectVisible is a no-op (skips commit) when nothing to remove", () => {
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
      initialSelection: ["z"],
    });
    setStateValue.mockClear();
    act(() => result.current.deselectVisible(["a", "b", "c"]));
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("allVisibleSelected returns true only when every id is selected, and never commits", () => {
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
      initialSelection: ["a", "b"],
    });
    expect(result.current.allVisibleSelected(["a", "b"])).toBe(true);
    expect(result.current.allVisibleSelected(["a", "b", "c"])).toBe(false);
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("clear() still commits an empty selection (Escape regression guard)", () => {
    const { result, setStateValue } = renderSelection({
      items: bulkItems,
      selectionMode: "multi",
      initialSelection: ["a", "b"],
    });
    act(() => result.current.clear());
    expect(setStateValue).toHaveBeenLastCalledWith("selection", []);
    expect(result.current.selection).toEqual([]);
  });
});

// A keyed instance keeps its selection across reruns while `options`,
// `max_selections` and `selection_mode` change underneath it. Reconciliation is
// the single pass that keeps the selection, the rendered rows and the value
// listview() returns from drifting apart in those cases.
describe("useSelection (reconciliation)", () => {
  const abc: ListviewItem[] = [
    { id: "a", label: "A" },
    { id: "b", label: "B" },
    { id: "c", label: "C" },
  ];

  it("drops ids that left `options`, freeing the cap slots they held", () => {
    // The dead-lock: cap 2, a+b selected, then the app rerenders with options
    // shrunk to [c]. Un-reconciled, the two phantoms keep the widget at 2 of 2 —
    // the only real row renders muted, every click is ignored, and Python
    // returns [] because map_selection discards ids it cannot resolve. So the
    // widget accepts no input at all while claiming to be full.
    const { result, rerender, setStateValue } = renderSelection({
      items: abc,
      selectionMode: "multi",
      maxSelections: 2,
      initialSelection: ["a", "b"],
    });
    expect(result.current.atCap).toBe(true);

    rerender({ items: [abc[2]] });
    expect(result.current.selection).toEqual([]);
    expect(setStateValue).toHaveBeenCalledWith("selection", []);
    expect(result.current.atCap).toBe(false);
    expect(result.current.isMuted("c")).toBe(false);
    // ... and the surviving row takes input again.
    act(() => result.current.toggle("c"));
    expect(result.current.selection).toEqual(["c"]);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["c"]);
  });

  it("clamps to a cap lowered at runtime, earliest-selected surviving", () => {
    const { result, rerender, setStateValue } = renderSelection({
      items: [...abc, { id: "d", label: "D" }],
      selectionMode: "multi",
      maxSelections: 4,
      initialSelection: ["a", "b", "c", "d"],
    });
    expect(result.current.selection).toEqual(["a", "b", "c", "d"]);

    rerender({ maxSelections: 2 });
    expect(result.current.selection).toEqual(["a", "b"]);
    expect(setStateValue).toHaveBeenCalledWith("selection", ["a", "b"]);
  });

  it("truncates to one when selection_mode flips to single", () => {
    // Two selected rows inside a listbox that no longer advertises
    // aria-multiselectable is an ARIA contradiction, and Python would map only
    // the first id — UI showing 2, value holding 1. Truncating also restores
    // single mode's click-to-deselect, which needs the selection to BE one id.
    const { result, rerender, setStateValue } = renderSelection({
      items: abc,
      selectionMode: "multi",
      initialSelection: ["a", "b"],
    });
    expect(result.current.selection).toEqual(["a", "b"]);

    rerender({ selectionMode: "single" });
    expect(result.current.selection).toEqual(["a"]);
    expect(setStateValue).toHaveBeenCalledWith("selection", ["a"]);
    act(() => result.current.toggle("a"));
    expect(result.current.selection).toEqual([]);
  });

  it("canonicalizes a typed id onto the option that later adopts it", () => {
    // accept_new_options: the user typed "7", then the caller promoted it into
    // options as the int 7. Both are ONE row (idKey "7"), so the entry must
    // become the option's own id — otherwise the row renders unselected, a click
    // appends a second entry for it, and Python returns a bare string beside the
    // option object.
    const { result, rerender, setStateValue } = renderSelection({
      items: [{ id: "one", label: "One" }],
      selectionMode: "multi",
      acceptNewOptions: true,
      initialSelection: ["7"],
    });
    // Unknown ids are legitimate while accept_new_options is on: kept, no commit.
    expect(result.current.selection).toEqual(["7"]);
    expect(setStateValue).not.toHaveBeenCalled();

    rerender({
      items: [
        { id: "one", label: "One" },
        { id: 7, label: "Seven" },
      ],
    });
    expect(result.current.selection).toEqual([7]);
    expect(setStateValue).toHaveBeenCalledWith("selection", [7]);
    // One entry for one row: clicking it deselects instead of appending.
    act(() => result.current.toggle(7));
    expect(result.current.selection).toEqual([]);
  });

  it("collapses two spellings of one row into a single entry", () => {
    // Python de-duplicates `default` by raw id, so with accept_new_options on it
    // can seed ["1", 1] — two entries for the one row idKey "1" would render as
    // a single row holding two cap slots.
    const { result, setStateValue } = renderSelection({
      items: [],
      selectionMode: "multi",
      acceptNewOptions: true,
      initialSelection: ["1", 1],
    });
    expect(result.current.selection).toEqual(["1"]);
    expect(setStateValue).toHaveBeenCalledWith("selection", ["1"]);
  });

  it("treats a row as the same row across id spellings in every op", () => {
    // No option adopts the typed "7" here, so the mismatch is not canonicalized
    // away — the row-identity ops must still recognise the numeric 7 as it.
    const { result } = renderSelection({
      items: [],
      selectionMode: "multi",
      acceptNewOptions: true,
      initialSelection: ["7"],
    });
    expect(result.current.isSelected(7)).toBe(true);
    expect(result.current.allVisibleSelected([7])).toBe(true);
    act(() => result.current.deselectVisible([7]));
    expect(result.current.selection).toEqual([]);
  });

  it("keeps a selected id that has become disabled", () => {
    // A disabled selection is locked, not removed: toggle/clear/deselectVisible
    // all refuse to drop it, so reconciliation must not be the back door.
    const { result, rerender, setStateValue } = renderSelection({
      items: abc,
      selectionMode: "multi",
      initialSelection: ["a"],
    });
    rerender({ items: [{ id: "a", label: "A", disabled: true }, abc[1], abc[2]] });
    expect(result.current.selection).toEqual(["a"]);
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("commits nothing while there is nothing to correct", () => {
    // Mount cannot need correcting — Python validates `default` against the same
    // rules — and an unrelated data change must not fire a value change for
    // something no user did. New array identities on every render, so the
    // reconciliation memo really does recompute.
    const { result, rerender, setStateValue } = renderSelection({
      items: [...abc],
      selectionMode: "multi",
      maxSelections: 2,
      initialSelection: ["a", "b"],
    });
    expect(setStateValue).not.toHaveBeenCalled();
    rerender({ items: [...abc] });
    rerender({ items: [abc[1], abc[0], abc[2]] });
    expect(result.current.selection).toEqual(["a", "b"]);
    expect(setStateValue).not.toHaveBeenCalled();
  });
});
