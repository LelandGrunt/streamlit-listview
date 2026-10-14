import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ListItem } from "./ListItem";
import type { ListviewItem } from "../types";

const base: ListviewItem = { id: "a", label: "Apple" };

describe("ListItem", () => {
  it("renders the label, the option role, and the locked testid", () => {
    render(
      <ListItem
        item={base}
        domId="listview-opt-a"
        posInSet={1}
        setSize={1}
        selected={false}
        disabled={false}
        focused={false}
        muted={false}
        onSelect={vi.fn()}
      />,
    );
    const opt = screen.getByRole("option");
    expect(opt).toHaveTextContent("Apple");
    expect(opt.getAttribute("id")).toBe("listview-opt-a");
    expect(opt.getAttribute("data-testid")).toBe("stListviewOption-a");
    expect(opt.getAttribute("aria-selected")).toBe("false");
  });

  it("renders the label as plain text, not Markdown", () => {
    // Only the widget's label and help render Markdown (README, "Markdown").
    render(
      <ListItem
        item={{ id: "a", label: "**Apple**" }}
        domId="listview-opt-a"
        posInSet={1}
        setSize={1}
        selected={false}
        disabled={false}
        focused={false}
        muted={false}
        onSelect={vi.fn()}
      />,
    );
    const opt = screen.getByRole("option");
    expect(opt).toHaveTextContent("**Apple**");
    expect(opt.querySelector("strong")).toBeNull();
  });

  it("reflects the selected state via aria-selected", () => {
    const { container } = render(
      <ListItem
        item={base}
        domId="listview-opt-a"
        posInSet={1}
        setSize={1}
        selected={true}
        disabled={false}
        focused={false}
        muted={false}
        onSelect={vi.fn()}
      />,
    );
    const opt = screen.getByRole("option");
    expect(opt.getAttribute("aria-selected")).toBe("true");
    // the attribute IS the styling hook — listview.css selects on it directly
    expect(container.querySelector('[aria-selected="true"]')).not.toBeNull();
  });

  it("calls onSelect with the id when clicked", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <ListItem
        item={base}
        domId="listview-opt-a"
        posInSet={1}
        setSize={1}
        selected={false}
        disabled={false}
        focused={false}
        muted={false}
        onSelect={onSelect}
      />,
    );
    await user.click(screen.getByRole("option"));
    expect(onSelect).toHaveBeenCalledWith("a");
  });

  it("does not call onSelect for a disabled item and sets aria-disabled", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    const { container } = render(
      <ListItem
        item={{ id: "a", label: "Apple", disabled: true }}
        domId="listview-opt-a"
        posInSet={1}
        setSize={1}
        selected={false}
        disabled={true}
        focused={false}
        muted={false}
        onSelect={onSelect}
      />,
    );
    const opt = screen.getByRole("option");
    expect(opt.getAttribute("aria-disabled")).toBe("true");
    await user.click(opt);
    expect(onSelect).not.toHaveBeenCalled();
    // the attribute IS the styling hook — listview.css selects on it directly
    expect(container.querySelector('[aria-disabled="true"]')).not.toBeNull();
  });

  it("adds focused and muted classes", () => {
    const { container } = render(
      <ListItem
        item={base}
        domId="listview-opt-a"
        posInSet={1}
        setSize={1}
        selected={false}
        disabled={false}
        focused={true}
        muted={true}
        onSelect={vi.fn()}
      />,
    );
    expect(container.querySelector(".listview-item--focused")).not.toBeNull();
    expect(container.querySelector(".listview-item--muted")).not.toBeNull();
  });

  it("reports its place in the whole list through aria-posinset and aria-setsize", () => {
    render(
      <ListItem
        item={base}
        domId="listview-opt-a"
        posInSet={23456}
        setSize={100000}
        selected={false}
        disabled={false}
        focused={false}
        muted={false}
        onSelect={vi.fn()}
      />,
    );
    const opt = screen.getByRole("option");
    expect(opt.getAttribute("aria-posinset")).toBe("23456");
    expect(opt.getAttribute("aria-setsize")).toBe("100000");
    // a listbox has no levels
    expect(opt.getAttribute("aria-level")).toBeNull();
  });

  it("renders as a treeitem at its level when it is a row of a tree", () => {
    // collapsible_groups makes the list a tree: a row is a selectable treeitem
    // under its group's treeitem.
    render(
      <ListItem
        item={base}
        domId="listview-opt-a"
        posInSet={2}
        setSize={3}
        level={2}
        selected={true}
        disabled={false}
        focused={false}
        muted={false}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.queryByRole("option")).toBeNull();
    const row = screen.getByRole("treeitem");
    expect(row.getAttribute("aria-level")).toBe("2");
    expect(row.getAttribute("aria-selected")).toBe("true");
    expect(row.getAttribute("aria-posinset")).toBe("2");
    expect(row.getAttribute("aria-setsize")).toBe("3");
    expect(row.getAttribute("data-testid")).toBe("stListviewOption-a");
  });
});
