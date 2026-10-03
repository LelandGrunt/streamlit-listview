import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Listview } from "./Listview";
import type { ListviewData } from "./types";
import { makeData } from "./test/makeData";

describe("Listview", () => {
  it("renders a listbox with all items grouped under static headers", () => {
    render(<Listview data={makeData()} setStateValue={vi.fn()} />);
    const listbox = screen.getByRole("listbox");
    expect(listbox).toBeInTheDocument();
    expect(screen.getByText("Fruit")).toBeInTheDocument();
    expect(screen.getByText("Veg")).toBeInTheDocument();
    const options = within(listbox).getAllByRole("option");
    expect(options).toHaveLength(4);
    expect(options.map((o) => o.textContent)).toEqual([
      "Apple",
      "Banana",
      "Carrot",
      "Disabled",
    ]);
  });

  it("renders the placeholder and no listbox options when items is empty", () => {
    render(
      <Listview
        data={makeData({ items: [], placeholder: "Nothing here" })}
        setStateValue={vi.fn()}
      />,
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.queryAllByRole("option")).toHaveLength(0);
  });

  it("renders an empty placeholder when items is empty and placeholder is null", () => {
    render(
      <Listview
        data={makeData({ items: [], placeholder: null })}
        setStateValue={vi.fn()}
      />,
    );
    const ph = screen.getByTestId("listview-placeholder");
    expect(ph.textContent).toBe("");
  });

  it("Enter on the keyboard-focused item selects it", () => {
    const setStateValue = vi.fn();
    render(<Listview data={makeData()} setStateValue={setStateValue} />);
    const listbox = screen.getByRole("listbox");
    fireEvent.keyDown(listbox, { key: "ArrowDown" }); // focus first item (Apple, id "a")
    fireEvent.keyDown(listbox, { key: "Enter" });
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["a"]);
  });

  it("seeds selection from default_ids without writing state on mount", () => {
    const setStateValue = vi.fn();
    render(
      <Listview
        data={makeData({ default_ids: ["a"] })}
        setStateValue={setStateValue}
      />,
    );
    const apple = screen.getByText("Apple").closest('[role="option"]')!;
    expect(apple.getAttribute("aria-selected")).toBe("true");
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("seeds selection from state_selection when present, ignoring default_ids", () => {
    // A remount that kept the Python-side widget state (a keyed widget moved
    // between sidebar and main) ships the persisted selection as
    // state_selection; seeding from default_ids instead would render rows that
    // disagree with the value listview() keeps returning.
    const setStateValue = vi.fn();
    render(
      <Listview
        data={makeData({ default_ids: ["a"], state_selection: ["c"] })}
        setStateValue={setStateValue}
      />,
    );
    const carrot = screen.getByText("Carrot").closest('[role="option"]')!;
    const apple = screen.getByText("Apple").closest('[role="option"]')!;
    expect(carrot.getAttribute("aria-selected")).toBe("true");
    expect(apple.getAttribute("aria-selected")).toBe("false");
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("an empty state_selection wins over default_ids (a cleared selection survives)", () => {
    // [] is a real persisted value — the user deselected everything — so it
    // must not fall through to `default` (?? semantics, not ||).
    const setStateValue = vi.fn();
    render(
      <Listview
        data={makeData({ default_ids: ["a"], state_selection: [] })}
        setStateValue={setStateValue}
      />,
    );
    const apple = screen.getByText("Apple").closest('[role="option"]')!;
    expect(apple.getAttribute("aria-selected")).toBe("false");
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("state_selection: null falls back to seeding from default_ids", () => {
    const setStateValue = vi.fn();
    render(
      <Listview
        data={makeData({ default_ids: ["b"], state_selection: null })}
        setStateValue={setStateValue}
      />,
    );
    const banana = screen.getByText("Banana").closest('[role="option"]')!;
    expect(banana.getAttribute("aria-selected")).toBe("true");
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("clicking an item selects it and writes selection state (single mode)", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(<Listview data={makeData()} setStateValue={setStateValue} />);
    await user.click(screen.getByText("Apple"));
    expect(setStateValue).toHaveBeenCalledWith("selection", ["a"]);
    const apple = screen.getByText("Apple").closest('[role="option"]')!;
    expect(apple.getAttribute("aria-selected")).toBe("true");
  });

  it("clicking an item moves roving keyboard focus to it (aria-activedescendant)", async () => {
    const user = userEvent.setup();
    render(<Listview data={makeData()} setStateValue={vi.fn()} />);
    const listbox = screen.getByRole("listbox");
    // No roving focus before interaction.
    expect(listbox.getAttribute("aria-activedescendant")).toBeNull();
    await user.click(screen.getByText("Carrot"));
    // Focus now tracks the clicked row, so a subsequent ArrowUp/Down resumes here.
    expect(listbox.getAttribute("aria-activedescendant")).toBe("listview-opt-c");
  });

  it("multi mode marks the listbox aria-multiselectable and toggles members", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({ selection_mode: "multi" })}
        setStateValue={setStateValue}
      />,
    );
    const listbox = screen.getByRole("listbox");
    expect(listbox.getAttribute("aria-multiselectable")).toBe("true");
    await user.click(screen.getByText("Apple"));
    await user.click(screen.getByText("Banana"));
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["a", "b"]);
  });

  it("does not select a disabled item", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(<Listview data={makeData()} setStateValue={setStateValue} />);
    await user.click(screen.getByText("Disabled"));
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("applies the disabled state to the whole widget and blocks selection", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    const { container } = render(
      <Listview data={makeData({ disabled: true })} setStateValue={setStateValue} />,
    );
    const root = container.querySelector(
      '[data-testid="stListview"]',
    ) as HTMLElement;
    expect(root.className).toContain("listview--disabled");
    const listbox = screen.getByRole("listbox");
    expect(listbox.getAttribute("aria-disabled")).toBe("true");
    await user.click(screen.getByText("Apple"));
    expect(setStateValue).not.toHaveBeenCalled();
  });

  it("renders ungrouped items without a header and keeps grouped headers", () => {
    render(
      <Listview
        data={makeData({
          items: [
            { id: "x", label: "Loose" },
            { id: "a", label: "Apple", group: "Fruit" },
          ],
        })}
        setStateValue={vi.fn()}
      />,
    );
    expect(screen.getByText("Loose")).toBeInTheDocument();
    expect(screen.getByText("Fruit")).toBeInTheDocument();
    // exactly one group header (Fruit); the loose item has none
    expect(
      screen.getAllByTestId("stListviewGroup"),
    ).toHaveLength(1);
  });

  it("applies layout via inline CSS variables", () => {
    const { container } = render(
      <Listview
        data={makeData({ height: 240, item_height: 36, width: 420 })}
        setStateValue={vi.fn()}
      />,
    );
    const root = container.querySelector(
      '[data-testid="stListview"]',
    ) as HTMLElement;
    expect(root.style.getPropertyValue("--listview-height")).toBe("240px");
    expect(root.style.getPropertyValue("--listview-item-height")).toBe("36px");
    expect(root.style.getPropertyValue("--listview-width")).toBe("420px");
  });

  it("omits the inline --listview-item-height var when item_height is null", () => {
    const { container } = render(
      <Listview
        data={makeData({ item_height: null })}
        setStateValue={vi.fn()}
      />,
    );
    const root = container.querySelector(
      '[data-testid="stListview"]',
    ) as HTMLElement;
    // No inline var: the listview.css default (--listview-item-height: auto on
    // the .listview root selector) wins so .listview-item min-height resolves to 'auto'.
    expect(root.style.getPropertyValue("--listview-item-height")).toBe("");
  });

  it("sets the --listview-content-font-size var when content_font_size is provided", () => {
    const { container } = render(
      <Listview
        data={makeData({ content_font_size: 13 })}
        setStateValue={vi.fn()}
      />,
    );
    const root = container.querySelector(
      '[data-testid="stListview"]',
    ) as HTMLElement;
    expect(root.style.getPropertyValue("--listview-content-font-size")).toBe(
      "13px",
    );
  });

  it("omits the --listview-content-font-size var when content_font_size is null", () => {
    const { container } = render(
      <Listview
        data={makeData({ content_font_size: null })}
        setStateValue={vi.fn()}
      />,
    );
    const root = container.querySelector(
      '[data-testid="stListview"]',
    ) as HTMLElement;
    // No inline var: listview.css falls back to calc(var(--st-base-font-size)*0.875).
    expect(root.style.getPropertyValue("--listview-content-font-size")).toBe("");
  });

  it("sets width to 100% when width is 'stretch'", () => {
    const { container } = render(
      <Listview data={makeData({ width: "stretch" })} setStateValue={vi.fn()} />,
    );
    const root = container.querySelector(
      '[data-testid="stListview"]',
    ) as HTMLElement;
    expect(root.style.getPropertyValue("--listview-width")).toBe("100%");
  });

  // The attribute is the whole interface between the container lookup and the
  // sheet's sidebar block, which un-swaps the two surface tokens Streamlit's
  // sidebar theme trades. It must be ABSENT (not "false") in the main body, so
  // the default rules keep applying there untouched.
  it("marks the root data-in-sidebar only when mounted in the sidebar", () => {
    const { container, rerender } = render(
      <Listview data={makeData()} setStateValue={vi.fn()} />,
    );
    const root = () =>
      container.querySelector('[data-testid="stListview"]') as HTMLElement;
    expect(root().hasAttribute("data-in-sidebar")).toBe(false);
    rerender(<Listview data={makeData()} setStateValue={vi.fn()} inSidebar />);
    expect(root().getAttribute("data-in-sidebar")).toBe("true");
  });

  it("adds the listview--no-grid class only when show_grid_lines is false", () => {
    const { container, rerender } = render(
      <Listview data={makeData({ show_grid_lines: true })} setStateValue={vi.fn()} />,
    );
    const root = () =>
      container.querySelector('[data-testid="stListview"]') as HTMLElement;
    expect(root().classList.contains("listview--no-grid")).toBe(false);
    rerender(
      <Listview data={makeData({ show_grid_lines: false })} setStateValue={vi.fn()} />,
    );
    expect(root().classList.contains("listview--no-grid")).toBe(true);
  });
});

// ── Task 9: search, collapse, new options, Escape, jump-to-default ──────────

function baseData(overrides: Partial<ListviewData> = {}): ListviewData {
  return makeData({
    label: "L",
    items: [
      { id: "apple", label: "Apple", group: "Fruit" },
      { id: "banana", label: "Banana", group: "Fruit" },
      { id: "carrot", label: "Carrot", group: "Veg" },
    ],
    ...overrides,
  });
}

beforeEach(() => {
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("search", () => {
  it("renders no search field when enable_search=false", () => {
    render(<Listview data={baseData()} setStateValue={vi.fn()} />);
    expect(screen.queryByTestId("stListviewSearch")).toBeNull();
  });

  it("filters items as the user types", async () => {
    const user = userEvent.setup();
    render(<Listview data={baseData({ enable_search: true })} setStateValue={vi.fn()} />);
    await user.type(screen.getByTestId("stListviewSearch"), "car");
    expect(screen.getByText("Carrot")).toBeInTheDocument();
    expect(screen.queryByText("Apple")).toBeNull();
  });

  it("pin_search renders the field in a non-scrolling header strip", () => {
    const { container } = render(
      <Listview data={baseData({ enable_search: true, pin_search: true })} setStateValue={vi.fn()} />,
    );
    const header = container.querySelector(".listview-header");
    expect(header).not.toBeNull();
    expect(header!.querySelector('[data-testid="stListviewSearch"]')).not.toBeNull();
  });

  it("in-flow search (pin_search=false) places the field inside the scroll body, not the header", () => {
    const { container } = render(
      <Listview data={baseData({ enable_search: true, pin_search: false })} setStateValue={vi.fn()} />,
    );
    expect(container.querySelector(".listview-header")).toBeNull();
    expect(
      container.querySelector('.listview-body [data-testid="stListviewSearch"]'),
    ).not.toBeNull();
  });

  it('pressing "/" in the listbox focuses the search field', () => {
    render(<Listview data={baseData({ enable_search: true })} setStateValue={vi.fn()} />);
    const listbox = screen.getByRole("listbox");
    const search = screen.getByTestId("stListviewSearch");
    expect(document.activeElement).not.toBe(search);
    fireEvent.keyDown(listbox, { key: "/" });
    expect(document.activeElement).toBe(search);
  });
});

describe("collapsible groups", () => {
  it("collapsing a group hides its items but keeps the header", async () => {
    const user = userEvent.setup();
    render(
      <Listview
        data={baseData({ collapsible_groups: true })}
        setStateValue={vi.fn()}
      />,
    );
    const fruitHeader = screen.getByRole("button", { name: /Fruit/ });
    await user.click(fruitHeader);
    expect(screen.queryByText("Apple")).toBeNull();
    expect(fruitHeader).toHaveAttribute("aria-expanded", "false");
    // sibling group untouched
    expect(screen.getByText("Carrot")).toBeInTheDocument();
  });

  it("collapsed_groups seeds the initial collapsed state", () => {
    render(
      <Listview
        data={baseData({ collapsible_groups: true, collapsed_groups: ["Fruit"] })}
        setStateValue={vi.fn()}
      />,
    );
    expect(screen.queryByText("Apple")).toBeNull();
    expect(screen.getByText("Carrot")).toBeInTheDocument();
  });

  it("search overrides collapse: a matching item in a collapsed group still shows", async () => {
    const user = userEvent.setup();
    render(
      <Listview
        data={baseData({ enable_search: true, collapsible_groups: true, collapsed_groups: "all" })}
        setStateValue={vi.fn()}
      />,
    );
    expect(screen.queryByText("Apple")).toBeNull(); // collapsed initially
    await user.type(screen.getByTestId("stListviewSearch"), "apple");
    expect(screen.getByText("Apple")).toBeInTheDocument();
  });
});

describe("accept_new_options", () => {
  it("renders the entry row only when accept_new_options=true", () => {
    const { rerender } = render(
      <Listview data={baseData()} setStateValue={vi.fn()} />,
    );
    expect(screen.queryByTestId("stListviewNewOption")).toBeNull();
    rerender(<Listview data={baseData({ accept_new_options: true })} setStateValue={vi.fn()} />);
    expect(screen.getByTestId("stListviewNewOption")).toBeInTheDocument();
  });

  it("adding a new option selects it, renders it as a row, and writes state", async () => {
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({ accept_new_options: true, selection_mode: "multi" })}
        setStateValue={setStateValue}
      />,
    );
    await user.type(screen.getByTestId("stListviewNewOption"), "Mango");
    await user.keyboard("{Enter}");
    expect(screen.getByText("Mango")).toBeInTheDocument();
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["Mango"]);
  });

  it("adding the same new option twice yields a single row (dedup)", async () => {
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({ accept_new_options: true, selection_mode: "multi" })}
        setStateValue={setStateValue}
      />,
    );
    const input = screen.getByTestId("stListviewNewOption");
    await user.type(input, "Mango");
    await user.keyboard("{Enter}");
    await user.type(input, "Mango");
    await user.keyboard("{Enter}");
    // remembered once, selected once — exactly one synthetic row
    expect(screen.getAllByText("Mango")).toHaveLength(1);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["Mango"]);
  });

  it("typing an existing numeric id selects that option, not a duplicate string row", async () => {
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          items: [
            { id: 1, label: "One" },
            { id: 2, label: "Two" },
          ],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={setStateValue}
      />,
    );
    await user.type(screen.getByTestId("stListviewNewOption"), "1");
    await user.keyboard("{Enter}");
    // selects the existing numeric option (id 1), NOT a new string "1"
    expect(setStateValue).toHaveBeenLastCalledWith("selection", [1]);
    // no duplicate row was added
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("typing the string form of a numeric synthetic id resolves to it, not a duplicate row", async () => {
    // A numeric default not in options seeds a synthetic row {id: 7, label "7"}.
    // Typing "7" must resolve to that existing id (number 7) rather than create a
    // second {id: "7"} row — which would collide on the React key and the DOM id
    // (both String(7) === "7").
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          items: [{ id: 1, label: "One" }],
          accept_new_options: true,
          selection_mode: "multi",
          default_ids: [7],
        })}
        setStateValue={setStateValue}
      />,
    );
    expect(screen.getByText("7")).toBeInTheDocument(); // synthetic numeric row
    await user.type(screen.getByTestId("stListviewNewOption"), "7");
    await user.keyboard("{Enter}");
    expect(screen.getAllByText("7")).toHaveLength(1); // no duplicate
    const sevenRows = screen
      .getAllByRole("option")
      .filter((o) => o.textContent === "7");
    expect(sevenRows).toHaveLength(1);
  });

  it("seeds a typed value carried in state_selection as a persistent added row", async () => {
    // Before a remount, the typed value lived in addedItems (frontend state
    // that the remount destroys). It comes back through state_selection, and
    // must re-seed addedItems — not just render while selected — so
    // deselecting it after the remount keeps the row, exactly as it would have
    // without the remount.
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          accept_new_options: true,
          selection_mode: "multi",
          default_ids: [],
          state_selection: ["Mango"],
        })}
        setStateValue={setStateValue}
      />,
    );
    const mango = screen.getByText("Mango").closest('[role="option"]')!;
    expect(mango.getAttribute("aria-selected")).toBe("true");
    expect(setStateValue).not.toHaveBeenCalled();
    await user.click(screen.getByText("Mango"));
    expect(setStateValue).toHaveBeenLastCalledWith("selection", []);
    // Deselected, but still in the list as a re-selectable row.
    expect(screen.getByText("Mango")).toBeInTheDocument();
  });

  it("seeds no synthetic row for a default that spells a known option's id differently", () => {
    // Python now ships a matched default in the option's own spelling, but the
    // seed can still arrive as "7" against the numeric option id 7 — a persisted
    // state_selection typed under accept_new_options before the caller promoted
    // the value into `options` as an int. That is ONE row, so the seeded
    // added-options list must recognise it by row identity: seeding it as
    // unknown would carry a phantom {id: "7"} entry alongside the real option.
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          items: [{ id: 7, label: "Seven" }],
          accept_new_options: true,
          selection_mode: "multi",
          default_ids: ["7"],
        })}
        setStateValue={setStateValue}
      />,
    );
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByText("Seven")).toBeInTheDocument();
    // Reconciliation canonicalises the seeded "7" onto the option's id and
    // commits it, so what listview() returns is the option, not a bare string.
    expect(setStateValue).toHaveBeenLastCalledWith("selection", [7]);
  });

  it("drops a stale string-id added option once it is promoted into options with a numeric id", async () => {
    // The user adds "5" (string), then the caller promotes it into options with a
    // NUMERIC id 5. String(id) is the row-identity model, so only ONE "5" row must
    // show — not the stale string-id added row beside the numeric option's row.
    const user = userEvent.setup();
    const { rerender } = render(
      <Listview
        data={baseData({
          items: [{ id: "x", label: "X" }],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={vi.fn()}
      />,
    );
    await user.type(screen.getByTestId("stListviewNewOption"), "5");
    await user.keyboard("{Enter}");
    expect(screen.getAllByText("5")).toHaveLength(1);
    rerender(
      <Listview
        data={baseData({
          items: [
            { id: "x", label: "X" },
            { id: 5, label: "5" },
          ],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={vi.fn()}
      />,
    );
    expect(screen.getAllByText("5")).toHaveLength(1); // no stale duplicate
  });

  it("typing an existing option's VISIBLE label selects that option instead of duplicating it", async () => {
    // The user only ever sees labels: Python applies format_func / label
    // server-side, so an option {"id": "apple", "label": "Apple"} shows no trace
    // of its id. Matching the typed text against ids alone produced two rows both
    // reading "Apple" and committed the bare string "Apple" beside the option
    // object for the same visible entry.
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          items: [
            { id: "apple", label: "Apple" },
            { id: "banana", label: "Banana" },
          ],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={setStateValue}
      />,
    );
    await user.type(screen.getByTestId("stListviewNewOption"), "Apple");
    await user.keyboard("{Enter}");
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["apple"]);
    expect(screen.getAllByText("Apple")).toHaveLength(1); // no twin row
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("matches a typed value against labels with the search fold (case + ß)", async () => {
    // Same fold as the search filter, so anything the user could FIND by typing it
    // into the search box also counts as "already in the list".
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          items: [
            { id: 1, label: "Bahnhofstraße" },
            { id: 2, label: "Apple" },
          ],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={setStateValue}
      />,
    );
    const input = screen.getByTestId("stListviewNewOption");
    await user.type(input, "BAHNHOFSTRASSE");
    await user.keyboard("{Enter}");
    expect(setStateValue).toHaveBeenLastCalledWith("selection", [1]);
    await user.type(input, "apple");
    await user.keyboard("{Enter}");
    expect(setStateValue).toHaveBeenLastCalledWith("selection", [1, 2]);
    expect(screen.getAllByRole("option")).toHaveLength(2); // still no new rows
  });

  it("falls back to a folded match on the id when the label differs", async () => {
    // Plain (non-dict) options have id === label, but a dict option or a
    // format_func can give a row a label that no longer contains its id. A typed
    // value that spells the id still belongs to that row.
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          items: [{ id: "Apple", label: "Granny Smith" }],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={setStateValue}
      />,
    );
    await user.type(screen.getByTestId("stListviewNewOption"), "apple");
    await user.keyboard("{Enter}");
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["Apple"]);
    expect(screen.getAllByRole("option")).toHaveLength(1); // no second row
  });

  it("a visible-label match on a later row beats an id match on an earlier one", async () => {
    // Labels are the only thing the user can see, so ALL labels are scanned
    // before any id (two passes, not one combined test per row). A single pass
    // let the first row's hidden id "berlin" shadow the second row's visible
    // label "Berlin" — typing exactly what a row says selected a different row.
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          items: [
            { id: "berlin", label: "München" },
            { id: "muenchen", label: "Berlin" },
          ],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={setStateValue}
      />,
    );
    await user.type(screen.getByTestId("stListviewNewOption"), "BERLIN");
    await user.keyboard("{Enter}");
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["muenchen"]);
    expect(screen.getAllByRole("option")).toHaveLength(2); // no new row
  });

  it("still adds a value that only PARTIALLY matches an existing label", async () => {
    // Resolution is by whole (folded) label, not by substring — "App" is a new
    // option even though "Apple" contains it.
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          items: [{ id: "apple", label: "Apple" }],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={setStateValue}
      />,
    );
    await user.type(screen.getByTestId("stListviewNewOption"), "App");
    await user.keyboard("{Enter}");
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["App"]);
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("renders added entries in a block of their own at the very bottom", async () => {
    // README promise: added entries are appended at the bottom. Grouping the
    // caller's options and the added rows separately is what keeps that true when
    // the list MIXES grouped and ungrouped options — a single grouping pass merged
    // the added row into the first ungrouped block, which sits above the group.
    const user = userEvent.setup();
    render(
      <Listview
        data={baseData({
          items: [
            { id: "z", label: "Zulu" },
            { id: "b", label: "Bravo", group: "G" },
          ],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={vi.fn()}
      />,
    );
    await user.type(screen.getByTestId("stListviewNewOption"), "new");
    await user.keyboard("{Enter}");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Zulu",
      "Bravo",
      "new",
    ]);
    // ... and below the group header, not above it
    const header = screen.getByText("G");
    const added = screen.getByText("new");
    expect(
      header.compareDocumentPosition(added) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // keyboard order follows the rendered order: End lands on the added row
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "End" });
    expect(screen.getByRole("listbox").getAttribute("aria-activedescendant")).toBe(
      "listview-opt-new",
    );
  });

  it("at the cap, adding a new option neither selects it nor leaves a phantom row", async () => {
    // multi mode at max_selections: selection.add() is a no-op, so the typed
    // value must NOT be persisted as an unselected/muted row the user can't
    // remove and never actually selected.
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({
          accept_new_options: true,
          selection_mode: "multi",
          max_selections: 1,
          default_ids: ["apple"], // already at the cap
        })}
        setStateValue={setStateValue}
      />,
    );
    setStateValue.mockClear();
    await user.type(screen.getByTestId("stListviewNewOption"), "Mango");
    await user.keyboard("{Enter}");
    expect(screen.queryByText("Mango")).toBeNull(); // no phantom row
    expect(setStateValue).not.toHaveBeenCalled(); // no selection change
  });

  it("keeps an added option as a re-selectable row after another option is picked (single mode)", async () => {
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({ accept_new_options: true, selection_mode: "single" })}
        setStateValue={setStateValue}
      />,
    );
    // Add a new option: in single mode it becomes the sole selection and a row.
    await user.type(screen.getByTestId("stListviewNewOption"), "Mango");
    await user.keyboard("{Enter}");
    expect(screen.getByText("Mango")).toBeInTheDocument();

    // Picking a different existing option replaces the selection ...
    await user.click(screen.getByText("Apple"));
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["apple"]);

    // ... but the added option must STAY in the list, unselected and re-selectable.
    const mango = screen.getByText("Mango").closest('[role="option"]')!;
    expect(mango).toBeInTheDocument();
    expect(mango.getAttribute("aria-selected")).toBe("false");
    await user.click(screen.getByText("Mango"));
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["Mango"]);
  });

  it("swaps the synthetic block when an equal-sized rebuild spells different rows", async () => {
    // Branch partner of the identity test (Listview.identity.test.tsx): the
    // synthetic-rows memo keeps the previous ARRAY when a rebuild is
    // element-wise identical, so a rebuild of the SAME SIZE naming different
    // rows must not be mistaken for one — the new rows have to render.
    const user = userEvent.setup();
    const items = [
      { id: "a", label: "A" },
      { id: "b", label: "B" },
      { id: "c", label: "C" },
    ];
    const rows = () => screen.getAllByRole("option").map((o) => o.textContent);
    const { rerender } = render(
      <Listview
        data={baseData({ items, accept_new_options: true, selection_mode: "multi" })}
        setStateValue={vi.fn()}
      />,
    );
    await user.click(screen.getByText("B"));
    await user.click(screen.getByText("C"));
    // Drop b from options: the selected "b" survives as ONE synthetic row
    // (labelled by its idKey, hence lowercase).
    rerender(
      <Listview
        data={baseData({
          items: [items[0], items[2]],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={vi.fn()}
      />,
    );
    expect(rows()).toEqual(["A", "C", "b"]);
    // Restore b, drop c: still one synthetic row, but a DIFFERENT one.
    rerender(
      <Listview
        data={baseData({
          items: [items[0], items[1]],
          accept_new_options: true,
          selection_mode: "multi",
        })}
        setStateValue={vi.fn()}
      />,
    );
    expect(rows()).toEqual(["A", "B", "c"]);
  });
});

describe("Escape", () => {
  it("clears the query first, then the selection", async () => {
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({ enable_search: true, default_ids: ["apple"] })}
        setStateValue={setStateValue}
      />,
    );
    const search = screen.getByTestId("stListviewSearch");
    await user.type(search, "car");
    // first Escape clears the query (selection untouched)
    fireEvent.keyDown(search, { key: "Escape" });
    expect((search as HTMLInputElement).value).toBe("");
    expect(setStateValue).not.toHaveBeenCalled();
    // focus the listbox and Escape again → clears selection
    const listbox = screen.getByRole("listbox");
    fireEvent.keyDown(listbox, { key: "Escape" });
    expect(setStateValue).toHaveBeenLastCalledWith("selection", []);
  });

  it("clears a whitespace-only query before touching the selection", async () => {
    // Regression: the branch keyed off `isFiltering`, which folds (trims) the
    // query — so a box holding only spaces counted as "not filtering", and
    // Escape wiped the selection (a state write + on_change) while the spaces
    // and the × clear button stayed visible. Escape must agree with the box.
    const user = userEvent.setup();
    const setStateValue = vi.fn();
    render(
      <Listview
        data={baseData({ enable_search: true, default_ids: ["apple"] })}
        setStateValue={setStateValue}
      />,
    );
    const search = screen.getByTestId("stListviewSearch") as HTMLInputElement;
    await user.type(search, "   ");
    expect(screen.getByRole("button", { name: "Clear search" })).toBeInTheDocument();
    fireEvent.keyDown(search, { key: "Escape" });
    expect(search.value).toBe("");
    expect(setStateValue).not.toHaveBeenCalled();
    // The box is empty now, so the next Escape is for the selection.
    fireEvent.keyDown(search, { key: "Escape" });
    expect(setStateValue).toHaveBeenLastCalledWith("selection", []);
  });
});

/**
 * Give the scroll frame and one row a fake geometry, since jsdom does no layout:
 * the frame sits at viewport y=0 and is `frame` px tall; the row sits `top` px
 * below the frame's top edge (i.e. in unscrolled content coordinates) and is
 * `height` px tall. `scrollTop` is made a real read/write property so the
 * container's scroll math is observable. `header` is the height of the row's
 * sticky group header, when the row has one (jsdom otherwise reports 0).
 */
function stubGeometry(
  body: HTMLElement,
  row: HTMLElement,
  { frame = 100, top = 0, height = 20, scrollTop = 0, header = 0 } = {},
): void {
  Object.defineProperty(body, "clientHeight", { value: frame, configurable: true });
  body.scrollTop = scrollTop; // jsdom stores the assignment
  body.getBoundingClientRect = () =>
    ({ top: 0, height: frame }) as DOMRect;
  row.getBoundingClientRect = () =>
    ({ top: top - body.scrollTop, height }) as DOMRect;
  const headerEl = row.parentElement?.querySelector(".listview-group-header");
  if (headerEl) {
    headerEl.getBoundingClientRect = () => ({ top: 0, height: header }) as DOMRect;
  }
}

function rowFor(label: string): HTMLElement {
  return screen.getByText(label).closest('[role="option"]') as HTMLElement;
}

describe("jump to default", () => {
  it("centers the first default id in the LIST BODY without scrolling the page", () => {
    // Element.scrollIntoView() would scroll every scrollable ancestor, including
    // the Streamlit page — a listview below the fold would yank the host page's
    // scroll position away from whatever the user was reading. Only
    // .listview-body may move.
    const scrollSpy = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    const setStateValue = vi.fn();
    const { container, rerender } = render(
      <Listview
        data={baseData({ default_ids: ["apple"] })}
        setStateValue={setStateValue}
      />,
    );
    const body = container.querySelector(".listview-body") as HTMLElement;
    stubGeometry(body, rowFor("Carrot"), { frame: 100, top: 260, height: 20 });
    // A default_ids change by value re-triggers the jump.
    rerender(
      <Listview
        data={baseData({ default_ids: ["carrot"] })}
        setStateValue={setStateValue}
      />,
    );
    // centered: row top 260, frame 100, row 20 tall -> 260 - (100-20)/2
    expect(body.scrollTop).toBe(220);
    expect(scrollSpy).not.toHaveBeenCalled();
    scrollSpy.mockRestore();
  });

  it("does not scroll when the target row is not rendered", () => {
    // The jump resolves its target against the (unfiltered) items, so an active
    // search can hide the very row it wants to scroll to.
    const setStateValue = vi.fn();
    const { container, rerender } = render(
      <Listview
        data={baseData({ enable_search: true, default_ids: ["apple"] })}
        setStateValue={setStateValue}
      />,
    );
    const body = container.querySelector(".listview-body") as HTMLElement;
    fireEvent.change(screen.getByTestId("stListviewSearch"), {
      target: { value: "apple" },
    });
    stubGeometry(body, rowFor("Apple"), { frame: 100, top: 260, height: 20 });
    body.scrollTop = 7;
    rerender(
      <Listview
        data={baseData({ enable_search: true, default_ids: ["carrot"] })}
        setStateValue={setStateValue}
      />,
    );
    expect(screen.queryByText("Carrot")).toBeNull(); // filtered out
    expect(body.scrollTop).toBe(7); // untouched
  });

  it("scrolls to a default id containing CSS-selector metacharacters without throwing", () => {
    // An id like `a"]` terminates a naive `[id="…"]` attribute selector, and a
    // newline cannot appear raw in a CSS string at all — querySelector then threw
    // SyntaxError from inside the rAF callback, where no React error boundary can
    // catch it. The row lookup compares id properties, so none of these is special.
    for (const trickyId of ['a"]', "line1\nline2", "back\\slash", "12start"]) {
      const items = [
        { id: "other", label: "Other" },
        { id: trickyId, label: "Tricky" },
      ];
      const { container, rerender, unmount } = render(
        <Listview
          data={baseData({ items, default_ids: ["other"] })}
          setStateValue={vi.fn()}
        />,
      );
      const body = container.querySelector(".listview-body") as HTMLElement;
      stubGeometry(body, rowFor("Tricky"), { frame: 100, top: 300, height: 20 });
      rerender(
        <Listview
          data={baseData({ items, default_ids: [trickyId] })}
          setStateValue={vi.fn()}
        />,
      );
      expect(body.scrollTop).toBe(260); // centered: 300 - (100 - 20)/2
      unmount();
    }
  });
});

describe("group item counts", () => {
  it("shows each group's item count in its header", () => {
    render(<Listview data={baseData()} setStateValue={vi.fn()} />);
    const fruit = screen.getByText("Fruit").closest('[data-testid="stListviewGroup"]')!;
    const veg = screen.getByText("Veg").closest('[data-testid="stListviewGroup"]')!;
    expect(fruit).toHaveTextContent("(2)");
    expect(veg).toHaveTextContent("(1)");
  });

  it("counts only the matching items while a search filter is active", async () => {
    const user = userEvent.setup();
    render(<Listview data={baseData({ enable_search: true })} setStateValue={vi.fn()} />);
    await user.type(screen.getByTestId("stListviewSearch"), "apple");
    const fruit = screen.getByText("Fruit").closest('[data-testid="stListviewGroup"]')!;
    expect(fruit).toHaveTextContent("(1)"); // only Apple matches
    expect(screen.queryByText("Veg")).toBeNull(); // no matches → group not rendered
  });

  it("shows the full count for a collapsed group", () => {
    render(
      <Listview
        data={baseData({ collapsible_groups: true, collapsed_groups: ["Fruit"] })}
        setStateValue={vi.fn()}
      />,
    );
    const fruit = screen.getByRole("button", { name: /Fruit/ });
    expect(screen.queryByText("Apple")).toBeNull(); // rows hidden
    expect(fruit).toHaveTextContent("(2)"); // full count still shown
  });
});

describe("Listview select_all toggle", () => {
  it("renders no toggle when select_all is off", () => {
    render(<Listview data={makeData({ selection_mode: "multi" })} setStateValue={vi.fn()} />);
    expect(screen.queryByTestId("stListviewSelectAllToggle")).toBeNull();
  });

  it("renders the toggle in a header (no pinned search) and the seam flattens the body top radius", () => {
    const { container } = render(
      <Listview
        data={makeData({ selection_mode: "multi", select_all: true })}
        setStateValue={vi.fn()}
      />,
    );
    const header = container.querySelector(".listview-header") as HTMLElement;
    expect(header).not.toBeNull();
    expect(within(header).getByTestId("stListviewSelectAllToggle")).toBeInTheDocument();
    // seam: header is immediately followed by the body (the
    // `.listview-header + .listview-body` CSS rule flattens the body top radius).
    const body = header.nextElementSibling as HTMLElement;
    expect(body.classList.contains("listview-body")).toBe(true);
  });

  it("renders SearchField first then SelectAllToggle when pinned search + select_all are both on", () => {
    const { container } = render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          enable_search: true,
          pin_search: true,
        })}
        setStateValue={vi.fn()}
      />,
    );
    const header = container.querySelector(".listview-header") as HTMLElement;
    const search = within(header).getByTestId("stListviewSearch");
    const toggle = within(header).getByTestId("stListviewSelectAllToggle");
    // SearchField appears before the toggle in DOM order (Tab reaches search first).
    expect(
      search.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("Select all selects collapsed-group rows and excludes disabled rows (scope = visibleItems)", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          collapsible_groups: true,
          collapsed_groups: "all",
        })}
        setStateValue={setStateValue}
      />,
    );
    await user.click(screen.getByTestId("stListviewSelectAllToggle"));
    // a,b,c selectable; d disabled excluded; collapsed groups still in scope.
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["a", "b", "c"]);
  });

  it("targetIds includes accept_new_options synthetic rows in scope", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          accept_new_options: true,
          // a synthetic selected-but-unknown id surfaces as a visible row
          default_ids: ["zeta"],
        })}
        setStateValue={setStateValue}
      />,
    );
    await user.click(screen.getByTestId("stListviewSelectAllToggle"));
    // the synthetic 'zeta' row is part of the visible scope and stays selected
    // alongside the known selectable rows.
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["zeta", "a", "b", "c"]);
  });

  it("label flips to Deselect all when all visible selectable rows are selected", () => {
    render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          default_ids: ["a", "b", "c"],
        })}
        setStateValue={vi.fn()}
      />,
    );
    expect(screen.getByTestId("stListviewSelectAllToggle")).toHaveTextContent(
      "Deselect all",
    );
  });

  it("label flips to Deselect all when selection.length >= max_selections", () => {
    render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          max_selections: 2,
          default_ids: ["a", "b"],
        })}
        setStateValue={vi.fn()}
      />,
    );
    expect(screen.getByTestId("stListviewSelectAllToggle")).toHaveTextContent(
      "Deselect all",
    );
  });

  it("toggle is disabled and reads Select all when the widget is disabled", () => {
    render(
      <Listview
        data={makeData({ selection_mode: "multi", select_all: true, disabled: true })}
        setStateValue={vi.fn()}
      />,
    );
    const toggle = screen.getByTestId("stListviewSelectAllToggle");
    expect(toggle).toBeDisabled();
    expect(toggle).toHaveTextContent("Select all");
  });

  it("toggle is disabled and reads Select all when the visible scope is empty (search matches nothing)", async () => {
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({ selection_mode: "multi", select_all: true, enable_search: true })}
        setStateValue={vi.fn()}
      />,
    );
    await user.type(screen.getByTestId("stListviewSearch"), "zzzzz");
    const toggle = screen.getByTestId("stListviewSelectAllToggle");
    expect(toggle).toBeDisabled();
    expect(toggle).toHaveTextContent("Select all");
  });

  it("Deselect all removes matching rows but preserves out-of-view selections", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          enable_search: true,
          default_ids: ["a", "b", "c"],
        })}
        setStateValue={setStateValue}
      />,
    );
    // Filter to just "Apple" (id a); b and c are out of view.
    await user.type(screen.getByTestId("stListviewSearch"), "Apple");
    const toggle = screen.getByTestId("stListviewSelectAllToggle");
    expect(toggle).toHaveTextContent("Deselect all"); // the only visible row is selected
    await user.click(toggle);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["b", "c"]);
  });

  it("does not show an actionable 'Deselect all' when the cap was reached by out-of-view rows", async () => {
    // Regression: at the cap, the toggle used to flip to "Deselect all" purely
    // because selection.length >= max_selections — even when the search filters
    // OUT the selected rows. deselectVisible(targetIds) then removed nothing, so
    // the enabled "Deselect all" was a dead button. With nothing visible to
    // deselect and no room to select more, the toggle must be disabled and read
    // "Select all".
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          enable_search: true,
          max_selections: 2,
          default_ids: ["b", "c"], // at the cap; both selectable, both off-view once filtered
        })}
        setStateValue={setStateValue}
      />,
    );
    // Filter to "Apple" (id a) — NOT one of the selected rows.
    await user.type(screen.getByTestId("stListviewSearch"), "Apple");
    const toggle = screen.getByTestId("stListviewSelectAllToggle");
    expect(toggle).toHaveTextContent("Select all"); // not a misleading "Deselect all"
    expect(toggle).toBeDisabled(); // cap blocks selecting; nothing visible to deselect
  });

  it("at the cap with the selected rows visible, 'Deselect all' is actionable and clears them", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          max_selections: 2,
          default_ids: ["a", "b"], // at the cap; both visible (no search)
        })}
        setStateValue={setStateValue}
      />,
    );
    const toggle = screen.getByTestId("stListviewSelectAllToggle");
    expect(toggle).toHaveTextContent("Deselect all");
    expect(toggle).not.toBeDisabled();
    await user.click(toggle);
    expect(setStateValue).toHaveBeenLastCalledWith("selection", []);
  });

  it("with room under the cap, 'Select all' is enabled and fills up to max_selections", async () => {
    const setStateValue = vi.fn();
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({
          selection_mode: "multi",
          select_all: true,
          max_selections: 2, // below cap initially (nothing selected)
        })}
        setStateValue={setStateValue}
      />,
    );
    const toggle = screen.getByTestId("stListviewSelectAllToggle");
    expect(toggle).toHaveTextContent("Select all");
    expect(toggle).not.toBeDisabled();
    await user.click(toggle);
    // a, b selectable in list order; capped at 2.
    expect(setStateValue).toHaveBeenLastCalledWith("selection", ["a", "b"]);
  });
});

// ── Group blocks: React keys + ARIA structure ────────────────────────────────

describe("group blocks", () => {
  it("keeps sibling blocks distinct when a real group is named like the ungrouped sentinel", () => {
    // Regression: the ungrouped block was keyed with the literal string
    // "__ungrouped__", which Python happily accepts as a group name. Two sibling
    // blocks then shared ONE React key, and the corrupted reconciliation leaked
    // blocks, grew phantom rows across successive filter changes, repeated an
    // option DOM id, and left rows on screen that did not match the query.
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const items = [
      { id: "z", label: "Zulu", group: "__ungrouped__" },
      { id: "a", label: "Alpha" }, // genuinely ungrouped
      { id: "b", label: "Bravo", group: "X" },
    ];
    render(
      <Listview
        data={baseData({ items, enable_search: true })}
        setStateValue={vi.fn()}
      />,
    );
    const search = screen.getByTestId("stListviewSearch");
    const rows = () => screen.getAllByRole("option").map((o) => o.textContent);
    expect(rows()).toEqual(["Zulu", "Alpha", "Bravo"]);
    // walk the filter through several states; every step must match the query
    for (const [query, expected] of [
      ["a", ["Alpha", "Bravo"]],
      ["al", ["Alpha"]],
      ["", ["Zulu", "Alpha", "Bravo"]],
      ["brav", ["Bravo"]],
    ] as const) {
      fireEvent.change(search, { target: { value: query } });
      expect(rows()).toEqual([...expected]);
      // no phantom / duplicated DOM ids
      const ids = screen.getAllByRole("option").map((o) => o.id);
      expect(new Set(ids).size).toBe(ids.length);
    }
    // no "two children with the same key" warning anywhere along the way
    expect(errors).not.toHaveBeenCalled();
    errors.mockRestore();
  });

  it("exposes each named group as a role=group inside the listbox, with the header hidden", () => {
    // A flat option list hid the grouping from AT entirely; the header text was
    // also non-option content inside the listbox, which AT may read as an item.
    render(<Listview data={makeData()} setStateValue={vi.fn()} />);
    const listbox = screen.getByRole("listbox");
    const groups = within(listbox).getAllByRole("group");
    expect(groups.map((g) => g.getAttribute("aria-label"))).toEqual([
      "Fruit",
      "Veg",
    ]);
    expect(
      within(groups[0])
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Apple", "Banana"]);
    // the visible header is hidden from the tree — the group's name carries it
    for (const header of screen.getAllByTestId("stListviewGroup")) {
      expect(header.getAttribute("aria-hidden")).toBe("true");
    }
  });

  it("gives the ungrouped block no group role (there is no name to give it)", () => {
    render(
      <Listview
        data={baseData({
          items: [
            { id: "x", label: "Loose" },
            { id: "a", label: "Apple", group: "Fruit" },
          ],
        })}
        setStateValue={vi.fn()}
      />,
    );
    const groups = screen.getAllByRole("group");
    expect(groups).toHaveLength(1);
    expect(groups[0].getAttribute("aria-label")).toBe("Fruit");
    // the loose row is not inside it
    expect(within(groups[0]).queryByText("Loose")).toBeNull();
  });

  describe("rows beyond one render chunk", () => {
    // A block renders its rows in chunks of 100 (the cure for React's quadratic
    // sibling search when thousands of rows enter one parent at once). 250 rows
    // span three chunks, the last one partial, and the chunks must stay
    // invisible: the same rows, in the same order, under the same parent — also
    // while the filter moves rows across chunk boundaries.
    const rowLabel = (i: number) => `Row ${String(i).padStart(3, "0")}`;
    const rowLabels = (from: number, to: number) =>
      Array.from({ length: to - from }, (_, k) => rowLabel(from + k));
    const rows = (group?: string) =>
      Array.from({ length: 250 }, (_, i) => ({
        id: `r${i}`,
        label: rowLabel(i),
        ...(group === undefined ? {} : { group }),
      }));
    const shown = () =>
      screen.queryAllByRole("option").map((o) => o.textContent);

    it("renders every row in order, all children of the one block", () => {
      render(
        <Listview data={baseData({ items: rows() })} setStateValue={vi.fn()} />,
      );
      const options = screen.getAllByRole("option");
      expect(options.map((o) => o.textContent)).toEqual(rowLabels(0, 250));
      expect(new Set(options.map((o) => o.parentElement)).size).toBe(1);
    });

    it("keeps every row once and in order as the filter crosses chunk boundaries", () => {
      const errors = vi.spyOn(console, "error").mockImplementation(() => {});
      render(
        <Listview
          data={baseData({ items: rows(), enable_search: true })}
          setStateValue={vi.fn()}
        />,
      );
      const search = screen.getByTestId("stListviewSearch");
      for (const [query, expected] of [
        ["Row 1", rowLabels(100, 200)],
        ["", rowLabels(0, 250)],
        ["Row 24", rowLabels(240, 250)],
        ["Row 2", rowLabels(200, 250)],
        ["", rowLabels(0, 250)],
      ] as const) {
        fireEvent.change(search, { target: { value: query } });
        expect(shown()).toEqual(expected);
        const ids = screen.getAllByRole("option").map((o) => o.id);
        expect(new Set(ids).size).toBe(ids.length);
      }
      expect(errors).not.toHaveBeenCalled();
      errors.mockRestore();
    });

    it("keeps each surviving row's DOM node while the filter narrows and clears", () => {
      // A row's chunk is fixed by its place in the UNFILTERED list. Were it
      // derived from the filtered rows, narrowing would move survivors into
      // other chunks, and React would destroy and rebuild every one of them on
      // each keystroke instead of keeping them.
      render(
        <Listview
          data={baseData({ items: rows(), enable_search: true })}
          setStateValue={vi.fn()}
        />,
      );
      const search = screen.getByTestId("stListviewSearch");
      const row150 = () => screen.getByText("Row 150").closest('[role="option"]');
      const node = row150();
      for (const query of ["5", "Row 15", "Row 150", ""]) {
        fireEvent.change(search, { target: { value: query } });
        expect(row150()).toBe(node);
      }
    });

    it("brings every row of a long group back in order when it is expanded", async () => {
      const user = userEvent.setup();
      render(
        <Listview
          data={baseData({ items: rows("G"), collapsible_groups: true })}
          setStateValue={vi.fn()}
        />,
      );
      const header = screen.getByRole("button", { name: /G/ });
      await user.click(header);
      expect(shown()).toEqual([]);
      await user.click(header);
      expect(shown()).toEqual(rowLabels(0, 250));
      const group = screen.getByRole("group");
      for (const option of screen.getAllByRole("option")) {
        expect(option.parentElement).toBe(group);
      }
    });
  });

  it("keeps the collapsible header a real button (it cannot be aria-hidden)", () => {
    render(
      <Listview
        data={baseData({ collapsible_groups: true })}
        setStateValue={vi.fn()}
      />,
    );
    const header = screen.getByRole("button", { name: /Fruit/ });
    expect(header.getAttribute("aria-hidden")).toBeNull();
    // its group still carries the name, so the grouping is conveyed either way
    expect(
      screen.getAllByRole("group").map((g) => g.getAttribute("aria-label")),
    ).toEqual(["Fruit", "Veg"]);
  });
});

// ── Accessible name (WCAG 4.1.2) ─────────────────────────────────────────────

describe("listbox accessible name", () => {
  it("names the listbox from the widget label in every label_visibility", () => {
    // The visible label is deliberately aria-hidden, and the help trigger names
    // only itself (and is absent without help / outside "visible"), so without
    // aria-labelledby a screen reader announced just "list box, 4 items".
    for (const visibility of ["visible", "hidden", "collapsed"] as const) {
      for (const help of [null, "Some help"]) {
        const { unmount } = render(
          <Listview
            data={makeData({ label_visibility: visibility, help })}
            setStateValue={vi.fn()}
          />,
        );
        expect(screen.getByRole("listbox")).toHaveAccessibleName("Pick one");
        unmount();
      }
    }
  });

  it("uses the RENDERED markdown of the label, not its source", () => {
    render(
      <Listview
        data={makeData({ label: "**Pick** a :red[fruit]" })}
        setStateValue={vi.fn()}
      />,
    );
    expect(screen.getByRole("listbox")).toHaveAccessibleName("Pick a fruit");
  });

  it("points at the label's screen-reader copy, which is aria-hidden", () => {
    const { container } = render(
      <Listview data={makeData()} setStateValue={vi.fn()} />,
    );
    const labelledBy = screen
      .getByRole("listbox")
      .getAttribute("aria-labelledby") as string;
    const span = container.querySelector(`#${labelledBy}`) as HTMLElement;
    expect(span.className).toContain("listview-widget-label__a11y-name");
    // aria-hidden, so the name is announced once (as the listbox's), not twice —
    // and the visible copy is aria-hidden too, so neither is loose text.
    expect(span.getAttribute("aria-hidden")).toBe("true");
    expect(
      (container.querySelector(".listview-widget-label__text") as HTMLElement)
        .getAttribute("aria-hidden"),
    ).toBe("true");
  });
});

// ── Scroll containment: the list body only ───────────────────────────────────

describe("keyboard scroll stays inside the list body", () => {
  function setup(
    scrollTop: number,
    row: string,
    top: number,
    { header = 0, data = baseData() } = {},
  ) {
    const { container } = render(<Listview data={data} setStateValue={vi.fn()} />);
    const body = container.querySelector(".listview-body") as HTMLElement;
    stubGeometry(body, rowFor(row), { frame: 100, top, height: 20, scrollTop, header });
    return body;
  }

  it("brings a row above the frame in beneath its sticky group header", () => {
    // Regression: .listview-group-header is position: sticky; top: 0, so it
    // paints over the top of the scrollport. Scrolling a row's top edge to the
    // frame's top edge parked the focused row exactly under that header —
    // ArrowUp / Home focused a row the user could not see. The row must land
    // just below the header instead.
    const body = setup(200, "Apple", 50, { header: 30 });
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Home" });
    expect(body.scrollTop).toBe(20); // 50 - 30
  });

  it("treats a row hidden under the sticky header as out of view", () => {
    // Inside the frame by the numbers (top 110 vs scrollTop 100), but the first
    // 30px of the frame are the stuck header, so the row is covered.
    const body = setup(100, "Apple", 110, { header: 30 });
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Home" });
    expect(body.scrollTop).toBe(80); // 110 - 30
  });

  it("uses the plain frame edge for an ungrouped row (no sticky header)", () => {
    const data = baseData({
      items: [
        { id: "apple", label: "Apple" },
        { id: "banana", label: "Banana" },
        { id: "carrot", label: "Carrot" },
      ],
    });
    const body = setup(200, "Apple", 50, { header: 30, data });
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Home" });
    expect(body.scrollTop).toBe(50);
  });

  it("scrolls THIS instance's row when a sibling instance in the document shares the id", () => {
    // The row lookup goes through the tree scope's id map. In production each
    // instance owns a ShadowRoot, so that is per-instance; in a light-DOM mount
    // (this test tree, or isolate_styles=False) two same-id rows share one
    // document and getElementById answers with the FIRST instance's row. The
    // lookup must notice that hit is outside this body and fall back to this
    // body's own rows, rather than measuring — or skipping — the wrong widget.
    const first = render(<Listview data={baseData()} setStateValue={vi.fn()} />);
    const second = render(<Listview data={baseData()} setStateValue={vi.fn()} />);
    const firstBody = first.container.querySelector(".listview-body") as HTMLElement;
    const secondBody = second.container.querySelector(".listview-body") as HTMLElement;
    const secondRow = within(second.container)
      .getByText("Carrot")
      .closest('[role="option"]') as HTMLElement;
    stubGeometry(secondBody, secondRow, { frame: 100, top: 260, height: 20 });
    fireEvent.keyDown(within(second.container).getByRole("listbox"), { key: "End" });
    expect(secondBody.scrollTop).toBe(180); // 260 + 20 - 100
    expect(firstBody.scrollTop).toBe(0);
  });

  it("brings a row below the frame in by its bottom edge", () => {
    const body = setup(0, "Carrot", 260);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "End" });
    expect(body.scrollTop).toBe(180); // 260 + 20 - 100
  });

  it("brings a row above the frame in by its top edge", () => {
    const body = setup(200, "Apple", 50);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Home" });
    expect(body.scrollTop).toBe(50);
  });

  it("leaves an already-visible row exactly where it is", () => {
    const body = setup(100, "Apple", 110);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Home" });
    expect(body.scrollTop).toBe(100);
  });

  it("never calls scrollIntoView (which would scroll the Streamlit page too)", () => {
    const scrollSpy = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    const body = setup(0, "Carrot", 260);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "End" });
    expect(body.scrollTop).toBe(180);
    expect(scrollSpy).not.toHaveBeenCalled();
    scrollSpy.mockRestore();
  });
});

describe("a click in the frame's empty space", () => {
  // A list shorter than `height` leaves empty space below its last row. That
  // space is .listview-body itself, which is not focusable, so a click there
  // moved focus nowhere and the frame never lit up in the primary color —
  // st.text_area focuses on the very same click. The body forwards it.
  const bodyOf = (container: HTMLElement) =>
    container.querySelector(".listview-body") as HTMLElement;

  it("focuses the listbox", () => {
    const { container } = render(
      <Listview data={makeData()} setStateValue={vi.fn()} />,
    );
    fireEvent.click(bodyOf(container));
    expect(document.activeElement).toBe(screen.getByRole("listbox"));
  });

  it("leaves a click on a child alone, so the search field keeps its caret", () => {
    // The in-flow search box sits INSIDE the body: forwarding every click that
    // bubbles up would pull focus out of the input the user just clicked into.
    render(
      <Listview
        data={makeData({ enable_search: true })}
        setStateValue={vi.fn()}
      />,
    );
    const input = screen.getByRole("searchbox");
    input.focus();
    fireEvent.click(input);
    expect(document.activeElement).toBe(input);
  });

  it("does not focus a disabled widget", () => {
    const { container } = render(
      <Listview data={makeData({ disabled: true })} setStateValue={vi.fn()} />,
    );
    fireEvent.click(bodyOf(container));
    expect(document.activeElement).not.toBe(screen.getByRole("listbox"));
  });
});
