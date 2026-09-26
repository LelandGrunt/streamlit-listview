import { describe, it, expect } from "vitest";
import { createRemarkColoringAndSmall } from "./streamlitPlugins";
import {
  classOf,
  findElement,
  renderHast as renderHastWith,
  textOf,
} from "../test/hast";

/** Parse `src`, run the coloring plugin, and return the HAST root. */
const renderHast = (src: string) =>
  renderHastWith(src, [createRemarkColoringAndSmall()]);

describe("createRemarkColoringAndSmall", () => {
  it(":red[hi] becomes a colored-text span with the listview-md-color modifier", () => {
    const span = findElement(renderHast(":red[hi]"), "span");
    expect(classOf(span)).toBe("listview-md-color listview-md-color--red");
    expect(textOf(span)).toBe("hi");
  });

  it(":blue-background[hi] becomes a colored-background span", () => {
    const span = findElement(renderHast(":blue-background[hi]"), "span");
    expect(classOf(span)).toBe("listview-md-bg listview-md-bg--blue");
    expect(textOf(span)).toBe("hi");
  });

  it("grey is normalized to the gray token (no separate grey class)", () => {
    const span = findElement(renderHast(":grey[hi]"), "span");
    expect(classOf(span)).toBe("listview-md-color listview-md-color--gray");
  });

  it(":blue-badge[x] becomes a badge span", () => {
    const span = findElement(renderHast(":blue-badge[x]"), "span");
    expect(classOf(span)).toBe("listview-md-badge listview-md-badge--blue");
    expect(textOf(span)).toBe("x");
  });

  it(":rainbow-badge[x] is NOT rendered as a badge (rainbow unsupported)", () => {
    const span = findElement(renderHast(":rainbow-badge[x]"), "span");
    expect(span).toBeUndefined();
  });

  it(":small[x] becomes a span with the listview-md-small class", () => {
    const span = findElement(renderHast(":small[x]"), "span");
    expect(classOf(span)).toBe("listview-md-small");
    expect(textOf(span)).toBe("x");
  });

  it(":shimmer[x] becomes a shimmer span", () => {
    const span = findElement(renderHast(":shimmer[x]"), "span");
    expect(classOf(span)).toBe("listview-md-shimmer");
    expect(textOf(span)).toBe("x");
  });

  it("arbitrary CSS color via attributes emits inline style, no modifier class", () => {
    const span = findElement(renderHast(":color[hi]{foreground=#0f0}"), "span");
    expect(classOf(span)).toBe("listview-md-color");
    expect(String(span?.properties?.style)).toContain("color: #0f0");
  });

  it("arbitrary CSS background via attributes emits inline style + bg modifier", () => {
    const span = findElement(renderHast(":color[hi]{background=#000}"), "span");
    expect(classOf(span)).toBe("listview-md-bg");
    expect(String(span?.properties?.style)).toContain("background-color: #000");
  });

  it("foreground + background attributes together emit both styles", () => {
    const span = findElement(
      renderHast(":color[hi]{foreground=#fff background=#000}"),
      "span",
    );
    // background present -> bg modifier wins
    expect(classOf(span)).toBe("listview-md-bg");
    const style = String(span?.properties?.style);
    expect(style).toContain("color: #fff");
    expect(style).toContain("background-color: #000");
  });

  it("leaves an unknown directive name untouched (cleanup handles it)", () => {
    const span = findElement(renderHast(":foo[x]"), "span");
    expect(span).toBeUndefined();
  });

  it("leaves a -background directive with a non-palette prefix untouched", () => {
    const span = findElement(renderHast(":notacolor-background[x]"), "span");
    expect(span).toBeUndefined();
  });

  it("leaves a CHILDLESS palette directive untouched (no text-eating empty span)", () => {
    // "Ampel :red" parses ":red" as a directive with no children. Claiming it
    // would emit an empty span and drop the ":red" the author typed, so the
    // plugin bails and the cleanup renders it literally (see cleanup tests).
    const tree = renderHast("Ampel :red");
    expect(findElement(tree, "span")).toBeUndefined();
  });

  // ── CSS-injection hardening ───────────────────────────────────────────────
  // Quoted directive attribute values may contain ';', ':', spaces and
  // url(...); a multi-declaration payload must NOT reach the inline style (it
  // would enable clickjacking overlays / resource-load beacons). Only a single
  // well-formed CSS <color> token is allowed through.

  it("drops a foreground value carrying extra CSS declarations (no injection)", () => {
    const span = findElement(
      renderHast(
        ':color[x]{foreground="red; position: fixed; inset: 0; z-index: 9999"}',
      ),
      "span",
    );
    const style = String(span?.properties?.style ?? "");
    expect(style).not.toContain("position");
    expect(style).not.toContain("fixed");
    expect(style).not.toContain("z-index");
  });

  it("drops a url(...) background payload (no resource-load beacon)", () => {
    const span = findElement(
      renderHast(':color[x]{background="url(https://evil.example/leak)"}'),
      "span",
    );
    const style = String(span?.properties?.style ?? "");
    expect(style).not.toContain("url(");
  });

  it("keeps a valid foreground when the background is an injection payload", () => {
    const span = findElement(
      renderHast(':color[x]{foreground=#fff background="red; position: fixed"}'),
      "span",
    );
    // Invalid background dropped -> no bg modifier; valid foreground preserved.
    expect(classOf(span)).toBe("listview-md-color");
    const style = String(span?.properties?.style);
    expect(style).toContain("color: #fff");
    expect(style).not.toContain("position");
  });

  it("still accepts a CSS named color", () => {
    const span = findElement(renderHast(":color[hi]{foreground=red}"), "span");
    expect(classOf(span)).toBe("listview-md-color");
    expect(String(span?.properties?.style)).toContain("color: red");
  });

  it("still accepts an rgba() functional color", () => {
    const span = findElement(
      renderHast(':color[hi]{background="rgba(0, 0, 0, 0.5)"}'),
      "span",
    );
    expect(classOf(span)).toBe("listview-md-bg");
    expect(String(span?.properties?.style)).toContain(
      "background-color: rgba(0, 0, 0, 0.5)",
    );
  });
});
