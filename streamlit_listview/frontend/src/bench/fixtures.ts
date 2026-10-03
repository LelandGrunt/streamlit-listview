import type { ListviewData, ListviewItem } from "../types";
import { makeData } from "../test/makeData";

/**
 * Fixtures for the frontend-tier performance benchmark (listview.bench.tsx;
 * see CLAUDE.md, "Performance benchmarks"). Nothing here is reachable from
 * index.tsx, so the production bundle is unaffected. The file imports only what
 * every checkout of the component has — its payload types and the shared
 * test-data factory — because the bench is copied into OTHER checkouts to
 * benchmark them: a baseline such as `main` must be able to run it unchanged.
 */

/** The row counts every benchmark cell is measured at. */
export const SIZES = [100, 1_000, 5_000, 10_000, 25_000, 50_000] as const;
export type Size = (typeof SIZES)[number];

/** `grouped` = batches of 100 (the demo/e2e shape); `ungrouped` = no group key. */
export const SHAPES = ["grouped", "ungrouped"] as const;
export type Shape = (typeof SHAPES)[number];

/**
 * TypeScript mirror of demo/data.py::make_large_dataset — id `item-00042`,
 * label `Item 00042`, group `Batch 000` — so both tiers measure the same rows.
 * fixtures.test.ts pins it to the literals tests/test_demo.py pins the Python
 * generator to; change both generators or neither.
 */
export function makeLargeDataset(n: number, shape: Shape): ListviewItem[] {
  const items: ListviewItem[] = new Array<ListviewItem>(n);
  for (let i = 0; i < n; i++) {
    const num = String(i).padStart(5, "0");
    items[i] =
      shape === "grouped"
        ? {
            id: `item-${num}`,
            label: `Item ${num}`,
            group: `Batch ${String(Math.floor(i / 100)).padStart(3, "0")}`,
          }
        : { id: `item-${num}`, label: `Item ${num}` };
  }
  return items;
}

/**
 * A complete payload with the benchmark defaults — search on (two scenarios
 * drive it), everything else the shared test default — overrides last.
 */
export function benchData(
  items: ListviewItem[],
  overrides: Partial<ListviewData> = {},
): ListviewData {
  return makeData({
    label: "Benchmark",
    items,
    enable_search: true,
    ...overrides,
  });
}

/**
 * "Freshly parsed JSON": equal content, new objects — exactly what every
 * Streamlit rerun delivers, and what the rerun scenarios must hand the
 * component so they measure the real identity-reuse path, not a cached array.
 */
export function freshCopy(items: ListviewItem[]): ListviewItem[] {
  return JSON.parse(JSON.stringify(items)) as ListviewItem[];
}

/**
 * The subset a comma-separated environment variable names, or all of `all`
 * when it is unset or blank. An entry outside `all` throws, naming the
 * variable: a typo must shrink nothing silently — a matrix that quietly ran
 * without its 50k column would be read as "no regression at 50k".
 */
export function subsetFromEnv<T extends string | number>(
  name: string,
  raw: string | undefined,
  all: readonly T[],
): T[] {
  if (raw === undefined || raw.trim() === "") {
    return [...all];
  }
  return raw.split(",").map((entry) => {
    const text = entry.trim();
    const match = all.find((value) => String(value) === text);
    if (match === undefined) {
      throw new Error(`${name}: "${text}" is not one of ${all.join(", ")}`);
    }
    return match;
  });
}

/**
 * Fails a benchmark whose scenario would otherwise measure nothing (a needle
 * that matches no row, a header that is not a toggle). Called from each
 * bench's untimed `setup`, never from the timed body.
 */
export function precondition(ok: boolean, what: string): void {
  if (!ok) {
    throw new Error(`benchmark precondition failed: ${what}`);
  }
}
