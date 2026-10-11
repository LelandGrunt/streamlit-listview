import { describe, it, expect } from "vitest";
import { elementAt } from "./arrays";

describe("elementAt", () => {
  it("returns the element at an index inside the array", () => {
    expect(elementAt(["a", "b"], 1)).toBe("b");
  });

  it("throws a RangeError for an index past the end", () => {
    expect(() => elementAt(["a"], 1)).toThrow(
      new RangeError("index 1 is outside an array of length 1"),
    );
  });

  it("throws a RangeError for a negative index", () => {
    expect(() => elementAt(["a"], -1)).toThrow(RangeError);
  });
});
