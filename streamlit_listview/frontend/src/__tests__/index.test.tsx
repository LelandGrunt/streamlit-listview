import { describe, it, expect, vi, beforeEach } from "vitest";
import { act } from "@testing-library/react";
import type { FrontendRendererArgs } from "@streamlit/component-v2-lib";
import renderListview from "../index";
import type { ListviewData, ListviewState } from "../types";
import { makeData as makeSharedData } from "../test/makeData";

// Thin wrapper over the shared factory: this file's payloads center on a single
// ungrouped option (the glue tests only need one row to find).
function makeData(overrides: Partial<ListviewData> = {}): ListviewData {
  return makeSharedData({
    label: "Fruit",
    items: [{ id: "a", label: "Apple" }],
    ...overrides,
  });
}

function makeArgs(
  data: ListviewData,
): FrontendRendererArgs<ListviewState, ListviewData> {
  const parentElement = document.createElement("div");
  parentElement.innerHTML = '<div class="listview-root"></div>';
  return {
    data,
    key: "test-key",
    name: "streamlit_listview.listview",
    parentElement,
    setStateValue: vi.fn(),
    setTriggerValue: vi.fn(),
  };
}

describe("index renderer glue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders into the .listview-root node", async () => {
    const args = makeArgs(makeData());
    await act(async () => {
      renderListview(args);
    });
    const root = args.parentElement.querySelector(".listview-root")!;
    expect(root.childElementCount).toBeGreaterThan(0);
    // The placeholder renders the container root by its testid.
    expect(
      root.querySelector('[data-testid="stListview"]'),
    ).not.toBeNull();
  });

  it("does not call setStateValue during initial render (default= seeds it)", async () => {
    const args = makeArgs(makeData({ default_ids: ["a"] }));
    await act(async () => {
      renderListview(args);
    });
    expect(args.setStateValue).not.toHaveBeenCalled();
  });

  it("reuses one React root per parentElement across re-invocations", async () => {
    const args = makeArgs(makeData({ items: [{ id: "a", label: "Apple" }] }));
    let cleanup1: ReturnType<typeof renderListview>;
    await act(async () => {
      cleanup1 = renderListview(args);
    });
    // Re-invoke with the SAME parentElement but new data (re-render path).
    await act(async () => {
      renderListview({
        ...args,
        data: makeData({ items: [{ id: "b", label: "Banana" }] }),
      });
    });
    const root = args.parentElement.querySelector(".listview-root")!;
    // Reuse guarantee: dropping the WeakMap guard would create a SECOND React
    // root and append a duplicate tree. Exactly one container child must remain.
    expect(root.childElementCount).toBe(1);
    expect(
      root.querySelectorAll('[data-testid="stListview"]'),
    ).toHaveLength(1);
    // Reconciliation into the SAME root: the re-render replaced the old option
    // with the new one (a fresh second mount would leave the stale "a" tree).
    expect(
      root.querySelector('[data-testid="stListviewOption-b"]'),
    ).not.toBeNull();
    expect(
      root.querySelector('[data-testid="stListviewOption-a"]'),
    ).toBeNull();
    // The first call returns a usable cleanup function.
    expect(typeof cleanup1!).toBe("function");
  });

  it("cleanup unmounts and empties the root", async () => {
    const args = makeArgs(makeData());
    let cleanup!: () => void;
    await act(async () => {
      cleanup = renderListview(args) as () => void;
    });
    const root = args.parentElement.querySelector(".listview-root")!;
    await act(async () => {
      cleanup();
    });
    expect(root.childElementCount).toBe(0);
  });

  it("a second cleanup call is a no-op (the root was already dropped)", async () => {
    const args = makeArgs(makeData());
    let cleanup!: () => void;
    await act(async () => {
      cleanup = renderListview(args) as () => void;
    });
    await act(async () => {
      cleanup();
    });
    // The cached root is gone; calling cleanup again must not throw.
    await act(async () => {
      cleanup();
    });
    const root = args.parentElement.querySelector(".listview-root")!;
    expect(root.childElementCount).toBe(0);
  });

  // The renderer is where the container is resolved, because `parentElement` is
  // the only handle on the host position and it is available before the first
  // render — reading it from a hook inside the tree would land a frame late and
  // flash the main-body colors on every mount.
  it("marks the root data-in-sidebar when parentElement sits in the sidebar", async () => {
    const args = makeArgs(makeData());
    const sidebar = document.createElement("section");
    sidebar.setAttribute("data-testid", "stSidebar");
    sidebar.appendChild(args.parentElement as HTMLElement);
    document.body.appendChild(sidebar);

    await act(async () => {
      renderListview(args);
    });
    const root = args.parentElement.querySelector('[data-testid="stListview"]')!;
    expect(root.getAttribute("data-in-sidebar")).toBe("true");
  });

  it("leaves data-in-sidebar off for a main-body parentElement", async () => {
    const args = makeArgs(makeData());
    const main = document.createElement("section");
    main.setAttribute("data-testid", "stMain");
    main.appendChild(args.parentElement as HTMLElement);
    document.body.appendChild(main);

    await act(async () => {
      renderListview(args);
    });
    const root = args.parentElement.querySelector('[data-testid="stListview"]')!;
    expect(root.hasAttribute("data-in-sidebar")).toBe(false);
  });

  it("throws if the .listview-root node is missing", () => {
    const parentElement = document.createElement("div"); // no root child
    const args = {
      ...makeArgs(makeData()),
      parentElement,
    };
    expect(() => renderListview(args)).toThrow(/listview-root/);
  });
});
