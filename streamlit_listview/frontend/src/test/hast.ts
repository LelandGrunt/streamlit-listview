import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkDirective from "remark-directive";
import { toHast } from "mdast-util-to-hast";
import { visit } from "unist-util-visit";
import type { Root as MdastRoot } from "mdast";
import type { Root as HastRoot, Element } from "hast";

/** The attacher shape every createRemark* factory in streamlitPlugins returns. */
export type ListviewRemarkPlugin = () => (tree: MdastRoot) => MdastRoot;

/**
 * Parse `src` (remark-parse + remark-directive), run the given plugins in
 * order, and return the HAST root. The one scaffold the streamlitPlugins test
 * files share; each passes just the plugin list it exercises.
 */
export function renderHast(
  src: string,
  plugins: ListviewRemarkPlugin[],
): HastRoot {
  const processor = unified().use(remarkParse).use(remarkDirective);
  for (const plugin of plugins) {
    processor.use(plugin);
  }
  // The loop discards use()'s return, so the processor's static type never
  // learns the plugins' tree generics the way a .use() chain would — runSync
  // types as the generic Node; every plugin here maps mdast Root -> Root.
  const mdast = processor.runSync(processor.parse(src)) as MdastRoot;
  return toHast(mdast) as HastRoot;
}

/** First element with the given tagName, or undefined. */
export function findElement(
  tree: HastRoot,
  tagName: string,
): Element | undefined {
  let found: Element | undefined;
  visit(tree, "element", (el: Element) => {
    if (!found && el.tagName === tagName) found = el;
  });
  return found;
}

/** Concatenated text content of a node. */
export function textOf(node: unknown): string {
  let out = "";
  visit(node as HastRoot, "text", (t: { value: string }) => {
    out += t.value;
  });
  return out;
}

/** className of a HAST element as a single space-joined string. */
export function classOf(el: Element | undefined): string {
  const c = el?.properties?.className;
  return Array.isArray(c) ? c.join(" ") : String(c ?? "");
}
