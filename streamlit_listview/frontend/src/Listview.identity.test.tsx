import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Listview } from "./Listview";
import { makeData } from "./test/makeData";

// Wrap foldForMatch with a counting pass-through (behaviour untouched). The
// per-label fold pass in useFilter is keyed on the identity of `allItems`, which
// in turn is keyed on the identity of the synthetic-rows array — so "were the
// labels re-folded?" is the observable form of "did an element-wise identical
// rebuild return the SAME array?". Its own file, so the mock cannot leak into
// the main Listview suite.
const { foldCalls } = vi.hoisted(() => ({ foldCalls: vi.fn() }));
vi.mock("./utils/text", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./utils/text")>();
  return {
    ...actual,
    foldForMatch: (value: string) => {
      foldCalls(value);
      return actual.foldForMatch(value);
    },
  };
});

describe("items referential identity across reruns", () => {
  // Every Streamlit rerun hands the renderer freshly parsed JSON: equal content,
  // new objects. The fold pass is keyed on the items array's identity, so it
  // re-running is the observable form of "the rerun invalidated the whole
  // filter/group/scope chain" (and handed every row a new `item` prop).
  const fruit = () => [
    { id: "a", label: "Apple" },
    { id: "b", label: "Banana" },
  ];
  const data = (items: { id: string; label: string }[]) =>
    makeData({ items, enable_search: true });

  it("a rerun with unchanged options does not re-fold the labels", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <Listview data={data(fruit())} setStateValue={vi.fn()} />,
    );
    await user.type(screen.getByTestId("stListviewSearch"), "an");
    expect(foldCalls).toHaveBeenCalledWith("Banana"); // wiring guard
    foldCalls.mockClear();

    rerender(<Listview data={data(fruit())} setStateValue={vi.fn()} />);

    expect(screen.getByText("Banana")).toBeInTheDocument();
    expect(foldCalls).not.toHaveBeenCalledWith("Apple");
    expect(foldCalls).not.toHaveBeenCalledWith("Banana");
  });

  it("a rerun with a changed option re-folds and renders the new label", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <Listview data={data(fruit())} setStateValue={vi.fn()} />,
    );
    await user.type(screen.getByTestId("stListviewSearch"), "an");
    foldCalls.mockClear();

    rerender(
      <Listview
        data={data([
          { id: "a", label: "Apple" },
          { id: "b", label: "Bandana" },
        ])}
        setStateValue={vi.fn()}
      />,
    );

    expect(foldCalls).toHaveBeenCalledWith("Apple");
    expect(screen.getByText("Bandana")).toBeInTheDocument();
    expect(screen.queryByText("Banana")).not.toBeInTheDocument();
  });
});

describe("newOptionItems referential identity", () => {
  it("a click that cannot change the synthetic rows does not invalidate the fold/filter chain", async () => {
    const user = userEvent.setup();
    render(
      <Listview
        data={makeData({
          items: [
            { id: "apple", label: "Apple" },
            { id: "banana", label: "Banana" },
          ],
          accept_new_options: true,
          selection_mode: "multi",
          enable_search: true,
        })}
        setStateValue={vi.fn()}
      />,
    );
    // One synthetic row, so the memo's non-empty path is the one under test
    // (the empty path is already covered by the NO_NEW_OPTIONS constant).
    await user.type(screen.getByTestId("stListviewNewOption"), "Mango");
    await user.keyboard("{Enter}");
    // Activate the filter: the label fold pass runs once over allItems —
    // also the wiring guard proving the counting mock is in place.
    await user.type(screen.getByTestId("stListviewSearch"), "an");
    expect(screen.getByText("Banana")).toBeInTheDocument();
    expect(screen.getByText("Mango")).toBeInTheDocument();
    expect(foldCalls).toHaveBeenCalledWith("Banana");
    foldCalls.mockClear();

    // Selecting a row re-runs the synthetic-rows memo (it depends on the live
    // selection) but rebuilds an element-wise identical list, so the previous
    // array's identity must survive and the per-label fold pass must NOT run
    // again. Only the per-render query fold may.
    await user.click(screen.getByText("Banana"));
    const banana = screen.getByText("Banana").closest('[role="option"]')!;
    expect(banana.getAttribute("aria-selected")).toBe("true");
    expect(foldCalls).not.toHaveBeenCalledWith("Apple");
    expect(foldCalls).not.toHaveBeenCalledWith("Banana");
    expect(foldCalls).not.toHaveBeenCalledWith("Mango");

    // Counter-check: a rebuild that genuinely grows the list must hand back a
    // NEW array and re-run the fold pass ("Papaya" itself stays filtered out by
    // the active query). "Apple" folds twice on this add — once by
    // findExistingId's label scan, once by the re-run fold pass; a wrongly
    // remembered array would leave only the scan's single fold.
    foldCalls.mockClear();
    await user.type(screen.getByTestId("stListviewNewOption"), "Papaya");
    await user.keyboard("{Enter}");
    expect(
      foldCalls.mock.calls.filter(([value]) => value === "Apple"),
    ).toHaveLength(2);
  });
});
