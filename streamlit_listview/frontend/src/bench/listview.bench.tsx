import { bench, describe } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import { Listview } from "../Listview";
import type { Id, ListviewData, ListviewItem } from "../types";
import {
  SHAPES,
  SIZES,
  benchData,
  freshCopy,
  makeLargeDataset,
  precondition,
  subsetFromEnv,
} from "./fixtures";

/**
 * Frontend-tier performance benchmark: the component through its public
 * surface (props and DOM events) in jsdom, at every size and shape, one bench
 * per scenario. `npm run bench`; CLAUDE.md ("Performance benchmarks") has the
 * two tiers' roles, the compare workflow and the caveats — React development
 * build, jsdom DOM speed — that make these numbers relative, never absolute.
 *
 * Imports only what every checkout of the component has — `Listview`, its
 * payload types and the shared test-data factory — so the file measures ANY
 * checkout: a baseline (`main`) is benchmarked by copying src/bench/ into it.
 *
 * Every cell is declared, always, in the fixed SHAPES x SIZES order, and the
 * ones outside LISTVIEW_BENCH_SHAPES / LISTVIEW_BENCH_SIZES are skipped rather
 * than omitted: `vitest bench --compare` pairs benchmarks by their position in
 * the file, not by name, so a loop over only the selected cells would line a
 * subset run up against the wrong cells of a full baseline.
 *
 * vitest's bench() gives tinybench no per-iteration hook (the runner builds
 * `new Task(bench, name, fn)` without options), only a Bench-level `setup` /
 * `teardown` that runs once before the warm-up and once before the measured
 * run. Every body below therefore leaves the list ready for its own next
 * iteration; the two scenarios that would need an untimed reset between
 * halves (search, group toggle) measure both halves together.
 */

const sizes = subsetFromEnv(
  "LISTVIEW_BENCH_SIZES",
  process.env.LISTVIEW_BENCH_SIZES,
  SIZES,
);
const shapes = subsetFromEnv(
  "LISTVIEW_BENCH_SHAPES",
  process.env.LISTVIEW_BENCH_SHAPES,
  SHAPES,
);

const noop = () => {};

interface BenchBudget {
  iterations?: number;
  time?: number;
  warmupIterations?: number;
  warmupTime?: number;
}

// tinybench runs a task until BOTH its time budget (default 500 ms) and its
// iteration count (default 10) are met. Up to 5k rows that is cheap. Above it
// one iteration costs seconds (50k mount ≈ 4.6 s in jsdom), so the count is
// fixed and the budgets zeroed, with one warm-up iteration instead of five.
function budget(n: number): BenchBudget {
  if (n <= 5_000) {
    return {};
  }
  const iterations = n <= 10_000 ? 8 : n <= 25_000 ? 5 : 3;
  return { iterations, time: 0, warmupIterations: 1, warmupTime: 0 };
}

// `budget` is sized for mount (~2 s a go at 50k). The other scenarios cost
// 10-15x less per iteration, and 3 samples of them swing ~20% run to run —
// more than the few-percent effects an A/B comparison has to resolve — so
// above 5k rows they get a larger fixed count.
function cheapBudget(n: number): BenchBudget {
  if (n <= 5_000) {
    return {};
  }
  return { iterations: 15, time: 0, warmupIterations: 2, warmupTime: 0 };
}

/** A rendered row by its DOM id — an id-map hit, cheap even at 50k rows. */
const row = (id: Id) => document.getElementById(`listview-opt-${id}`);

for (const shape of SHAPES) {
  for (const n of SIZES) {
    const selected = shapes.includes(shape) && sizes.includes(n);
    describe.skipIf(!selected)(`${shape} n=${n}`, () => {
      const base = makeLargeDataset(n, shape);
      const last = base[n - 1].id;
      const opts = budget(n);
      const cheapOpts = cheapBudget(n);

      // The browser tier renders `collapsible_groups=<grouped>` for every
      // scenario, so every payload this cell builds carries it — the mount,
      // each rerun's payload, and the group scenario's own mount — and a
      // rerun can never change the configuration the list mounted with.
      const cellData = (
        items: ListviewItem[],
        overrides: Partial<ListviewData> = {},
      ) =>
        benchData(items, {
          collapsible_groups: shape === "grouped",
          ...overrides,
        });

      // Render AND unmount in the timed body: with no per-iteration hook, the
      // alternative is hundreds of 100-row trees (or three 50k ones) left
      // mounted, skewing every later iteration. The unmount is ~10% of the
      // mount at 50k; the number is a mount cycle and is documented as such.
      bench(
        "mount",
        () => {
          render(<Listview data={cellData(base)} setStateValue={noop} />);
          cleanup();
        },
        {
          ...opts,
          setup: () => {
            render(<Listview data={cellData(base)} setStateValue={noop} />);
            precondition(
              row(last) !== null,
              "the last row renders after mount",
            );
            cleanup();
          },
        },
      );

      const first = base[0].id;
      const second = base[1].id;
      // "04999": the zero-padded number of the last label; no other label
      // contains it, so the query leaves exactly one row.
      const needle = base[n - 1].label.slice("Item ".length);
      const mid = n >> 1;

      // One mounted instance per scenario. `setup` (untimed; once before the
      // warm-up, once before the measured run) mounts it, caches the DOM
      // handles the body needs — looked up ONCE, never inside the timed body,
      // where a querySelectorAll over 50k rows would be the measurement — and
      // checks the scenario's precondition; `teardown` unmounts AND lets go
      // of every handle (see `release`).
      let view: RenderResult;
      let searchInput: HTMLElement;
      let targets: HTMLElement[] = [];
      let header: HTMLElement;
      let input: HTMLElement;
      let ring: ListviewItem[][] = [];
      const mount = (overrides: Partial<ListviewData> = {}) => {
        view = render(
          <Listview data={cellData(base, overrides)} setStateValue={noop} />,
        );
        searchInput = view.getByTestId("stListviewSearch");
        precondition(row(last) !== null, "the last row renders after mount");
      };
      const setSearch = (value: string) =>
        fireEvent.change(searchInput, { target: { value } });
      const rerenderWith = (items: ListviewItem[]) =>
        view.rerender(<Listview data={cellData(items)} setStateValue={noop} />);

      // The handles outlive the unmount, and a detached row keeps its React
      // fiber — and through it the whole unmounted tree — alive. Every cell's
      // closures live until the run ends, so without this each cell leaves its
      // last tree behind: a 1k-to-50k run held 1.4 GB of live heap after the
      // 50k cell (0.45 GB released), and the full matrix ran out of heap
      // before its last cell. `undefined as never` assigns "none" without
      // widening the handle types.
      const release = () => {
        cleanup();
        view = searchInput = header = input = undefined as never;
        targets = [];
        ring = [];
      };

      // Two pre-built fresh copies, alternated. The component keeps its own
      // retained objects whenever content is equal, so every rerun still
      // compares a payload of NEW objects against them — the real rerun path —
      // while building the copy stays out of the timed body.
      let turn = 0;
      bench("rerun_unchanged", () => rerenderWith(ring[turn++ & 1]), {
        ...cheapOpts,
        setup: () => {
          mount();
          ring = [freshCopy(base), freshCopy(base)];
          turn = 0;
        },
        teardown: release,
      });

      // An edited and an unedited copy, alternated: every iteration is then a
      // one-row change against the previous payload.
      bench("rerun_one_changed", () => rerenderWith(ring[turn++ & 1]), {
        ...cheapOpts,
        setup: () => {
          mount();
          const edited = freshCopy(base);
          edited[mid] = {
            ...edited[mid],
            label: `${edited[mid].label} (edited)`,
          };
          ring = [edited, freshCopy(base)];
          turn = 0;
        },
        teardown: release,
      });

      // Narrow to one row, then clear. The clear is the quadratic-insert path
      // the render chunks fix and dominates the number; the browser tier
      // measures the two halves apart.
      bench(
        "search_narrow_then_clear",
        () => {
          setSearch(needle);
          setSearch("");
        },
        {
          ...opts,
          setup: () => {
            mount();
            setSearch(needle);
            precondition(
              row(last) !== null && row(first) === null,
              "the needle leaves exactly the last row",
            );
            setSearch("");
            precondition(
              row(first) !== null,
              "clearing the query brings the rows back",
            );
          },
          teardown: release,
        },
      );

      // Alternate two rows so every click changes the selection.
      bench(
        "click_select",
        () => {
          fireEvent.click(targets[turn++ & 1]);
        },
        {
          ...cheapOpts,
          setup: () => {
            mount();
            targets = [row(first) as HTMLElement, row(second) as HTMLElement];
            fireEvent.click(targets[1]);
            precondition(
              targets[1].getAttribute("aria-selected") === "true",
              "a click selects the row",
            );
            turn = 0;
          },
          teardown: release,
        },
      );

      if (shape === "grouped") {
        const collapsed = () => row(first) === null;
        bench(
          "group_collapse_then_expand",
          () => {
            fireEvent.click(header);
            fireEvent.click(header);
          },
          {
            ...cheapOpts,
            setup: () => {
              mount();
              const found = view.container.querySelector<HTMLElement>(
                "button.listview-group-header--collapsible",
              );
              precondition(
                found !== null,
                "the first group header is a toggle",
              );
              header = found as HTMLElement;
              fireEvent.click(header);
              precondition(
                collapsed(),
                "clicking the header collapses the first group",
              );
              fireEvent.click(header);
              precondition(!collapsed(), "clicking it again expands the group");
            },
            teardown: release,
          },
        );
      }

      // Typing is local input state; the Enter commit builds the synthetic row
      // and runs the "already in the list?" lookup over every option. A new,
      // unique value each iteration, so no commit is a no-op.
      //
      // Every commit adds a row that STAYS (added options persist), so the
      // count is fixed at every size: tinybench's open-ended time budget would
      // grow a 100-row list by hundreds of rows and end up measuring a
      // different list than it started with. Up to 5k rows: 10 iterations +
      // the setup probe = at most 11 extra rows per mount (setup remounts for
      // each mode). Above it `cheapBudget`'s 15 + the probe = 16, negligible
      // on 10k+ rows.
      const addOpts =
        n <= 5_000
          ? { iterations: 10, time: 0, warmupIterations: 1, warmupTime: 0 }
          : cheapOpts;
      let added = 0;
      bench(
        "add_option",
        () => {
          fireEvent.change(input, { target: { value: `bench-${added++}` } });
          fireEvent.keyDown(input, { key: "Enter" });
        },
        {
          ...addOpts,
          setup: () => {
            mount({ accept_new_options: true });
            fireEvent.click(row(first) as HTMLElement);
            input = view.getByTestId("stListviewNewOption");
            fireEvent.change(input, { target: { value: "bench-probe" } });
            fireEvent.keyDown(input, { key: "Enter" });
            precondition(
              row("bench-probe") !== null,
              "Enter adds the typed option as a row",
            );
            added = 0;
          },
          teardown: release,
        },
      );
    });
  }
}
