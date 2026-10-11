import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GroupHeader } from "./GroupHeader";

describe("GroupHeader", () => {
  it("renders the group name as plain text", () => {
    render(<GroupHeader name="Fruits" count={2} />);
    expect(screen.getByText("Fruits")).toBeInTheDocument();
  });

  it("is hidden from the a11y tree and carries no chevron in Milestone A", () => {
    // The enclosing block is a named role="group", so this text would be a
    // duplicate — and non-option content inside a listbox that AT may announce as
    // an item. aria-hidden removes it; role="presentation" (the previous value)
    // dropped only the element's role and left its text in the tree.
    const { container } = render(<GroupHeader name="Fruits" count={2} />);
    const header = container.querySelector(
      '[data-testid="stListviewGroup"]',
    ) as HTMLElement;
    expect(header.getAttribute("aria-hidden")).toBe("true");
    expect(header.getAttribute("role")).toBeNull();
    // no toggle button / chevron yet
    expect(container.querySelector("button")).toBeNull();
    expect(
      container.querySelector('[data-testid="listview-group-chevron"]'),
    ).toBeNull();
  });
});

describe("collapsible mode", () => {
  // With collapsible_groups the list is a tree, and the header's block is the
  // treeitem that carries the name and aria-expanded. The header itself is
  // what the mouse clicks; the keyboard reaches the group through the tree's
  // active descendant, so the header takes no focus and stays out of the
  // accessibility tree, like the static header.
  const header = (container: HTMLElement) =>
    container.querySelector('[data-testid="stListviewGroup"]') as HTMLElement;

  it("renders no button and stays hidden from the accessibility tree", () => {
    const { container } = render(
      <GroupHeader
        name="Fruit"
        count={2}
        collapsible
        collapsed={false}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button")).toBeNull();
    const el = header(container);
    expect(el.getAttribute("aria-hidden")).toBe("true");
    expect(el.getAttribute("role")).toBeNull();
    expect(el.getAttribute("tabindex")).toBeNull();
    expect(el.getAttribute("aria-expanded")).toBeNull();
    expect(el).toHaveClass("listview-group-header--collapsible");
  });

  it("turns the chevron with the collapsed state", () => {
    const chevron = (collapsed: boolean) => {
      const { container, unmount } = render(
        <GroupHeader
          name="Fruit"
          count={2}
          collapsible
          collapsed={collapsed}
          onToggle={vi.fn()}
        />,
      );
      const value = container
        .querySelector(".listview-group-header__chevron")
        ?.getAttribute("data-collapsed");
      unmount();
      return value;
    };
    expect(chevron(false)).toBe("false");
    expect(chevron(true)).toBe("true");
  });

  it("clicking the header calls onToggle", () => {
    const onToggle = vi.fn();
    const { container } = render(
      <GroupHeader
        name="Fruit"
        count={2}
        collapsible
        collapsed={false}
        onToggle={onToggle}
      />,
    );
    fireEvent.click(header(container));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("marks the header the keyboard focus is on", () => {
    const { container, rerender } = render(
      <GroupHeader name="Fruit" count={2} collapsible onToggle={vi.fn()} />,
    );
    expect(header(container)).not.toHaveClass("listview-group-header--focused");
    rerender(
      <GroupHeader
        name="Fruit"
        count={2}
        collapsible
        focused
        onToggle={vi.fn()}
      />,
    );
    expect(header(container)).toHaveClass("listview-group-header--focused");
  });

  it("non-collapsible header renders no button (static, Milestone-A behavior)", () => {
    render(<GroupHeader name="Fruit" count={2} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Fruit")).toBeInTheDocument();
  });
});

describe("item count", () => {
  it("renders the count as a muted (N) after the name in the static variant", () => {
    const { container } = render(<GroupHeader name="Fruits" count={5} />);
    expect(screen.getByText("(5)")).toBeInTheDocument();
    const count = container.querySelector(".listview-group-header__count");
    expect(count).not.toBeNull();
    expect(count).toHaveTextContent("(5)");
    // the count is a separate element from the name
    expect(screen.getByText("Fruits")).not.toHaveTextContent("(5)");
  });

  it("renders the count in the collapsible variant alongside the chevron and name", () => {
    render(
      <GroupHeader
        name="Fruit"
        count={3}
        collapsible
        collapsed={false}
        onToggle={vi.fn()}
      />,
    );
    const el = screen.getByTestId("stListviewGroup");
    expect(el).toHaveTextContent("Fruit(3)");
    expect(el.querySelector(".listview-group-header__chevron")).not.toBeNull();
    expect(el.querySelector(".listview-group-header__count")).not.toBeNull();
  });
});
