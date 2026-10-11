import { describe, expect, it } from "vitest";
import { blockKeyOf, blocksFor } from "./blocks";
import type { ListviewItem } from "../types";

describe("blockKeyOf", () => {
  it("maps a row without a group to the block without a group", () => {
    expect(blockKeyOf(undefined, "Other")).toBeNull();
    expect(blockKeyOf(null, "Other")).toBeNull();
  });

  it("maps a group named like ungrouped_label to that block too", () => {
    expect(blockKeyOf("Other", "Other")).toBeNull();
  });

  it("keeps every other group apart", () => {
    expect(blockKeyOf("Fruit", "Other")).toBe("Fruit");
    expect(blockKeyOf("Other", "N/A")).toBe("Other");
  });
});

describe("blocksFor", () => {
  const items: ListviewItem[] = [
    { id: "x", label: "No group" },
    { id: "a", label: "Apple", group: "Fruit" },
    { id: "c", label: "Carrot", group: "Veg" },
    { id: "o", label: "Shares the header", group: "Other" },
    { id: "b", label: "Banana", group: "Fruit" },
  ];

  it("renders one block per group in order of first appearance, then the rows without a group last", () => {
    const blocks = blocksFor(items, "Other");
    expect(blocks.map((block) => block.name)).toEqual(["Fruit", "Veg", null]);
    expect(blocks.map((block) => block.items.map((item) => item.id))).toEqual([
      ["a", "b"],
      ["c"],
      ["x", "o"],
    ]);
  });

  it("keeps a group named like ungrouped_label apart under another label", () => {
    const blocks = blocksFor(items, "N/A");
    expect(blocks.map((block) => block.name)).toEqual([
      "Fruit",
      "Veg",
      "Other",
      null,
    ]);
  });

  it("adds no empty block when every row has a group", () => {
    const grouped = items.filter((item) => item.group != null);
    expect(blocksFor(grouped, "N/A").map((block) => block.name)).toEqual([
      "Fruit",
      "Veg",
      "Other",
    ]);
  });

  it("returns no block for no rows", () => {
    expect(blocksFor([], "Other")).toEqual([]);
  });
});
