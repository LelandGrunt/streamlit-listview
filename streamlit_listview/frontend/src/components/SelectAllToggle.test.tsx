import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SelectAllToggle } from "./SelectAllToggle";

describe("SelectAllToggle", () => {
  it("renders a button (not a checkbox) whose text and accessible name are the label", () => {
    render(<SelectAllToggle label="Select all" onClick={vi.fn()} disabled={false} />);
    const btn = screen.getByTestId("stListviewSelectAllToggle");
    expect(btn.tagName).toBe("BUTTON");
    expect(btn).toHaveTextContent("Select all");
    expect(screen.getByRole("button", { name: "Select all" })).toBe(btn);
  });

  it("renders the Deselect all label when passed", () => {
    render(<SelectAllToggle label="Deselect all" onClick={vi.fn()} disabled={false} />);
    expect(screen.getByTestId("stListviewSelectAllToggle")).toHaveTextContent(
      "Deselect all",
    );
  });

  it("maps the disabled prop to a disabled button", () => {
    render(<SelectAllToggle label="Select all" onClick={vi.fn()} disabled />);
    expect(screen.getByTestId("stListviewSelectAllToggle")).toBeDisabled();
  });

  it("calls onClick when clicked while enabled", () => {
    const onClick = vi.fn();
    render(<SelectAllToggle label="Select all" onClick={onClick} disabled={false} />);
    fireEvent.click(screen.getByTestId("stListviewSelectAllToggle"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does not call onClick when disabled", () => {
    const onClick = vi.fn();
    render(<SelectAllToggle label="Select all" onClick={onClick} disabled />);
    fireEvent.click(screen.getByTestId("stListviewSelectAllToggle"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
