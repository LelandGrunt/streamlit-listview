import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { useRef } from "react";
import { useResetChunkHeights } from "./useResetChunkHeights";
import { FORGET_CLASS } from "../utils/chunks";

/** Animation frames the test advances by hand. */
let frames: FrameRequestCallback[] = [];
function nextFrame(): void {
  const due = frames;
  frames = [];
  for (const callback of due) {
    callback(0);
  }
}

/** Rows the browser renders; every other row sits in a skipped chunk. */
let renderedRows = new Set<string>();

/**
 * A listbox of render chunks, each a list of row labels. `blocks` stands in for
 * Listview's renderBlocks: a new array whenever the chunks may have changed.
 */
function Listbox({
  blocks,
  mounted = true,
}: {
  blocks: string[][];
  mounted?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useResetChunkHeights(ref, blocks);
  return (
    <div ref={mounted ? ref : undefined}>
      {blocks.map((rows, key) => (
        <div key={key} className="listview-chunk" data-testid={`chunk-${key}`}>
          {rows.map((label) => (
            <div key={label} role="option">
              {label}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

const forgetting = (key: number) =>
  screen.getByTestId(`chunk-${key}`).classList.contains(FORGET_CLASS);

beforeEach(() => {
  frames = [];
  renderedRows = new Set();
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  });
  // As in the browser: only `contentVisibilityAuto: true` reports a row in a
  // skipped chunk as invisible; without it every row with a box is visible.
  Element.prototype.checkVisibility = function (
    this: Element,
    options?: CheckVisibilityOptions,
  ): boolean {
    return (
      options?.contentVisibilityAuto !== true ||
      renderedRows.has(this.textContent ?? "")
    );
  };
});

afterEach(() => {
  vi.unstubAllGlobals();
  // @ts-expect-error -- jsdom has no checkVisibility; the tests add their own
  delete Element.prototype.checkVisibility;
});

describe("useResetChunkHeights", () => {
  it("makes a skipped chunk whose rows changed forget its height for two frames", () => {
    const { rerender } = render(
      <Listbox
        blocks={[
          ["Apple", "Banana", "Cherry"],
          ["Date", "Elder"],
        ]}
      />,
    );
    rerender(<Listbox blocks={[["Apple", "Banana", "Cherry"], ["Date"]]} />);
    expect(forgetting(1)).toBe(true);
    nextFrame();
    // still hidden while the browser runs the rendering update that drops
    // the remembered height
    expect(forgetting(1)).toBe(true);
    nextFrame();
    expect(forgetting(1)).toBe(false);
  });

  it("leaves a chunk the browser renders alone, so it never blanks", () => {
    renderedRows = new Set(["Apple"]);
    const { rerender } = render(<Listbox blocks={[["Apple", "Banana"]]} />);
    rerender(<Listbox blocks={[["Apple"]]} />);
    expect(forgetting(0)).toBe(false);
    expect(frames).toHaveLength(0);
  });

  it("leaves a chunk alone whose row count did not change", () => {
    const { rerender } = render(
      <Listbox blocks={[["Apple", "Banana"], ["Cherry"]]} />,
    );
    rerender(
      <Listbox
        blocks={[
          ["Apple", "Banana"],
          ["Cherry", "Date"],
        ]}
      />,
    );
    expect(forgetting(0)).toBe(false);
    expect(forgetting(1)).toBe(true);
  });

  it("leaves a new chunk alone: the browser has no height to remember for it", () => {
    const { rerender } = render(<Listbox blocks={[["Apple"]]} />);
    rerender(<Listbox blocks={[["Apple"], ["Banana", "Cherry"]]} />);
    expect(forgetting(1)).toBe(false);
    expect(frames).toHaveLength(0);
  });

  it("hides nothing in an engine without checkVisibility", () => {
    // @ts-expect-error -- simulate an engine that lacks the method
    delete Element.prototype.checkVisibility;
    const { rerender } = render(<Listbox blocks={[["Apple", "Banana"]]} />);
    rerender(<Listbox blocks={[["Apple"]]} />);
    expect(forgetting(0)).toBe(false);
  });

  it("does nothing while the listbox is not mounted", () => {
    const { rerender } = render(
      <Listbox blocks={[["Apple", "Banana"]]} mounted={false} />,
    );
    rerender(<Listbox blocks={[["Apple"]]} mounted={false} />);
    expect(forgetting(0)).toBe(false);
    expect(frames).toHaveLength(0);
  });
});
