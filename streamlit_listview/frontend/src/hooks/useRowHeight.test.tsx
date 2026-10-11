import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { useRef } from "react";
import { ROW_HEIGHT_PROPERTY, useRowHeight } from "./useRowHeight";
import { FORGET_CLASS } from "../utils/chunks";

/** jsdom has no ResizeObserver: a stand-in that records what it observes. */
class FakeResizeObserver {
  static instances: FakeResizeObserver[] = [];
  readonly observed: Element[] = [];
  disconnected = false;
  private readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
    FakeResizeObserver.instances.push(this);
  }

  observe(target: Element): void {
    this.observed.push(target);
  }

  disconnect(): void {
    this.disconnected = true;
  }

  /** Deliver a notification, as the browser does after a size change. */
  notify(): void {
    this.callback([], this as unknown as ResizeObserver);
  }
}

/** Animation frames the test advances by hand. */
let frames: FrameRequestCallback[] = [];
function nextFrame(): void {
  const due = frames;
  frames = [];
  for (const callback of due) {
    callback(0);
  }
}

/** The height every row reports; tests change it between steps. */
let rowHeight = 35.5;
/** The height each render chunk reports, by test id (the chunk's own box). */
let chunkHeights = new Map<string, number>();
/** Rows the browser renders; every other row sits in a skipped chunk. */
let renderedRows = new Set<string>();

/** What useRowHeight returned on each render of Listbox, oldest first. */
let remeasures: Array<() => void> = [];
const remeasure = () => remeasures[remeasures.length - 1]!();

function Listbox({
  rows,
  mounted = true,
}: {
  rows: string[];
  mounted?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  remeasures.push(useRowHeight(ref));
  return (
    <div ref={mounted ? ref : undefined} data-testid="listbox">
      {rows.map((label) => (
        <div key={label} className="listview-item">
          {label}
        </div>
      ))}
    </div>
  );
}

/** A listbox of render chunks, each a list of row labels. */
function Chunked({ chunks }: { chunks: string[][] }) {
  const ref = useRef<HTMLDivElement>(null);
  remeasures.push(useRowHeight(ref));
  return (
    <div ref={ref} data-testid="listbox">
      {chunks.map((rows, key) => (
        <div key={key} className="listview-chunk" data-testid={`chunk-${key}`}>
          {rows.map((label) => (
            <div key={label} className="listview-item">
              {label}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

const listbox = () => screen.getByTestId("listbox");
const forgetting = (key: number) =>
  screen.getByTestId(`chunk-${key}`).classList.contains(FORGET_CLASS);
const published = () => listbox().style.getPropertyValue(ROW_HEIGHT_PROPERTY);

beforeEach(() => {
  rowHeight = 35.5;
  remeasures = [];
  frames = [];
  FakeResizeObserver.instances = [];
  chunkHeights = new Map();
  renderedRows = new Set();
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(
    function (this: Element) {
      const height = this.classList.contains("listview-chunk")
        ? (chunkHeights.get(this.getAttribute("data-testid") as string) ?? 0)
        : rowHeight;
      return { height } as DOMRect;
    },
  );
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
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  // @ts-expect-error -- jsdom has no checkVisibility; the tests add their own
  delete Element.prototype.checkVisibility;
});

describe("useRowHeight", () => {
  it("publishes the first row's height on the listbox at the commit", () => {
    vi.stubGlobal("ResizeObserver", undefined);
    render(<Listbox rows={["Apple", "Banana"]} />);
    expect(published()).toBe("35.5px");
  });

  it("observes the listbox, which the browser never skips", () => {
    // A ResizeObserver on the first row reports nothing while the row's render
    // chunk is skipped (content-visibility: auto), so a rerun that changed
    // item_height while the list was scrolled away from its top left the
    // estimate stale. The listbox is as tall as its rendered chunks, so it
    // resizes whenever the rows do.
    render(<Listbox rows={["Apple", "Banana"]} />);
    expect(FakeResizeObserver.instances).toHaveLength(1);
    expect(FakeResizeObserver.instances[0]!.observed).toEqual([listbox()]);
  });

  it("measures the first row again a frame after the listbox resizes", () => {
    render(<Listbox rows={["Apple", "Banana"]} />);
    const [observer] = FakeResizeObserver.instances;
    rowHeight = 48;
    observer!.notify();
    // Not in the callback: a write there resizes the listbox again within the
    // same rendering update, which ends the browser's delivery loop with an
    // undelivered notification and a window error event.
    expect(published()).toBe("35.5px");
    nextFrame();
    expect(published()).toBe("48px");
  });

  it("ignores a row that reports no height", () => {
    rowHeight = 0;
    render(<Listbox rows={["Apple"]} />);
    expect(published()).toBe("");
  });

  it("does not rewrite an unchanged height", () => {
    // A width-only resize notifies too; rewriting the same value would
    // invalidate the style of every chunk for nothing.
    render(<Listbox rows={["Apple"]} />);
    const setProperty = vi.spyOn(listbox().style, "setProperty");
    FakeResizeObserver.instances[0]!.notify();
    nextFrame();
    expect(setProperty).not.toHaveBeenCalled();
  });

  it("measures a new first row at the commit and keeps its one observer", () => {
    const { rerender } = render(<Listbox rows={["Apple", "Banana"]} />);
    rowHeight = 56;
    rerender(<Listbox rows={["Banana"]} />);
    expect(published()).toBe("56px");
    expect(FakeResizeObserver.instances).toHaveLength(1);
    expect(FakeResizeObserver.instances[0]!.disconnected).toBe(false);
  });

  it("leaves a commit that keeps its first row to the observer", () => {
    // Measuring at every commit would force a layout on every keystroke and
    // click; the listbox's resize reports a changed height a frame later.
    const { rerender } = render(<Listbox rows={["Apple"]} />);
    rowHeight = 48;
    rerender(<Listbox rows={["Apple", "Banana", "Cherry"]} />);
    expect(published()).toBe("35.5px");
    FakeResizeObserver.instances[0]!.notify();
    nextFrame();
    expect(published()).toBe("48px");
  });

  it("disconnects when the list unmounts", () => {
    const { unmount } = render(<Listbox rows={["Apple"]} />);
    unmount();
    expect(FakeResizeObserver.instances[0]!.disconnected).toBe(true);
  });

  it("writes nothing for a measurement due after the list unmounts", () => {
    const { unmount } = render(<Listbox rows={["Apple"]} />);
    const host = listbox();
    rowHeight = 48;
    FakeResizeObserver.instances[0]!.notify();
    unmount();
    nextFrame();
    expect(host.style.getPropertyValue(ROW_HEIGHT_PROPERTY)).toBe("35.5px");
  });

  it("measures the first row when one arrives", () => {
    const { rerender } = render(<Listbox rows={[]} />);
    expect(published()).toBe("");
    rerender(<Listbox rows={["Apple"]} />);
    expect(published()).toBe("35.5px");
  });

  it("does nothing while the listbox is not mounted", () => {
    render(<Listbox rows={["Apple"]} mounted={false} />);
    expect(FakeResizeObserver.instances).toHaveLength(0);
    expect(published()).toBe("");
  });

  it("measures the first row again on request", () => {
    // scrollToId asks for a measurement right before it measures a row: after
    // a key-change remount the stylesheet applies while every chunk is
    // skipped, and the listbox's resize is reported a frame later than the
    // jump measures.
    render(<Listbox rows={["Apple", "Banana"]} />);
    rowHeight = 48;
    remeasure();
    expect(published()).toBe("48px");
  });

  it("returns the same function on every render", () => {
    // scrollToId depends on it, and a new function would give the jump to a
    // default and every keyboard move a new callback on each commit.
    const { rerender } = render(<Listbox rows={["Apple"]} />);
    rerender(<Listbox rows={["Banana"]} />);
    expect(remeasures[0]).toBeTypeOf("function");
    expect(new Set(remeasures).size).toBe(1);
  });

  it("measures nothing on request before a first row exists", () => {
    render(<Listbox rows={[]} />);
    remeasure();
    expect(published()).toBe("");
  });

  it("makes a skipped chunk that kept another height forget it, a frame after a changed write", () => {
    // Chromium keeps the height a skipped chunk had when it last rendered
    // (contain-intrinsic-size: auto). After a rerun that changed item_height,
    // a chunk the user had scrolled past stayed 3,539 px tall among chunks of
    // 5,000 px, and a forced layout of its rows changed nothing (2026-10-08).
    // Only the chunks at another height than their rows hide: hiding a chunk
    // the viewport lands on blanks it for a frame.
    renderedRows = new Set(["Elder"]);
    chunkHeights = new Map([
      ["chunk-0", 71],
      ["chunk-1", 71],
      ["chunk-2", 71],
    ]);
    render(
      <Chunked
        chunks={[
          ["Apple", "Banana"],
          ["Cherry", "Date"],
          ["Elder", "Fig"],
        ]}
      />,
    );
    nextFrame();
    expect([forgetting(0), forgetting(1), forgetting(2)]).toEqual([
      false,
      false,
      false,
    ]);
    // The rows are 50 px now. The write lays out at the next rendering
    // update, after which chunk 0 still shows its remembered 71 px, chunk 1
    // the estimate, and the rendered chunk 2 its rows.
    rowHeight = 50;
    chunkHeights = new Map([
      ["chunk-0", 71],
      ["chunk-1", 100],
      ["chunk-2", 100],
    ]);
    remeasure();
    expect(published()).toBe("50px");
    expect(forgetting(0)).toBe(false);
    nextFrame();
    expect([forgetting(0), forgetting(1), forgetting(2)]).toEqual([
      true,
      false,
      false,
    ]);
    nextFrame();
    nextFrame();
    expect(forgetting(0)).toBe(false);
  });

  it("forgets nothing after an unchanged measurement", () => {
    chunkHeights = new Map([["chunk-0", 71]]);
    render(<Chunked chunks={[["Apple", "Banana"]]} />);
    nextFrame();
    chunkHeights = new Map([["chunk-0", 12]]);
    remeasure();
    expect(frames).toHaveLength(0);
    expect(forgetting(0)).toBe(false);
  });

  it("forgets nothing once the list has unmounted", () => {
    chunkHeights = new Map([["chunk-0", 71]]);
    const { unmount } = render(<Chunked chunks={[["Apple", "Banana"]]} />);
    nextFrame();
    const chunk = screen.getByTestId("chunk-0");
    rowHeight = 50;
    remeasure();
    unmount();
    nextFrame();
    expect(chunk.classList.contains(FORGET_CLASS)).toBe(false);
  });

  it("measures each new first row without a ResizeObserver", () => {
    vi.stubGlobal("ResizeObserver", undefined);
    const { rerender } = render(<Listbox rows={["Apple", "Banana"]} />);
    rowHeight = 56;
    rerender(<Listbox rows={["Banana"]} />);
    expect(published()).toBe("56px");
  });
});
