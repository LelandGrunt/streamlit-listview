import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FORGET_CLASS, forgetHeights, isSkipped } from "./chunks";

/** Animation frames the test advances by hand. */
let frames: FrameRequestCallback[] = [];
function nextFrame(): void {
  const due = frames;
  frames = [];
  for (const callback of due) {
    callback(0);
  }
}

function chunk(rows: number): HTMLElement {
  const element = document.createElement("div");
  element.className = "listview-chunk";
  for (let i = 0; i < rows; i++) {
    const row = document.createElement("div");
    row.setAttribute("role", "option");
    element.appendChild(row);
  }
  return element;
}

beforeEach(() => {
  frames = [];
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  // @ts-expect-error -- jsdom has no checkVisibility; the tests add their own
  delete Element.prototype.checkVisibility;
});

describe("isSkipped", () => {
  it("is true for a chunk whose first row the browser does not render", () => {
    // As in the browser: only `contentVisibilityAuto: true` reports a row in
    // a skipped chunk as invisible.
    Element.prototype.checkVisibility = (options?: CheckVisibilityOptions) =>
      options?.contentVisibilityAuto !== true;
    expect(isSkipped(chunk(1))).toBe(true);
  });

  it("is false for a chunk the browser renders", () => {
    Element.prototype.checkVisibility = () => true;
    expect(isSkipped(chunk(1))).toBe(false);
  });

  it("is false in an engine without checkVisibility", () => {
    expect(isSkipped(chunk(1))).toBe(false);
  });
});

describe("forgetHeights", () => {
  it("hides the chunks for two animation frames", () => {
    const chunks = [chunk(1), chunk(2)];
    forgetHeights(chunks);
    expect(chunks.map((c) => c.classList.contains(FORGET_CLASS))).toEqual([
      true,
      true,
    ]);
    nextFrame();
    // still hidden while the browser runs the rendering update that drops
    // the remembered height
    expect(chunks[0]!.classList.contains(FORGET_CLASS)).toBe(true);
    nextFrame();
    expect(chunks.map((c) => c.classList.contains(FORGET_CLASS))).toEqual([
      false,
      false,
    ]);
  });

  it("queues no frame for no chunks", () => {
    forgetHeights([]);
    expect(frames).toHaveLength(0);
  });
});
