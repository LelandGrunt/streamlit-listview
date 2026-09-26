import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useScrollToItem } from "./useScrollToItem";
import type { Id, ListviewItem } from "../types";

const ITEMS: ListviewItem[] = [
  { id: "a", label: "A", group: "G1" },
  { id: "b", label: "B", group: "G2" },
  { id: "c", label: "C" },
];

function setup(initialDefaults: Id[]) {
  const scrollToId = vi.fn();
  const ensureGroupExpanded = vi.fn();
  const { rerender } = renderHook(
    ({ defaultIds }) =>
      useScrollToItem({ defaultIds, items: ITEMS, ensureGroupExpanded, scrollToId }),
    { initialProps: { defaultIds: initialDefaults } },
  );
  return { scrollToId, ensureGroupExpanded, rerender };
}

describe("useScrollToItem", () => {
  it("scrolls to the first default id on mount and expands its group", () => {
    const { scrollToId, ensureGroupExpanded } = setup(["b"]);
    expect(ensureGroupExpanded).toHaveBeenCalledWith("G2");
    expect(scrollToId).toHaveBeenCalledWith("b");
  });

  it("does not scroll on mount when there are no defaults", () => {
    const { scrollToId } = setup([]);
    expect(scrollToId).not.toHaveBeenCalled();
  });

  it("does not expand for a default item that has no group", () => {
    const { scrollToId, ensureGroupExpanded } = setup(["c"]);
    expect(ensureGroupExpanded).not.toHaveBeenCalled();
    expect(scrollToId).toHaveBeenCalledWith("c");
  });

  it("is a no-op when the default id is not in items", () => {
    const { scrollToId, ensureGroupExpanded } = setup(["missing"]);
    expect(scrollToId).not.toHaveBeenCalled();
    expect(ensureGroupExpanded).not.toHaveBeenCalled();
  });

  it("matches the default id by row identity, not by raw type", () => {
    // `defaultIds` comes from Python's `default`, the one id list that can spell
    // a row differently than `items` does: accept_new_options lets default="7"
    // through against a numeric option id 7. Both name the same row, so the jump
    // must happen (a raw === comparison read this as "not in options").
    const scrollToId = vi.fn();
    const ensureGroupExpanded = vi.fn();
    renderHook(() =>
      useScrollToItem({
        defaultIds: ["7"],
        items: [{ id: 7, label: "Seven", group: "G1" }],
        ensureGroupExpanded,
        scrollToId,
      }),
    );
    expect(ensureGroupExpanded).toHaveBeenCalledWith("G1");
    // Scrolled by the id as given: optionDomId folds both spellings to the same
    // DOM id, so the container finds the row either way.
    expect(scrollToId).toHaveBeenCalledWith("7");
  });

  it("scrolls again only when defaultIds changes between renders", () => {
    const { scrollToId, rerender } = setup(["a"]);
    expect(scrollToId).toHaveBeenCalledTimes(1);

    // unchanged → no scroll
    rerender({ defaultIds: ["a"] });
    expect(scrollToId).toHaveBeenCalledTimes(1);

    // changed → scroll to the new first id
    rerender({ defaultIds: ["b"] });
    expect(scrollToId).toHaveBeenCalledTimes(2);
    expect(scrollToId).toHaveBeenLastCalledWith("b");
  });
});
