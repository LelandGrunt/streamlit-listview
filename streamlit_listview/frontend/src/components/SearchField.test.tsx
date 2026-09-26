import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useRef, useState } from "react";
import { SearchField } from "./SearchField";

describe("SearchField", () => {
  it("renders an accessible search input with the placeholder and value", () => {
    render(
      <SearchField value="ap" placeholder="Search" disabled={false} onChange={vi.fn()} />,
    );
    const input = screen.getByTestId("stListviewSearch");
    expect(input).toHaveValue("ap");
    expect(input).toHaveAttribute("placeholder", "Search");
    expect(input).toHaveAttribute("aria-label", "Search");
  });

  it("renders a decorative search icon regardless of whether there is a value", () => {
    const { rerender } = render(
      <SearchField value="" placeholder="Search" disabled={false} onChange={vi.fn()} />,
    );
    const emptyIcon = screen.getByTestId("stListviewSearchIcon");
    expect(emptyIcon).toBeInTheDocument();
    // decorative: hidden from the accessibility tree
    expect(emptyIcon).toHaveAttribute("aria-hidden", "true");

    rerender(
      <SearchField value="ap" placeholder="Search" disabled={false} onChange={vi.fn()} />,
    );
    expect(screen.getByTestId("stListviewSearchIcon")).toBeInTheDocument();
  });

  it("calls onChange with the typed value", () => {
    const onChange = vi.fn();
    render(
      <SearchField value="" placeholder="Search" disabled={false} onChange={onChange} />,
    );
    fireEvent.change(screen.getByTestId("stListviewSearch"), { target: { value: "x" } });
    expect(onChange).toHaveBeenCalledWith("x");
  });

  it("shows a clear button only when there is a value; clicking it clears", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <SearchField value="" placeholder="Search" disabled={false} onChange={onChange} />,
    );
    expect(screen.queryByTestId("stListviewSearchClear")).toBeNull();

    rerender(
      <SearchField value="ap" placeholder="Search" disabled={false} onChange={onChange} />,
    );
    fireEvent.click(screen.getByTestId("stListviewSearchClear"));
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("returns focus to the input after clearing (the clear button unmounts)", () => {
    function Wrapper() {
      const [value, setValue] = useState("ap");
      const inputRef = useRef<HTMLInputElement>(null);
      return (
        <SearchField
          value={value}
          placeholder="Search"
          disabled={false}
          onChange={setValue}
          inputRef={inputRef}
        />
      );
    }
    render(<Wrapper />);
    fireEvent.click(screen.getByTestId("stListviewSearchClear"));
    // value cleared -> the clear button is gone, focus is back on the input
    expect(screen.queryByTestId("stListviewSearchClear")).toBeNull();
    expect(document.activeElement).toBe(screen.getByTestId("stListviewSearch"));
  });

  it("Escape in the input calls onEscape", () => {
    const onEscape = vi.fn();
    render(
      <SearchField
        value="ap"
        placeholder="Search"
        disabled={false}
        onChange={vi.fn()}
        onEscape={onEscape}
      />,
    );
    fireEvent.keyDown(screen.getByTestId("stListviewSearch"), { key: "Escape" });
    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it("ignores the Escape that cancels an IME candidate, but not a plain Escape", () => {
    const onEscape = vi.fn();
    render(
      <SearchField
        value="みかん"
        placeholder="Search"
        disabled={false}
        onChange={vi.fn()}
        onEscape={onEscape}
      />,
    );
    const input = screen.getByTestId("stListviewSearch");
    // jsdom cannot run a real IME session, so the composition flag is synthesized
    // here; a browser sets it on the Escape that discards the candidate.
    fireEvent.keyDown(input, { key: "Escape", isComposing: true });
    expect(onEscape).not.toHaveBeenCalled();

    // control: once the composition has ended, Escape clears as usual
    fireEvent.keyDown(input, { key: "Escape", isComposing: false });
    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it("is disabled when disabled=true", () => {
    render(
      <SearchField value="" placeholder="Search" disabled onChange={vi.fn()} />,
    );
    expect(screen.getByTestId("stListviewSearch")).toBeDisabled();
  });
});
