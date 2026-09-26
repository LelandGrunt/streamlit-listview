import { describe, it, expect } from "vitest";
import {
  LABEL_DISALLOWED_ELEMENTS,
  escapeLabelSource,
} from "./streamlitPlugins";

describe("LABEL_DISALLOWED_ELEMENTS", () => {
  it("blocks block-level + table + input elements", () => {
    for (const tag of [
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
      "h1",
      "h6",
      "ul",
      "ol",
      "li",
      "input",
      "hr",
      "blockquote",
      "pre",
      // defense in depth for the inline-only tier: mdast-util-to-hast renders an
      // mdast node it does not recognise as a block <div>
      "div",
    ]) {
      expect(LABEL_DISALLOWED_ELEMENTS).toContain(tag);
    }
  });
  it("does NOT block inline elements", () => {
    // `code` (inline code) stays allowed even though `pre` (code block) is not.
    for (const tag of ["a", "em", "strong", "code", "span", "img", "del"]) {
      expect(LABEL_DISALLOWED_ELEMENTS).not.toContain(tag);
    }
  });
});

describe("escapeLabelSource", () => {
  it("escapes a leading heading marker", () => {
    expect(escapeLabelSource("# Title")).toBe("\\# Title");
  });
  it("escapes a leading blockquote marker", () => {
    expect(escapeLabelSource("> quote")).toBe("\\> quote");
  });
  it.each(["+", "-", "*"])("escapes the leading list marker %j", (m) => {
    expect(escapeLabelSource(`${m} item`)).toBe(`\\${m} item`);
  });
  it("escapes an ordered-list marker", () => {
    expect(escapeLabelSource("1. item")).toBe("1\\. item");
    expect(escapeLabelSource("2) item")).toBe("2\\) item");
  });
  it("leaves inline markdown (bold/links) untouched", () => {
    expect(escapeLabelSource("**bold** and [x](y)")).toBe(
      "**bold** and [x](y)",
    );
  });
});
