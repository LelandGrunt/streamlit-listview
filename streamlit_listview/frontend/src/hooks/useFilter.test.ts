import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useFilter } from "./useFilter";
import type { ListviewItem } from "../types";

const ITEMS: ListviewItem[] = [
  { id: "a", label: "Apple" },
  { id: "b", label: "Banana", group: "Yellow" },
  { id: "c", label: "Cherry" },
];

describe("useFilter", () => {
  it("returns all items and isFiltering=false for an empty query", () => {
    const { result } = renderHook(() => useFilter({ items: ITEMS, query: "" }));
    expect(result.current.visibleItems).toEqual(ITEMS);
    expect(result.current.isFiltering).toBe(false);
  });

  it("treats a whitespace-only query as no filter", () => {
    const { result } = renderHook(() => useFilter({ items: ITEMS, query: "   " }));
    expect(result.current.visibleItems).toEqual(ITEMS);
    expect(result.current.isFiltering).toBe(false);
  });

  it("filters by case-insensitive substring of the label", () => {
    const { result } = renderHook(() => useFilter({ items: ITEMS, query: "an" }));
    expect(result.current.visibleItems.map((i) => i.id)).toEqual(["b"]);
    expect(result.current.isFiltering).toBe(true);
  });

  it("matches across groups and preserves item order", () => {
    const { result } = renderHook(() => useFilter({ items: ITEMS, query: "e" }));
    expect(result.current.visibleItems.map((i) => i.id)).toEqual(["a", "c"]);
  });

  it("returns an empty list when nothing matches", () => {
    const { result } = renderHook(() => useFilter({ items: ITEMS, query: "zzz" }));
    expect(result.current.visibleItems).toEqual([]);
    expect(result.current.isFiltering).toBe(true);
  });

  it("folds the German ß like the casefolded sort (Straße matched by STRASSE)", () => {
    // Python sort() uses str.casefold() (ß -> 'ss'); search must fold the same
    // way or a visibly-matching row is hidden.
    const items: ListviewItem[] = [{ id: "s", label: "Straße" }];
    const { result } = renderHook(() => useFilter({ items, query: "STRASSE" }));
    expect(result.current.visibleItems.map((i) => i.id)).toEqual(["s"]);
  });

  it("folds ß in the query too (STRAßE matches Strasse)", () => {
    const items: ListviewItem[] = [{ id: "s", label: "Strasse" }];
    const { result } = renderHook(() => useFilter({ items, query: "STRAßE" }));
    expect(result.current.visibleItems.map((i) => i.id)).toEqual(["s"]);
  });
});
