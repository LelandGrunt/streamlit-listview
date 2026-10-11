import { useMemo } from "react";
import type { ListviewItem } from "../types";
import { blocksFor } from "../utils/blocks";
import type { RenderGroup } from "../utils/blocks";
import { runsByKey } from "../utils/items";
import type { GroupKey, UseCollapseResult } from "./useCollapse";
import { GroupNode } from "./useKeyboardNav";
import type { NavNode } from "./useKeyboardNav";

// A block renders its rows in keyed "render chunks" of ROW_CHUNK_SIZE rows,
// each a `div.listview-chunk` (GroupBlock), not as one flat run. Two costs set
// that shape.
//
// React: when an update brings many new rows into ONE parent at once —
// clearing or backspacing the search, expanding a big group, options growing
// on a rerun — React places each new row on its own and, for each, searches
// forward through the following siblings for a settled DOM node to insert
// before (`getHostSibling`). Across thousands of new siblings that search is
// O(k²): clearing the search over 50k ungrouped rows took ~7 s (~40 s on a
// 4×-slowed CPU), against ~0.85 s for the same rows grouped 100 to a block.
//
// The browser: listview.css gives each chunk `content-visibility: auto`, so a
// chunk outside the scrollport skips style, layout and paint, sized by an
// estimate (its row count, `--listview-chunk-rows`, times the measured row
// height, see useRowHeight). In the 2026-10-07 spike at 100k rows a click
// settled in 0.40 s instead of 1.27 s and scrolling ran at 60 Hz: Chrome's
// lifecycle over the whole DOM, not script, was the cost. Every row stays in
// the DOM, but the accessibility tree holds only the rendered chunks, which is
// why each row reports aria-posinset / aria-setsize.
//
// A row's chunk is fixed by its place in the UNFILTERED list (`chunkOf` below),
// never by the filtered rows: a filter then cannot move a row into another
// chunk, so narrowing keeps every surviving row's DOM node, and the rows a
// broadening filter brings back land either in a chunk that still holds a
// settled survivor — which ends each sibling search within that chunk — or in a
// wholly new chunk, inserted with one search for all of its rows. (Keying a
// chunk by its first FILTERED row instead remounted the survivors on every
// scattered narrowing keystroke: 2–3× slower at 50k.) A chunk carries
// role="none", so assistive technology sees its rows as children of the
// block's group (or of the listbox), and scrollToId finds the block with
// closest(".listview-group"), because a row's parent is its chunk. 100 is the
// group size that measured fine; at the default 300 px height the browser
// renders at most two chunks.
export const ROW_CHUNK_SIZE = 100;

/** One render chunk of a block: its chunk number and the rows it holds. */
export interface RenderChunk {
  key: number;
  items: ListviewItem[];
}

/**
 * A block as the list renders it: its rows, whether it carries a header,
 * whether its group is open, whether it renders collapsed, and the chunks its
 * rows render in.
 */
export interface RenderBlock {
  group: RenderGroup;
  hasHeader: boolean;
  /**
   * The group's own state, which the chevron, aria-expanded and the arrow
   * keys show; `collapsed` folds in the search override.
   */
  open: boolean;
  collapsed: boolean;
  chunks: RenderChunk[];
}

/** A block's place among the blocks and its row count, in the unfiltered list. */
export interface BlockPlace {
  position: number;
  size: number;
}

export interface UseRenderBlocksArgs {
  /** Every row the list renders: the options and the synthetic rows. */
  allItems: ListviewItem[];
  /** The rows the search leaves (`useFilter`); `allItems` itself without a query. */
  visibleItems: ListviewItem[];
  isFiltering: boolean;
  ungroupedLabel: string;
  /** Whether the block without a group carries a header (`useGroupCollapse`). */
  isGrouped: boolean;
  /** Whether the list is a WAI-ARIA tree (`useGroupCollapse`). */
  asTree: boolean;
  collapse: UseCollapseResult;
}

export interface UseRenderBlocksResult {
  /** The blocks the list renders, each with its chunks; `[]` chunks while collapsed. */
  renderBlocks: RenderBlock[];
  /**
   * The rendered (filtered) blocks before the collapse and chunk pass, in
   * render order. The select-all scope reads them: a collapsed block stays in
   * scope.
   */
  renderGroups: RenderGroup[];
  /**
   * Each row's one-based place (aria-posinset), keyed by the item object: in
   * a listbox its place in the whole list, in a tree its place in its block.
   */
  rowPosition: Map<ListviewItem, number>;
  /** The number of rows in the whole list (a listbox row's aria-setsize). */
  listSize: number;
  /** Each block's place among the unfiltered blocks and its row count, keyed by its group. */
  blockPlace: Map<GroupKey, BlockPlace>;
  /**
   * The nodes the keyboard moves through, in the order they appear on
   * screen: the rows, and in a tree each block's header before its rows.
   */
  navNodes: NavNode[];
}

/**
 * The blocks the list renders and the per-row numbers that go with them. The
 * blocks come from `blocksFor`, which also serves the unfiltered positions, so
 * the rendered order and `aria-posinset` cannot disagree.
 */
export function useRenderBlocks({
  allItems,
  visibleItems,
  isFiltering,
  ungroupedLabel,
  isGrouped,
  asTree,
  collapse,
}: UseRenderBlocksArgs): UseRenderBlocksResult {
  // The blocks over EVERY row, filtered or not — the order aria-posinset counts
  // in — and the blocks the list renders (see blocksFor). Not filtering, they
  // are the same blocks: useFilter hands back `allItems` itself, so the
  // unfiltered blocks are reused rather than built twice.
  const allBlocks = useMemo(
    () => blocksFor(allItems, ungroupedLabel),
    [allItems, ungroupedLabel],
  );
  const renderGroups = useMemo(
    () =>
      visibleItems === allItems
        ? allBlocks
        : blocksFor(visibleItems, ungroupedLabel),
    [visibleItems, allItems, allBlocks, ungroupedLabel],
  );

  // Each row's one-based place, in render order, for aria-posinset: in a
  // listbox its place in the whole list, whose size (every row, filtered or
  // not) is aria-setsize; in a tree its place in its group, whose size is
  // aria-setsize, because a tree counts each level on its own. Each block's
  // place among the blocks and its row count come with it, for the tree's
  // group treeitems. `listSize` is the number of places handed out, which is
  // every row. The browser leaves the rows of a skipped render chunk out of
  // the accessibility tree, so without them a screen reader announced "23 of
  // 200" in a list of 100,000. Keyed by the item object and built from the
  // UNFILTERED blocks: a search keystroke or a click leaves every value
  // alone, so the memoized rows keep bailing out. A search therefore
  // announces places in the whole list (or group), not among the matches.
  const { rowPosition, listSize, blockPlace } = useMemo(() => {
    const byItem = new Map<ListviewItem, number>();
    const byBlock = new Map<GroupKey, BlockPlace>();
    let position = 0;
    allBlocks.forEach((block, index) => {
      byBlock.set(block.name, {
        position: index + 1,
        size: block.items.length,
      });
      block.items.forEach((item, inBlock) => {
        position += 1;
        byItem.set(item, asTree ? inBlock + 1 : position);
      });
    });
    return { rowPosition: byItem, listSize: position, blockPlace: byBlock };
  }, [allBlocks, asTree]);

  // Each row's render chunk: its place among ALL rows, filtered or not, in
  // steps of ROW_CHUNK_SIZE (see there for why it must not follow the filter).
  // Keyed by the item object, which the filter and the grouping pass through
  // unchanged. Rebuilt only when the rows themselves change, not per keystroke.
  const chunkOf = useMemo(() => {
    const byItem = new Map<ListviewItem, number>();
    allItems.forEach((item, i) => {
      byItem.set(item, Math.floor(i / ROW_CHUNK_SIZE));
    });
    return byItem;
  }, [allItems]);

  // Each block plus whether it carries a header, whether it renders collapsed
  // (a group is only visually collapsed while no search is active — search
  // overrides collapse) and the chunks its rows render in. Computed once so the
  // rendered blocks and navNodes cannot disagree, and so the chunks are
  // split only when the blocks change rather than on every render (each arrow
  // key, each click). A block keeps the order of `allItems`, so its chunk
  // numbers never decrease and each one is a single run — unique as a React key
  // within the block.
  const renderBlocks = useMemo(
    () =>
      renderGroups.map((group) => {
        // A block without a header cannot render collapsed: the header is its
        // only toggle. That holds even while useCollapse still lists the
        // block's `null` key as collapsed — a rerun that takes away the last
        // group prunes the key in an effect, after this render, and the list
        // would show an empty frame until then.
        const hasHeader = group.name != null || isGrouped;
        // The group's own state, which the chevron, aria-expanded and the
        // arrow keys show; `collapsed` folds in the search override.
        const open = !collapse.isCollapsed(group.name);
        const collapsed = hasHeader && !isFiltering && !open;
        return {
          group,
          hasHeader,
          open,
          collapsed,
          chunks: collapsed
            ? []
            : runsByKey(group.items, (item) => chunkOf.get(item) as number),
        };
      }),
    [renderGroups, isGrouped, isFiltering, collapse, chunkOf],
  );

  // The nodes the keyboard moves through: the rows of the rendered blocks,
  // minus collapsed ones, and in a tree each block's header before its rows.
  // Derived from the BLOCKS rather than from visibleItems so arrow-key order is
  // exactly the order the rows appear on screen — grouping reorders items
  // whenever a group's options are not contiguous in `options`, and the block
  // without a group always renders last. A header node carries the group's own
  // state, which ArrowLeft and ArrowRight read.
  const navNodes = useMemo<NavNode[]>(
    () =>
      renderBlocks.flatMap(({ group, open, collapsed }) => {
        const rows = collapsed ? [] : group.items;
        return asTree ? [new GroupNode(group.name, open), ...rows] : rows;
      }),
    [renderBlocks, asTree],
  );

  return {
    renderBlocks,
    renderGroups,
    rowPosition,
    listSize,
    blockPlace,
    navNodes,
  };
}
