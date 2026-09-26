import { describe, it, expect } from "vitest";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkStringify from "remark-stringify";
import remarkDirective from "remark-directive";
import { createRemarkTypographicalSymbols } from "./streamlitPlugins";

/** Run the plugin over `src` and return the transformed Markdown text. */
function runRemark(
  src: string,
  plugin: ReturnType<typeof createRemarkTypographicalSymbols>,
): string {
  return unified()
    .use(remarkParse)
    .use(remarkStringify)
    .use(remarkDirective)
    .use(plugin)
    .processSync(src)
    .toString();
}

describe("createRemarkTypographicalSymbols", () => {
  const plugin = createRemarkTypographicalSymbols();

  it.each([
    ["a -> b", "→"],
    ["a <- b", "←"],
    ["a <-> b", "↔"],
    ["a -- b", "—"],
    ["a >= b", "≥"],
    ["a <= b", "≤"],
    ["a ~= b", "≈"],
  ])("replaces %j with a typographical symbol", (input, symbol) => {
    expect(runRemark(input, plugin)).toContain(symbol);
  });

  it("converts two adjacent occurrences that share a single separating space", () => {
    // The shared space must serve as the trailing boundary of the first match
    // AND the leading boundary of the second; a consumed space would leave the
    // second pair unconverted.
    const out = runRemark("a -- -- b", plugin);
    expect((out.match(/—/g) || []).length).toBe(2);
  });

  it("does not replace inside a link target", () => {
    const out = runRemark("[x](http://a-->b)", plugin);
    expect(out).toContain("a-->b");
    expect(out).not.toContain("→");
  });

  it("leaves text without arrows untouched", () => {
    expect(runRemark("plain text", plugin).trim()).toBe("plain text");
  });
});
