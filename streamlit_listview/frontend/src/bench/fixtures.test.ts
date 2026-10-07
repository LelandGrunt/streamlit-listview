import { describe, expect, it } from "vitest";
import {
  SHAPES,
  SIZES,
  benchData,
  freshCopy,
  isGrouped,
  makeLargeDataset,
  precondition,
  subsetFromEnv,
} from "./fixtures";

describe("makeLargeDataset", () => {
  // The same literals tests/test_demo.py pins demo/data.py::make_large_dataset
  // to (test_make_large_dataset_size_and_shape / _groups_in_batches_of_100).
  // Both generators must change together or the two tiers measure different rows.
  it("mirrors demo/data.py::make_large_dataset row for row", () => {
    const items = makeLargeDataset(250, "grouped");
    expect(items).toHaveLength(250);
    expect(items[0]).toEqual({
      id: "item-00000",
      label: "Item 00000",
      group: "Batch 000",
    });
    expect(items[99].group).toBe("Batch 000");
    expect(items[100].group).toBe("Batch 001");
    expect(items[200].group).toBe("Batch 002");
    expect(items[249].id).toBe("item-00249");
    expect(new Set(items.map((item) => item.id)).size).toBe(250);
  });

  it("drops the group key in the ungrouped shape", () => {
    const items = makeLargeDataset(3, "ungrouped");
    expect(items[2]).toEqual({ id: "item-00002", label: "Item 00002" });
    expect(items.some((item) => "group" in item)).toBe(false);
  });

  // The same literals e2e/perf/test_cells.py pins cells.shape_rows to.
  it("adds `disabled` to every grouped row in the disabled shape, true on rows 5, 15, 25, …", () => {
    const items = makeLargeDataset(250, "disabled");
    expect(items[0]).toEqual({
      id: "item-00000",
      label: "Item 00000",
      group: "Batch 000",
      disabled: false,
    });
    expect(items[5]).toEqual({
      id: "item-00005",
      label: "Item 00005",
      group: "Batch 000",
      disabled: true,
    });
    expect(items.every((item) => typeof item.disabled === "boolean")).toBe(
      true,
    );
    const disabled = items.filter((item) => item.disabled);
    expect(disabled).toHaveLength(25);
    expect(disabled[1].id).toBe("item-00015");
    expect(disabled[24].id).toBe("item-00245");
    expect(items.map(({ disabled: _flag, ...row }) => row)).toEqual(
      makeLargeDataset(250, "grouped"),
    );
  });

  // Both tiers click, search for or edit these rows: the first two, the
  // middle one and the last. A disabled one would turn a scenario into a
  // precondition failure.
  it("leaves every row a scenario drives enabled, at every size", () => {
    for (const n of SIZES) {
      const items = makeLargeDataset(n, "disabled");
      for (const i of [0, 1, n >> 1, n - 1]) {
        expect(items[i].disabled).toBe(false);
      }
    }
  });

  it("is empty at n=0", () => {
    expect(makeLargeDataset(0, "grouped")).toEqual([]);
  });

  // The five-digit padding holds through 100,000 rows; a larger size would
  // spell a six-digit id that sorts before `item-99999`. tests/test_demo.py
  // pins the demo's largest size to the same bound.
  it("keeps ids unique and in row order at the largest size", () => {
    const n = SIZES[SIZES.length - 1];
    const ids = makeLargeDataset(n, "ungrouped").map((item) => String(item.id));
    expect(ids[n - 1]).toBe("item-99999");
    expect(new Set(ids).size).toBe(n);
    expect(ids).toEqual([...ids].sort());
  });
});

describe("benchData", () => {
  it("turns search on and keeps every other field at the shared test default", () => {
    const items = makeLargeDataset(2, "grouped");
    const data = benchData(items);
    expect(data.items).toBe(items);
    expect(data.enable_search).toBe(true);
    expect(data.label).toBe("Benchmark");
    expect(data.selection_mode).toBe("single");
    expect(data.accept_new_options).toBe(false);
    expect(data.collapsible_groups).toBe(false);
  });

  it("applies overrides last", () => {
    expect(
      benchData([], { accept_new_options: true, height: 500 }),
    ).toMatchObject({
      accept_new_options: true,
      height: 500,
    });
  });
});

describe("freshCopy", () => {
  it("returns equal content in new objects, like a parsed rerun payload", () => {
    const items = makeLargeDataset(2, "grouped");
    const copy = freshCopy(items);
    expect(copy).toEqual(items);
    expect(copy).not.toBe(items);
    expect(copy[0]).not.toBe(items[0]);
  });
});

describe("subsetFromEnv", () => {
  it("returns the whole list when the variable is unset or blank", () => {
    expect(subsetFromEnv("X", undefined, SIZES)).toEqual([...SIZES]);
    expect(subsetFromEnv("X", "  ", SHAPES)).toEqual([...SHAPES]);
  });

  it("parses a comma-separated subset, trimming whitespace, in the given order", () => {
    expect(subsetFromEnv("X", " 50000, 100", SIZES)).toEqual([50000, 100]);
    expect(subsetFromEnv("X", "ungrouped", SHAPES)).toEqual(["ungrouped"]);
  });

  it("refuses an entry outside the list, naming the variable and the allowed values", () => {
    expect(() =>
      subsetFromEnv("LISTVIEW_BENCH_SIZES", "100,2000", SIZES),
    ).toThrow(
      'LISTVIEW_BENCH_SIZES: "2000" is not one of 100, 1000, 5000, 10000, 25000, 50000, 100000',
    );
    expect(() =>
      subsetFromEnv("LISTVIEW_BENCH_SHAPES", "grouped,,ungrouped", SHAPES),
    ).toThrow(
      'LISTVIEW_BENCH_SHAPES: "" is not one of grouped, ungrouped, disabled',
    );
  });
});

describe("isGrouped", () => {
  it("is true for every shape with groups", () => {
    expect(SHAPES.filter(isGrouped)).toEqual(["grouped", "disabled"]);
  });
});

describe("precondition", () => {
  it("is silent when the condition holds", () => {
    expect(() => precondition(true, "anything")).not.toThrow();
  });

  it("throws naming what failed, so a scenario cannot time a no-op", () => {
    expect(() =>
      precondition(false, "the last row renders after mount"),
    ).toThrow(
      "benchmark precondition failed: the last row renders after mount",
    );
  });
});
