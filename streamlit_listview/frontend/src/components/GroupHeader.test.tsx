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
  it("renders a toggle button with aria-expanded reflecting open state", () => {
    render(<GroupHeader name="Fruit" count={2} collapsible collapsed={false} onToggle={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /Fruit/ });
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });

  it("aria-expanded is false when collapsed", () => {
    render(<GroupHeader name="Fruit" count={2} collapsible collapsed onToggle={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Fruit/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("clicking the header calls onToggle", () => {
    const onToggle = vi.fn();
    render(<GroupHeader name="Fruit" count={2} collapsible collapsed={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole("button", { name: /Fruit/ }));
    expect(onToggle).toHaveBeenCalledTimes(1);
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
    render(<GroupHeader name="Fruit" count={3} collapsible collapsed={false} onToggle={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /Fruit/ });
    expect(btn).toHaveTextContent("(3)");
    expect(btn.querySelector(".listview-group-header__count")).not.toBeNull();
  });
});
