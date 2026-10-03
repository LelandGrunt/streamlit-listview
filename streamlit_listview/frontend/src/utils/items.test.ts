import { describe, it, expect, vi } from "vitest";
import type { ListviewItem } from "../types";
import { reuseUnchangedItems, runsByKey } from "./items";

// Each rerun ships the options as freshly parsed JSON, so "unchanged" always
// means "equal content, new objects" — the fixtures below model exactly that by
// building `next` from literals rather than reusing `prev`'s objects.
describe("reuseUnchangedItems", () => {
  it("returns the previous array itself when every item is unchanged", () => {
    const prev: ListviewItem[] = [
      { id: "a", label: "A", group: "G" },
      { id: 1, label: "One", disabled: true },
    ];
    const next: ListviewItem[] = [
      { id: "a", label: "A", group: "G" },
      { id: 1, label: "One", disabled: true },
    ];
    expect(reuseUnchangedItems(prev, next)).toBe(prev);
  });

  it("keeps the unchanged items' objects when another item changed", () => {
    const prev: ListviewItem[] = [
      { id: "a", label: "A" },
      { id: "b", label: "B" },
    ];
    const next: ListviewItem[] = [
      { id: "a", label: "Apricot" },
      { id: "b", label: "B" },
    ];
    const out = reuseUnchangedItems(prev, next);
    expect(out).not.toBe(prev);
    expect(out[0]).toBe(next[0]);
    expect(out[1]).toBe(prev[1]);
  });

  it("matches items by id, so a reorder keeps every object", () => {
    const prev: ListviewItem[] = [
      { id: "a", label: "A" },
      { id: "b", label: "B" },
    ];
    const next: ListviewItem[] = [
      { id: "b", label: "B" },
      { id: "a", label: "A" },
    ];
    const out = reuseUnchangedItems(prev, next);
    expect(out).not.toBe(prev);
    expect(out[0]).toBe(prev[1]);
    expect(out[1]).toBe(prev[0]);
  });

  it("keeps earlier objects and takes new ones when items are added", () => {
    const prev: ListviewItem[] = [{ id: "a", label: "A" }];
    const next: ListviewItem[] = [
      { id: "a", label: "A" },
      { id: "b", label: "B" },
    ];
    const out = reuseUnchangedItems(prev, next);
    expect(out).toHaveLength(2);
    expect(out[0]).toBe(prev[0]);
    expect(out[1]).toBe(next[1]);
  });

  it("does not reuse an item whose id is spelled differently", () => {
    // 7 and "7" are one ROW (same idKey), but the id is what maps back to a
    // Python option — reusing the old object would ship the stale spelling.
    const prev: ListviewItem[] = [{ id: 7, label: "Seven" }];
    const next: ListviewItem[] = [{ id: "7", label: "Seven" }];
    expect(reuseUnchangedItems(prev, next)[0]).toBe(next[0]);
  });

  it("treats a field that appears or disappears as a change", () => {
    const prev: ListviewItem[] = [
      { id: "a", label: "A" },
      { id: "b", label: "B", group: "G" },
    ];
    const next: ListviewItem[] = [
      { id: "a", label: "A", disabled: true },
      { id: "b", label: "B" },
    ];
    const out = reuseUnchangedItems(prev, next);
    expect(out[0]).toBe(next[0]);
    expect(out[1]).toBe(next[1]);
  });

  it("returns a shorter array, not `prev`, when trailing options were removed", () => {
    // Every surviving row still sits at its old position, so a check that only
    // looks at the positions `next` has would call this "unchanged" and hand back
    // the longer previous array — the dropped option would keep rendering.
    const prev: ListviewItem[] = [
      { id: "a", label: "A" },
      { id: "b", label: "B" },
    ];
    const next: ListviewItem[] = [{ id: "a", label: "A" }];
    const out = reuseUnchangedItems(prev, next);
    expect(out).not.toBe(prev);
    expect(out).toHaveLength(1);
    expect(out[0]).toBe(prev[0]);
  });

  it("takes the new object for a moved option whose content changed", () => {
    const prev: ListviewItem[] = [
      { id: "a", label: "A" },
      { id: "b", label: "B" },
    ];
    const next: ListviewItem[] = [
      { id: "b", label: "Berry" },
      { id: "a", label: "A" },
    ];
    const out = reuseUnchangedItems(prev, next);
    expect(out[0]).toBe(next[0]);
    expect(out[1]).toBe(prev[0]);
  });

  it("builds no id index when every option is still at its old position", () => {
    // The common change — one option edited, disabled or relabelled in place —
    // must cost one positional pass, not a Map over every previous row plus a
    // second pass (measured ~9–11 ms per rerun at 50k rows against ~2.5 ms).
    // Only a row that LEFT its position needs the index.
    const prev: ListviewItem[] = Array.from({ length: 5 }, (_, i) => ({
      id: `r${i}`,
      label: `Row ${i}`,
    }));
    const next: ListviewItem[] = prev.map((item) => ({ ...item }));
    next[2] = { ...next[2], disabled: true };
    const mapSet = vi.spyOn(Map.prototype, "set");
    try {
      const out = reuseUnchangedItems(prev, next);
      expect(out[2]).toBe(next[2]);
      expect(out[4]).toBe(prev[4]);
      expect(mapSet).not.toHaveBeenCalled();
    } finally {
      mapSet.mockRestore();
    }
  });
});

describe("runsByKey", () => {
  const half = (n: number) => Math.floor(n / 2);

  it("splits a list into runs of consecutive elements sharing a key", () => {
    expect(runsByKey([1, 2, 3, 4, 5], half)).toEqual([
      { key: 0, items: [1] },
      { key: 1, items: [2, 3] },
      { key: 2, items: [4, 5] },
    ]);
  });

  it("starts a new run when a key comes back after another one", () => {
    expect(runsByKey([0, 1, 0], (n) => n)).toEqual([
      { key: 0, items: [0] },
      { key: 1, items: [1] },
      { key: 0, items: [0] },
    ]);
  });

  it("returns no runs for an empty list", () => {
    expect(runsByKey([], half)).toEqual([]);
  });

  it("keeps the elements' identity, which the memoized rows rely on", () => {
    const a = { id: "a", label: "A" };
    expect(runsByKey([a], () => 0)[0].items[0]).toBe(a);
  });
});
