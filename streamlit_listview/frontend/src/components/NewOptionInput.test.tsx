import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NewOptionInput } from "./NewOptionInput";

describe("NewOptionInput", () => {
  it("renders a decorative plus icon in the add-option box", () => {
    render(<NewOptionInput disabled={false} onAdd={vi.fn()} />);
    const icon = screen.getByTestId("stListviewNewOptionIcon");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });

  it("adds the trimmed value and clears on Enter", () => {
    const onAdd = vi.fn(() => null);
    render(<NewOptionInput disabled={false} onAdd={onAdd} />);
    const input = screen.getByTestId("stListviewNewOption") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "  Mango  " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onAdd).toHaveBeenCalledWith("Mango");
    expect(input.value).toBe("");
  });

  it("ignores the Enter that commits an IME candidate, but not a plain Enter", () => {
    const onAdd = vi.fn(() => null);
    render(<NewOptionInput disabled={false} onAdd={onAdd} />);
    const input = screen.getByTestId("stListviewNewOption") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "みかん" } });
    // jsdom cannot run a real IME session, so the composition flag is synthesized
    // here; a browser sets it on the keydown that commits the candidate.
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });
    expect(onAdd).not.toHaveBeenCalled();
    // the in-progress text must survive: submit() would have cleared it
    expect(input.value).toBe("みかん");

    // control: once the composition has ended, Enter adds as usual
    fireEvent.keyDown(input, { key: "Enter", isComposing: false });
    expect(onAdd).toHaveBeenCalledWith("みかん");
    expect(input.value).toBe("");
  });

  it("renders no Add button (Enter is the only way to add)", () => {
    render(<NewOptionInput disabled={false} onAdd={vi.fn()} />);
    expect(screen.queryByTestId("stListviewNewOptionAdd")).toBeNull();
  });

  it("does not add an empty or whitespace-only value", () => {
    const onAdd = vi.fn();
    render(<NewOptionInput disabled={false} onAdd={onAdd} />);
    const input = screen.getByTestId("stListviewNewOption");
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onAdd).not.toHaveBeenCalled();
  });

  it("is disabled when disabled=true", () => {
    render(<NewOptionInput disabled onAdd={vi.fn()} />);
    expect(screen.getByTestId("stListviewNewOption")).toBeDisabled();
  });

  it("keeps an empty status region in the DOM and marks nothing invalid at rest", () => {
    render(<NewOptionInput disabled={false} onAdd={vi.fn(() => null)} />);
    const hint = screen.getByTestId("stListviewNewOptionHint");
    expect(hint).toHaveAttribute("role", "status");
    expect(hint).toBeEmptyDOMElement();
    const input = screen.getByTestId("stListviewNewOption");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).not.toHaveAttribute("aria-describedby");
  });

  it("keeps a refused value and shows the caller's hint, linked to the input", () => {
    const onAdd = vi.fn(() => "Enter a whole number");
    render(<NewOptionInput disabled={false} onAdd={onAdd} />);
    const input = screen.getByTestId("stListviewNewOption") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onAdd).toHaveBeenCalledWith("abc");
    expect(input.value).toBe("abc");
    const hint = screen.getByTestId("stListviewNewOptionHint");
    expect(hint).toHaveTextContent("Enter a whole number");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", hint.id);
  });

  it("clears the hint and the invalid mark as soon as the text changes", () => {
    render(<NewOptionInput disabled={false} onAdd={vi.fn(() => "Nope.")} />);
    const input = screen.getByTestId("stListviewNewOption");
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.change(input, { target: { value: "ab" } });
    expect(screen.getByTestId("stListviewNewOptionHint")).toBeEmptyDOMElement();
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).not.toHaveAttribute("aria-describedby");
  });

  it("replaces the hint's node on a repeated refusal, so a screen reader announces it again", () => {
    // A live region announces a change. Setting the same text again changed
    // nothing in the DOM, so a second Enter on the same refused value stayed
    // silent for a screen-reader user while a sighted user saw the hint.
    render(<NewOptionInput disabled={false} onAdd={vi.fn(() => "Nope.")} />);
    const input = screen.getByTestId("stListviewNewOption");
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.keyDown(input, { key: "Enter" });
    const hint = screen.getByTestId("stListviewNewOptionHint");
    const first = hint.firstChild;
    expect(first).not.toBeNull();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(hint).toHaveTextContent("Nope.");
    expect(hint.firstChild).not.toBe(first);
  });
});
