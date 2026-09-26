import { describe, it, expect } from "vitest";
import {
  createRemarkColoringAndSmall,
  createRemarkUnsupportedDirectivesCleanup,
} from "./streamlitPlugins";
import {
  classOf,
  findElement,
  renderHast as renderHastWith,
  textOf,
} from "../test/hast";

const renderHast = (src: string) =>
  renderHastWith(src, [
    createRemarkColoringAndSmall(),
    createRemarkUnsupportedDirectivesCleanup(),
  ]);

describe("createRemarkUnsupportedDirectivesCleanup", () => {
  it("renders an unknown :foo[x] as literal text, not a span", () => {
    const tree = renderHast(":foo[x]");
    expect(textOf(tree)).toContain(":foo");
    expect(findElement(tree, "span")).toBeUndefined();
  });

  it("preserves the bracketed content of an unsupported directive", () => {
    // :rainbow is intentionally unsupported and must render verbatim, INCLUDING
    // its label text — dropping "Hello" would lose visible content.
    const tree = renderHast(":rainbow[Hello]");
    expect(textOf(tree)).toContain(":rainbow");
    expect(textOf(tree)).toContain("Hello");
    expect(findElement(tree, "span")).toBeUndefined();
  });

  it("renders a bare unsupported directive (no brackets) without adding []", () => {
    const tree = renderHast(":foo");
    expect(textOf(tree)).toContain(":foo");
    expect(textOf(tree)).not.toContain("[");
  });

  it("does NOT clobber a recognized directive handled earlier", () => {
    const tree = renderHast(":red[hi]");
    const span = findElement(tree, "span");
    expect(classOf(span)).toBe("listview-md-color listview-md-color--red");
    expect(textOf(span)).toBe("hi");
  });

  // ── leaf / container directives ───────────────────────────────────────────
  // Left unclaimed, these reach mdast-util-to-hast's unknown-node fallback,
  // which emits a block <div> — invalid inside the inline-only label <span>
  // (LABEL_DISALLOWED_ELEMENTS) and silently swallowing the typed markers.

  it("renders a leaf directive ::name[x] verbatim, never a <div>", () => {
    const tree = renderHast("::badge[Hello]");
    expect(textOf(tree)).toBe("::badge[Hello]");
    expect(findElement(tree, "div")).toBeUndefined();
    // block node -> the literal text is wrapped in a paragraph
    expect(findElement(tree, "p")).toBeDefined();
  });

  it("renders a childless leaf directive without adding []", () => {
    const tree = renderHast("::foo");
    expect(textOf(tree)).toBe("::foo");
    expect(findElement(tree, "div")).toBeUndefined();
  });

  it("renders a container directive's marker and lifts its block body", () => {
    const tree = renderHast(":::note\ncontent\n:::");
    // The opening `:::note` marker survives as its own paragraph; the body is
    // lifted after it. The closing fence is deliberately not reconstructed.
    expect(textOf(tree)).toContain(":::note");
    expect(textOf(tree)).toContain("content");
    expect(findElement(tree, "div")).toBeUndefined();
  });

  it("renders an empty container directive as just its marker", () => {
    const tree = renderHast(":::note\n:::");
    expect(textOf(tree)).toBe(":::note");
    expect(findElement(tree, "div")).toBeUndefined();
  });

  it("cleans up an unsupported directive nested inside another one", () => {
    // The visitor resumes AT the replacement, so the inner :bar[…] lifted out of
    // the leaf directive is still visited (otherwise it would leak a <div>).
    const tree = renderHast("::foo[:bar[x]]");
    expect(textOf(tree)).toBe("::foo[:bar[x]]");
    expect(findElement(tree, "div")).toBeUndefined();
    expect(findElement(tree, "span")).toBeUndefined();
  });
});

describe("childless palette/format directives render literally", () => {
  // A directive with no children is prose, not a formatting request: claiming it
  // would emit an empty span and DELETE the text. Deliberate divergence from
  // upstream Streamlit — see the comment in createRemarkColoringAndSmall.
  it.each([
    ["Ampel :red", "Ampel :red"],
    ["key:blue value", "key:blue value"],
    [":red[unterminated", ":red[unterminated"],
    [":small", ":small"],
    [":shimmer", ":shimmer"],
    [":red-badge", ":red-badge"],
    [":blue-background", ":blue-background"],
    [":color{foreground=red}", ":color"],
  ])("renders %j as %j with no span", (src, expected) => {
    const tree = renderHast(src);
    expect(textOf(tree)).toBe(expected);
    expect(findElement(tree, "span")).toBeUndefined();
  });
});
