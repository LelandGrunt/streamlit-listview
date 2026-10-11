import type { GroupKey } from "../hooks/useCollapse";
import type { ListviewItem } from "../types";
import { elementAt } from "./arrays";

/**
 * A block of rows the list renders together: a named group, or (`name: null`)
 * the one block for every row without a group.
 */
export interface RenderGroup {
  name: string | null;
  items: ListviewItem[];
}

/**
 * The block a row with `group` renders in: its group, or `null` for the block
 * without a group. A group named like `ungrouped_label` belongs to that block
 * too: it would otherwise render a second header with the same text, and two
 * headers the user cannot tell apart are no better than none.
 *
 * The Python side applies the same rule: `_options.sort_items` sorts the two
 * as one block. Change both copies together.
 */
export function blockKeyOf(
  group: string | null | undefined,
  ungroupedLabel: string,
): GroupKey {
  return group == null || group === ungroupedLabel ? null : group;
}

/**
 * The render blocks for `items`, in render order: one block per named group,
 * in the order the groups first appear, then ONE block for every row without a
 * group — the caller's ungrouped options and those of the group named like
 * `ungrouped_label`, then the accept_new_options rows, in the order `items`
 * lists them.
 *
 * The block without a group renders last wherever its rows stand in `items`.
 * Rendered at its first row's place, it read as part of the group above it, so
 * a row that belongs to no group looked like a member of that group; in a
 * grouped list it now also carries a header of its own (`ungrouped_label`).
 * Last is also where the README puts added entries: "appended at the bottom".
 *
 * ONE function serves the rendered (filtered) rows and the positions
 * (aria-posinset), which count the unfiltered rows: two copies of the block
 * order could disagree, and a row would announce a place it is not shown at.
 */
export function blocksFor(
  items: ListviewItem[],
  ungroupedLabel: string,
): RenderGroup[] {
  const blocks: RenderGroup[] = [];
  const indexByName = new Map<string, number>();
  const ungrouped: ListviewItem[] = [];
  for (const item of items) {
    const key = blockKeyOf(item.group, ungroupedLabel);
    if (key === null) {
      ungrouped.push(item);
      continue;
    }
    let idx = indexByName.get(key);
    if (idx === undefined) {
      idx = blocks.length;
      indexByName.set(key, idx);
      blocks.push({ name: key, items: [] });
    }
    elementAt(blocks, idx).items.push(item);
  }
  // A filter that leaves no row without a group adds no empty block.
  if (ungrouped.length > 0) {
    blocks.push({ name: null, items: ungrouped });
  }
  return blocks;
}
