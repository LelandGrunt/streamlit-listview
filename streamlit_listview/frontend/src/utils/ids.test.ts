import { describe, it, expect } from "vitest";
import { sameIds, disabledIdSet, idKey, itemIdByKey } from "./ids";

describe("sameIds", () => {
  it("is true for element-wise equal lists (same order)", () => {
    expect(sameIds(["a", 1], ["a", 1])).toBe(true);
  });

  it("is true for two empty lists", () => {
    expect(sameIds([], [])).toBe(true);
  });

  it("is false for different lengths", () => {
    expect(sameIds(["a"], ["a", "b"])).toBe(false);
  });

  it("is false for same length but different order/elements", () => {
    expect(sameIds(["a", "b"], ["b", "a"])).toBe(false);
  });
});

describe("idKey", () => {
  it("maps a numeric id and its string form onto the same key", () => {
    expect(idKey(7)).toBe("7");
    expect(idKey("7")).toBe(idKey(7));
  });
});

describe("itemIdByKey", () => {
  it("maps each row-identity key to the item's own (canonical) id", () => {
    const byKey = itemIdByKey([
      { id: "a", label: "A" },
      { id: 7, label: "Seven" },
    ]);
    // Looked up by key, it yields the id as `items` spells it — the id that maps
    // back to a Python option.
    expect(byKey.get("7")).toBe(7);
    expect(byKey.get("a")).toBe("a");
    expect(byKey.has("nope")).toBe(false);
    expect(byKey.size).toBe(2);
  });

  it("is empty for no items", () => {
    expect(itemIdByKey([]).size).toBe(0);
  });
});

describe("disabledIdSet", () => {
  it("collects only the ids of disabled items (string and numeric)", () => {
    const set = disabledIdSet([
      { id: "a", label: "A" },
      { id: "b", label: "B", disabled: true },
      { id: 3, label: "C", disabled: false },
      { id: 4, label: "D", disabled: true },
    ]);
    expect(set.has("b")).toBe(true);
    expect(set.has(4)).toBe(true);
    expect(set.has("a")).toBe(false);
    expect(set.has(3)).toBe(false);
    expect(set.size).toBe(2);
  });

  it("returns an empty set when nothing is disabled", () => {
    expect(disabledIdSet([{ id: "a", label: "A" }]).size).toBe(0);
  });
});
