import { describe, it, expect } from "vitest";
import { sameIds, disabledIdSet, idKey, itemIdByKey, parseNewIntId } from "./ids";

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

// The same table as tests/test_options.py (CANONICAL_INTS, NON_CANONICAL_INTS):
// Python and the frontend each hold one copy of the canonical-integer rule, so
// keep the two in step.
describe("parseNewIntId", () => {
  it.each([
    { text: "0", expected: 0 },
    { text: "42", expected: 42 },
    { text: "-5", expected: -5 },
    { text: "9007199254740991", expected: 9007199254740991 },
    { text: "-9007199254740991", expected: -9007199254740991 },
  ])("accepts the canonical whole number $text", ({ text, expected }) => {
    expect(parseNewIntId(text)).toBe(expected);
  });

  it.each([
    { text: "007", why: "a leading zero" },
    { text: "-0", why: "negative zero" },
    { text: "+5", why: "a plus sign" },
    { text: " 5", why: "whitespace" },
    { text: "42\n", why: "a trailing newline" },
    { text: "1_000", why: "a digit separator" },
    { text: "1.5", why: "a fraction" },
    { text: "1e3", why: "an exponent" },
    { text: "abc", why: "letters" },
    { text: "\u00b2", why: "a superscript digit" },
    { text: "\u0661", why: "an Arabic-Indic digit" },
    { text: "\uff14\uff12", why: "fullwidth digits" },
    { text: "9007199254740992", why: "a value past the safe-integer range" },
    { text: "1".repeat(5000), why: "thousands of digits" },
    { text: "", why: "an empty string" },
  ])("rejects $why", ({ text }) => {
    expect(parseNewIntId(text)).toBeUndefined();
  });
});
