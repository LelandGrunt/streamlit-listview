import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { useRef } from "react";
import { ROW_HEIGHT_PROPERTY, useRowHeight } from "./useRowHeight";

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

/** The height every element reports; tests change it between steps. */
let rowHeight = 35.5;

/** What useRowHeight returned on each render of Listbox, oldest first. */
let remeasures: Array<() => void> = [];
const remeasure = () => remeasures[remeasures.length - 1]();

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
        <div key={label} role="option">
          {label}
        </div>
      ))}
    </div>
  );
}

const listbox = () => screen.getByTestId("listbox");
const published = () => listbox().style.getPropertyValue(ROW_HEIGHT_PROPERTY);

beforeEach(() => {
  rowHeight = 35.5;
  remeasures = [];
  FakeResizeObserver.instances = [];
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(
    () => ({ height: rowHeight }) as DOMRect,
  );
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("useRowHeight", () => {
  it("publishes the first row's height on the listbox at the commit", () => {
    vi.stubGlobal("ResizeObserver", undefined);
    render(<Listbox rows={["Apple", "Banana"]} />);
    expect(published()).toBe("35.5px");
  });

  it("observes the first row and republishes a changed height", () => {
    render(<Listbox rows={["Apple", "Banana"]} />);
    const [observer] = FakeResizeObserver.instances;
    expect(observer.observed).toEqual([screen.getByText("Apple")]);
    rowHeight = 48;
    observer.notify();
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
    FakeResizeObserver.instances[0].notify();
    expect(setProperty).not.toHaveBeenCalled();
  });

  it("follows a new first row and stops observing the old one", () => {
    const { rerender } = render(<Listbox rows={["Apple", "Banana"]} />);
    rowHeight = 56;
    rerender(<Listbox rows={["Banana"]} />);
    const [old, current] = FakeResizeObserver.instances;
    expect(old.disconnected).toBe(true);
    expect(current.observed).toEqual([screen.getByText("Banana")]);
    expect(published()).toBe("56px");
  });

  it("keeps its one observer while the first row stays", () => {
    const { rerender } = render(<Listbox rows={["Apple"]} />);
    rerender(<Listbox rows={["Apple", "Banana", "Cherry"]} />);
    expect(FakeResizeObserver.instances).toHaveLength(1);
    expect(FakeResizeObserver.instances[0].disconnected).toBe(false);
  });

  it("disconnects when the list unmounts", () => {
    const { unmount } = render(<Listbox rows={["Apple"]} />);
    unmount();
    expect(FakeResizeObserver.instances[0].disconnected).toBe(true);
  });

  it("waits for a first row, and lets go when the last one leaves", () => {
    const { rerender } = render(<Listbox rows={[]} />);
    expect(FakeResizeObserver.instances).toHaveLength(0);
    expect(published()).toBe("");
    rerender(<Listbox rows={["Apple"]} />);
    expect(FakeResizeObserver.instances).toHaveLength(1);
    expect(published()).toBe("35.5px");
    rerender(<Listbox rows={[]} />);
    expect(FakeResizeObserver.instances[0].disconnected).toBe(true);
  });

  it("does nothing while the listbox is not mounted", () => {
    render(<Listbox rows={["Apple"]} mounted={false} />);
    expect(FakeResizeObserver.instances).toHaveLength(0);
    expect(published()).toBe("");
  });

  it("measures the first row again on request", () => {
    // A ResizeObserver reports nothing for a row inside a render chunk the
    // browser skips, so a stylesheet that applies while the first chunk is
    // skipped goes unseen. scrollToId asks for a measurement instead.
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

  it("measures each new first row without a ResizeObserver", () => {
    vi.stubGlobal("ResizeObserver", undefined);
    const { rerender } = render(<Listbox rows={["Apple", "Banana"]} />);
    rowHeight = 56;
    rerender(<Listbox rows={["Banana"]} />);
    expect(published()).toBe("56px");
  });
});
