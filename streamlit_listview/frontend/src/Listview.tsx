import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import type { CSSProperties, FC, MouseEvent } from "react";
import type { FrontendRendererArgs } from "@streamlit/component-v2-lib";
import type { Id, ListviewData, ListviewItem, ListviewState } from "./types";
import { WidgetLabel } from "./components/WidgetLabel";
import { GroupHeader } from "./components/GroupHeader";
import { ListItem } from "./components/ListItem";
import { SearchField } from "./components/SearchField";
import { SelectAllToggle } from "./components/SelectAllToggle";
import { NewOptionInput } from "./components/NewOptionInput";
import { useSelection } from "./hooks/useSelection";
import { useKeyboardNav } from "./hooks/useKeyboardNav";
import { useFilter } from "./hooks/useFilter";
import { useCollapse, type GroupKey } from "./hooks/useCollapse";
import { useScrollToItem } from "./hooks/useScrollToItem";
import { useColorScheme } from "./hooks/useColorScheme";
import { useRowHeight } from "./hooks/useRowHeight";
import { useResetChunkHeights } from "./hooks/useResetChunkHeights";
import { FORGET_CLASS } from "./utils/chunks";
import { disabledIdSet, idKey, itemIdByKey, parseNewIntId } from "./utils/ids";
import { reuseUnchangedItems, runsByKey } from "./utils/items";
import { foldForMatch } from "./utils/text";

// Module-level empty results for the "nothing to compute" paths below. Safe to
// share because every consumer only reads them — the render spreads/filters/maps
// them, and useSelection's bulk helpers copy the selection before appending.
//
// They exist for their IDENTITY, not to save an allocation: each is returned from
// a useMemo, and a fresh `[]` per render would count as a change and invalidate
// every memo downstream of it. `NO_NEW_OPTIONS` is the load-bearing one —
// newOptionItems has to depend on the live selection, so with accept_new_options
// OFF (the common case) a fresh `[]` gave `allItems` a new identity on every
// click, re-running the filter, the folded labels, the grouping and the scope
// passes over every row for a list that cannot have added rows at all.
const NO_NEW_OPTIONS: ListviewItem[] = [];
const NO_TARGET_IDS: Id[] = [];
const NO_DISABLED_IDS: Set<Id> = new Set();
const EMPTY_ID_MAP: Map<string, Id> = new Map();

// A block renders its rows in keyed "render chunks" of ROW_CHUNK_SIZE rows,
// each a `div.listview-chunk`, not as one flat run. Two costs set that shape.
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
// block's role="group" (or of the listbox), and scrollToId finds the block with
// closest(".listview-group"), because a row's parent is its chunk. 100 is the
// group size that measured fine; at the default 300 px height the browser
// renders at most two chunks.
const ROW_CHUNK_SIZE = 100;

export interface ListviewProps {
  data: ListviewData;
  setStateValue: FrontendRendererArgs<ListviewState>["setStateValue"];
  /**
   * Whether this instance is mounted in Streamlit's sidebar, which swaps the
   * two background tokens the sheet paints its surfaces from (see
   * `utils/container.ts`). Resolved in `index.tsx` from the renderer's
   * `parentElement` rather than by a hook here, so the flag is on the root
   * before first paint: an effect-based read would land a frame late and flash
   * the main-body colors on every mount.
   */
  inSidebar?: boolean;
}

interface RenderGroup {
  name: string | null;
  items: ListviewItem[];
}

/**
 * The block a row with `group` renders in: its group, or `null` for the block
 * without a group. A group named like `ungrouped_label` belongs to that block
 * too: it would otherwise render a second header with the same text, and two
 * headers the user cannot tell apart are no better than none.
 */
function blockKeyOf(
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
function blocksFor(
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
    blocks[idx].items.push(item);
  }
  // A filter that leaves no row without a group adds no empty block.
  if (ungrouped.length > 0) {
    blocks.push({ name: null, items: ungrouped });
  }
  return blocks;
}

function optionDomId(id: Id): string {
  return `listview-opt-${idKey(id)}`;
}

/**
 * The synthetic row an id absent from `options` renders as, under
 * accept_new_options: its own text as the label, because there is no option
 * object to take one from.
 *
 * ONE definition, because such a row can arrive by three routes — seeded from
 * `default`, found selected-but-unknown, or just typed — and a rule applied to
 * one route only would give a single entry two different labels depending on how
 * it got there. Labelling via `idKey` rather than a second `String(id)` for the
 * same reason row identity funnels through it (see utils/ids).
 */
function newOptionRow(id: Id): ListviewItem {
  return { id, label: idKey(id) };
}

/**
 * Element-wise equality for two synthetic-row lists: the same rows (by `idKey`)
 * carrying the same labels. The rows are freshly allocated per rebuild (see
 * `newOptionRow`), so object identity cannot answer this; the memo below uses it
 * to keep the previous ARRAY's identity when a rebuild changed nothing.
 */
function sameNewOptionRows(a: ListviewItem[], b: ListviewItem[]): boolean {
  return (
    a.length === b.length &&
    a.every(
      (item, i) =>
        idKey(item.id) === idKey(b[i].id) && item.label === b[i].label,
    )
  );
}

/** Where a scrolled-to row lands in the frame (the ScrollLogicalPosition subset we implement). */
type ScrollBlock = "center" | "nearest";

/**
 * How many frames scrollToId waits for the target row's chunk to drop
 * FORGET_CLASS before it measures the row anyway. useResetChunkHeights keeps
 * the class on for two frames; the bound only keeps a class that somehow
 * stayed from parking the scroll forever.
 */
const FORGET_WAIT_FRAMES = 4;

/**
 * How many frames scrollToId waits for the list's stylesheet before it measures
 * the row anyway: about ten seconds at 60 Hz. A remounted instance fetches its
 * stylesheet again, so on a slow connection the sheet arrives frames after the
 * first commit. The bound only stops the wait for a sheet that never loads.
 */
const STYLE_WAIT_FRAMES = 600;

/**
 * True once listview.css applies to the list: it makes the body a scroll
 * container (overflow-y: auto), and until then the computed value is the
 * initial `visible`. Before that the rows are unstyled and a scrollTop written
 * to the body is lost.
 */
function isStyled(body: HTMLElement): boolean {
  return getComputedStyle(body).overflowY !== "visible";
}

/**
 * The rendered row carrying `domId` inside `body`, or null when it is not
 * rendered (filtered out, in a collapsed group).
 *
 * Looked up through the tree scope the body lives in. In production that is
 * THIS instance's ShadowRoot (`isolate_styles=True`, Streamlit's default — the
 * renderer is handed the ShadowRoot as `parentElement`), so `getElementById` is
 * an id-map hit rather than a walk over every rendered row per arrow key, and
 * sibling listviews cannot see each other's rows even though `optionDomId`
 * carries no instance prefix — the same per-tree scoping `aria-activedescendant`
 * already relies on. It also takes a RAW string, so an id holding a newline, a
 * quote or a backslash needs no CSS escaping: with plain (non-dict) options the
 * id IS the option string, and a `[id="…"]` selector threw SyntaxError from
 * inside the rAF callback, where no React error boundary can catch it (even
 * CSS.escape was not a full answer — jsdom's selector engine fails to match a
 * correctly escaped backslash).
 *
 * A hit that is not inside this body — a light-DOM mount (`isolate_styles=False`,
 * or the jsdom test tree) where a same-id row of ANOTHER instance answered first
 * — falls back to scanning this body's own rows by `id` property, so every mount
 * mode resolves the right row; only the hot path changes. The scan is bounded by
 * the rendered rows (this list is not virtualized) and walked by index rather
 * than `Array.from(…).find(…)`, which materialized all rows into a fresh array
 * first.
 */
function findRowNode(body: HTMLElement, domId: string): Element | null {
  const root = body.getRootNode();
  // A subtree not (yet) attached to a document has its topmost ELEMENT as
  // root, and an element has no id map — the renderer can be invoked on a
  // detached host — so only a Document / ShadowRoot root takes the fast path.
  const hit =
    "getElementById" in root
      ? (root as Document | ShadowRoot).getElementById(domId)
      : null;
  if (hit !== null && body.contains(hit)) {
    return hit;
  }
  const rows = body.querySelectorAll('[role="option"]');
  for (let i = 0; i < rows.length; i += 1) {
    if (rows[i].id === domId) {
      return rows[i];
    }
  }
  return null;
}

/**
 * The hint NewOptionInput shows when int options refuse a typed value that is
 * not a whole number (see parseNewIntId).
 */
const NOT_A_WHOLE_NUMBER = "Enter a whole number";

/**
 * The row a typed `accept_new_options` value refers to, or undefined when the
 * value is genuinely new. The row, not just its id: the add reveals it, and
 * that needs the row's group.
 *
 * Folding goes through the shared `foldForMatch` — literally the fold the search
 * filter uses — so "already in the list" and "findable by searching" agree:
 * anything the user could have found by typing it into the search box resolves to
 * that row instead of spawning a duplicate.
 *
 * Resolution order:
 *  1. an exact row-identity (`idKey`) hit, so a typed "7" lands on numeric id 7;
 *  2. a folded match against the row's LABEL — the only thing the user can
 *     actually see, because Python applies `format_func`/`label` server-side (an
 *     option {"id": "the_hague", "label": "The Hague"} shows *no* trace of its
 *     id). Without this, typing the visible text of an existing option spawned a
 *     second, visually identical row and committed the bare string beside the
 *     option object for one and the same entry.
 *  3. a folded match against the id, so a case/whitespace variant of a plain
 *     option ("APPLE" for id/label "Apple") still resolves.
 *
 * Each step scans ALL rows before the next one runs — the label pass and the id
 * pass are separate passes, not one combined test per row. Folding both into a
 * single find() let an earlier row's hidden-id match shadow a later row's
 * visible-label match, so typing exactly what a row SAYS selected a different
 * row whose invisible id happened to spell the same text.
 *
 * Ties within a step (two rows folding to the same text) resolve to the first in
 * render order. A disabled row resolves like any other: `selection.add` is inert
 * for it, so typing its label is a no-op rather than a duplicate row.
 */
function findExistingRow(
  items: ListviewItem[],
  value: string,
): ListviewItem | undefined {
  const exact = items.find((item) => idKey(item.id) === value);
  if (exact !== undefined) {
    return exact;
  }
  const folded = foldForMatch(value);
  const byLabel = items.find((item) => foldForMatch(item.label) === folded);
  if (byLabel !== undefined) {
    return byLabel;
  }
  return items.find((item) => foldForMatch(idKey(item.id)) === folded);
}

export const Listview: FC<ListviewProps> = ({
  data,
  setStateValue,
  inSidebar,
}) => {
  const widgetDisabled = data.disabled;

  const [query, setQuery] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const listboxRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  // "light" | "dark" from the active Streamlit theme (not the OS scheme), so
  // the help tooltip can match Streamlit's themed tooltip surface.
  const colorScheme = useColorScheme(rootRef);

  // The caller's options, with every item unchanged since the previous render
  // kept as the previous render's OBJECT — and the previous array itself when
  // nothing changed. Each rerun ships the options as freshly parsed JSON, so
  // reading `data.items` directly made every rerun of the app (any widget, not
  // just this one) recompute every memo below that is keyed on the items and
  // re-render every row: O(N) per rerun for a list whose options never moved.
  // Read the options through `items` only, never `data.items`. The render-body
  // ref write follows the prevNewOptionItemsRef pattern below.
  const prevItemsRef = useRef<ListviewItem[]>(data.items);
  /* eslint-disable react/refs -- a deliberate render-body ref, see above */
  const items = reuseUnchangedItems(prevItemsRef.current, data.items);
  prevItemsRef.current = items;
  /* eslint-enable react/refs */

  // What a fresh mount seeds the selection from: the persisted Python-side
  // selection when this mount is a remount that kept the widget state (a keyed
  // instance moved between st.sidebar and the main body — the element id drops
  // the container), else the caller's `default`. Consumed only by mount-time
  // initializers, so a later change to either field never re-seeds (see
  // useSelection). `??`, not `||`: an empty persisted selection is a cleared
  // selection that must survive the move, not a fallback to `default`.
  const seedSelection = data.state_selection ?? data.default_ids;

  const selection = useSelection({
    items,
    selectionMode: data.selection_mode,
    maxSelections: data.max_selections,
    acceptNewOptions: data.accept_new_options,
    initialSelection: seedSelection,
    setStateValue,
  });

  // Options the user added via accept_new_options, persisted in frontend state
  // so an added option stays in the list (as a re-selectable row) after it is
  // deselected — in single mode, picking another option would otherwise drop it
  // entirely. Seeded with any unknown ids in the mount's seed selection: a
  // persisted selection carries the values the user typed before a remount, and
  // Python permits unknown ids in `default` when accept_new_options is on. Like
  // other UI-only state this survives reruns when the instance is keyed; a
  // keyless instance remounts and re-seeds.
  const [addedItems, setAddedItems] = useState<ListviewItem[]>(() => {
    if (!data.accept_new_options) {
      return [];
    }
    // "Unknown option?" is a row-identity question, so compare by idKey: the
    // seeded ids come from Python's `default` or the persisted selection, the
    // two lists whose ids can spell a row differently than `items` does
    // (accept_new_options lets `default="7"` past the unknown-id check while
    // `options` holds the int 7), which is exactly the case a raw comparison
    // would call unknown.
    const known = itemIdByKey(items);
    return seedSelection
      .filter((id) => !known.has(idKey(id)))
      .map((id) => newOptionRow(id));
  });

  // Row identity -> the option's own id, over the CALLER's options. Hoisted so
  // the memo below stops rebuilding it per click: it depends on the live
  // selection, so with accept_new_options on every click walked every row
  // (5000 String() + Map.set at the design target) over data that had not moved.
  // Gated on accept_new_options — that memo is the only consumer and bails to
  // NO_NEW_OPTIONS before reading this, so with the feature off (the common
  // case) the walk is skipped entirely.
  const knownIds = useMemo(
    () => (data.accept_new_options ? itemIdByKey(items) : EMPTY_ID_MAP),
    [data.accept_new_options, items],
  );

  // Synthetic rows for ids absent from items, surfaced only when
  // accept_new_options is on: the persisted added options PLUS any other
  // selected-but-unknown id (e.g. a stale value left over when the caller
  // shrank `options`).
  //
  // Row identity is by idKey (React keys, DOM ids), so both the "is this a
  // known option?" check and the dedup compare idKey — NOT the raw id.
  // Otherwise a numeric id and its string form (7 and "7") render as two
  // indistinguishable rows with a colliding key/DOM id, and a stale added option
  // is not dropped when the caller later promotes it into `options` with a
  // different id type (string "5" added, then numeric 5 in options).
  const builtNewOptionItems = useMemo<ListviewItem[]>(() => {
    if (!data.accept_new_options) {
      return NO_NEW_OPTIONS;
    }
    const seen = new Set<string>();
    const out: ListviewItem[] = [];
    // Persisted added options first (keep their typed label), then any other
    // selected-but-unknown id.
    const candidates: ListviewItem[] = [
      ...addedItems,
      ...selection.selection.map((id) => newOptionRow(id)),
    ];
    for (const item of candidates) {
      const key = idKey(item.id);
      if (knownIds.has(key) || seen.has(key)) {
        continue;
      }
      seen.add(key);
      out.push(item);
    }
    // The shared empty array, not this render's `out`, when nothing was added:
    // identity is what keeps `allItems` — and the whole filter/fold/group/scope
    // chain below it — from being invalidated by a click that cannot have changed
    // the synthetic rows. That covers the dominant accept_new_options state
    // (feature on, nothing typed yet), which the constant alone did not.
    return out.length === 0 ? NO_NEW_OPTIONS : out;
  }, [data.accept_new_options, knownIds, addedItems, selection.selection]);

  // The non-empty counterpart of NO_NEW_OPTIONS above: the memo depends on the
  // live selection, so once one synthetic row exists every click rebuilt an
  // equal-but-new array and invalidated that same chain per click. Same
  // resolution as reconcileSelection (useSelection): hand back the previous
  // value when the rebuild is element-wise identical. The render-body ref write
  // follows the itemClickRef pattern below.
  const prevNewOptionItemsRef = useRef<ListviewItem[]>(NO_NEW_OPTIONS);
  /* eslint-disable react/refs -- a deliberate render-body ref, see above */
  const newOptionItems = sameNewOptionRows(
    prevNewOptionItemsRef.current,
    builtNewOptionItems,
  )
    ? prevNewOptionItemsRef.current
    : builtNewOptionItems;
  prevNewOptionItemsRef.current = newOptionItems;
  /* eslint-enable react/refs */

  const allItems = useMemo(
    () => [...items, ...newOptionItems],
    [items, newOptionItems],
  );

  const { visibleItems, isFiltering } = useFilter({ items: allItems, query });

  const ungroupedLabel = data.ungrouped_label;
  // One pass over the caller's options (blocks as in blockKeyOf):
  //  - groupNames: the named blocks, in the order they first appear;
  //  - isGrouped: one of the options names a group, the one named like
  //    ungrouped_label included. Only then does the block without a group
  //    carry a header and count as a group of its own. Judged on the unfiltered
  //    options, so a search never adds or drops that header;
  //  - hasUngroupedOption: one of the options renders in that block.
  const { groupNames, isGrouped, hasUngroupedOption } = useMemo(() => {
    const names = new Set<string>();
    let grouped = false;
    let ungrouped = false;
    for (const item of items) {
      grouped ||= item.group != null;
      const key = blockKeyOf(item.group, ungroupedLabel);
      if (key === null) {
        ungrouped = true;
      } else {
        names.add(key);
      }
    }
    return {
      groupNames: Array.from(names),
      isGrouped: grouped,
      hasUngroupedOption: ungrouped,
    };
  }, [items, ungroupedLabel]);
  // The groups useCollapse tracks: every named group, plus `null` for the block
  // without a group while it carries a header — that is, while some row renders
  // in it, among the caller's options or the added ones.
  const groupKeys = useMemo<GroupKey[]>(() => {
    if (!isGrouped) {
      return groupNames;
    }
    return hasUngroupedOption || newOptionItems.length > 0
      ? [...groupNames, null]
      : groupNames;
  }, [groupNames, isGrouped, hasUngroupedOption, newOptionItems]);
  // collapsed_groups names headers, so ungrouped_label in it names the block
  // without a group.
  const collapsedGroups = useMemo(
    () =>
      Array.isArray(data.collapsed_groups)
        ? data.collapsed_groups.map((name) => blockKeyOf(name, ungroupedLabel))
        : data.collapsed_groups,
    [data.collapsed_groups, ungroupedLabel],
  );
  const collapse = useCollapse({
    collapsibleGroups: data.collapsible_groups,
    collapsedGroups,
    groupKeys,
  });
  // Opens the block a row with `group` renders in, before a scroll to that row.
  // A block without a header — the one block of a list without groups — cannot
  // be collapsed, and expanding its `null` key anyway would count as a
  // sighting: a later rerun that brings in groups would then skip the
  // collapsed_groups="all" seed for the block without a group.
  const expandGroup = collapse.expand;
  const expandBlock = useCallback(
    (group: string | null) => {
      const key = blockKeyOf(group, ungroupedLabel);
      if (key !== null || isGrouped) {
        expandGroup(key);
      }
    },
    [expandGroup, isGrouped, ungroupedLabel],
  );

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

  // Each row's one-based place in the whole list, in render order, for
  // aria-posinset; aria-setsize is the number of places handed out, which is
  // every row, filtered or not. (`rowPosition.size` rather than
  // `allItems.length`: the same number, but oxlint's react/refs rule reads
  // `allItems`, built from the render-body ref above, captured in the row
  // callback as a ref read during render.) The browser leaves the rows of
  // a skipped render chunk out of the accessibility tree, so without them a
  // screen reader announced "23 of 200" in a list of 100,000. Keyed by the item
  // object and built from the UNFILTERED blocks: a search keystroke or a click
  // leaves every value alone, so the memoized rows keep bailing out. A search
  // therefore announces places in the whole list, not among the matches.
  const rowPosition = useMemo(() => {
    const byItem = new Map<ListviewItem, number>();
    let position = 0;
    for (const block of allBlocks) {
      for (const item of block.items) {
        position += 1;
        byItem.set(item, position);
      }
    }
    return byItem;
  }, [allBlocks]);
  const setSize = rowPosition.size;

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
  // render below and focusableItems cannot disagree, and so the chunks are
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
        const collapsed =
          hasHeader && !isFiltering && collapse.isCollapsed(group.name);
        return {
          group,
          hasHeader,
          collapsed,
          chunks: collapsed
            ? []
            : runsByKey(group.items, (item) => chunkOf.get(item) as number),
        };
      }),
    [renderGroups, isGrouped, isFiltering, collapse, chunkOf],
  );

  // Items that can take keyboard focus: the rendered blocks flattened, minus
  // collapsed ones. Derived from the BLOCKS rather than from visibleItems so
  // arrow-key order is exactly the order the rows appear on screen — grouping
  // reorders items whenever a group's options are not contiguous in `options`,
  // and the block without a group always renders last.
  const focusableItems = useMemo(
    () =>
      renderBlocks.flatMap(({ group, collapsed }) =>
        collapsed ? [] : group.items,
      ),
    [renderBlocks],
  );

  // Bulk-action scope (D3): the post-filter visible set MINUS disabled rows,
  // in render order. Sourced from renderGroups (NOT focusableItems), so rows in
  // collapsed groups stay in scope (collapse is visual, not a filter), and in
  // the order the rows appear: Select all fills a max_selections cap from the
  // top of the list as shown, while grouping moves rows away from their place
  // in the options (the block without a group renders last). Because the
  // groups derive from allItems, accept_new_options synthetic rows are included
  // automatically.
  //
  // Gated on select_all, because the toggle is the ONLY consumer of this scope
  // and of everything derived from it (allVisibleSelected / someVisibleSelected /
  // isFull / canToggle all read targetIds and nothing else reads them). With the
  // gate off the empty scope makes those short-circuit, so the whole chain costs
  // nothing instead of one n-sized allocation plus three passes over every
  // visible row on each of the two renders a click produces. Python forbids
  // select_all in single mode, so on a long single-select list that work was not
  // merely wasted, it was unreachable-by-construction.
  //
  // Disabled-id membership for that exclusion (useSelection keeps its own private
  // set over items; the scope needs one over allItems, so the
  // accept_new_options rows are covered too). Its OWN memo, keyed on allItems,
  // rather than built inside targetIds: the disabled set cannot change with the
  // query, so folding it in there rebuilt a whole 5000-entry Set on every search
  // keystroke — 25,000 insertions for a five-character query where 5,000 do.
  const disabledIds = useMemo(
    () => (data.select_all ? disabledIdSet(allItems) : NO_DISABLED_IDS),
    [data.select_all, allItems],
  );

  const targetIds = useMemo(() => {
    if (!data.select_all) {
      return NO_TARGET_IDS;
    }
    const ids: Id[] = [];
    for (const group of renderGroups) {
      for (const item of group.items) {
        if (!disabledIds.has(item.id)) {
          ids.push(item.id);
        }
      }
    }
    return ids;
  }, [data.select_all, disabledIds, renderGroups]);

  // Select-all toggle state (D4), derived off the live selection so it stays
  // correct on the accept_new_options path too. Memoized on exactly what it
  // reads — the scope plus the two selection predicates, each of which is stable
  // while the selection is — because in the common "nothing in scope selected
  // yet" state the `some` cannot short-circuit and scans the entire scope: in the
  // render body that was 5000 lookups on EVERY render, i.e. every keystroke,
  // every arrow key and both renders a click produces.
  const { allVisibleSelected: isEverySelected, isSelected } = selection;
  const [allVisibleSelected, someVisibleSelected] = useMemo(
    () =>
      [
        targetIds.length > 0 && isEverySelected(targetIds),
        targetIds.some((id) => isSelected(id)),
      ] as const,
    [targetIds, isEverySelected, isSelected],
  );
  // The select-all toggle only renders in multi mode (Python rejects
  // select_all=True for single), so the hook's multi-guarded atCap is exactly
  // the cap signal we need here.
  const atCap = selection.atCap;
  // isFull => the toggle reads "Deselect all" and clears the visible scope. The
  // sensible moments to offer that: every visible row is already selected, OR
  // the cap blocks adding more AND there is something visible to clear. The
  // second clause's "something visible to clear" guard is what stops a cap
  // reached by rows the search hides from showing an enabled "Deselect all"
  // that deselectVisible(targetIds) would no-op on.
  const isFull = allVisibleSelected || (atCap && someVisibleSelected);
  // The toggle can act iff its action changes the selection. The "Deselect all"
  // state always has visible rows to clear, so it is always actionable; the
  // "Select all" state can add rows only when there is room under the cap.
  const canToggle = isFull || !atCap;

  const onSelect = useCallback(
    (id: Id) => {
      // Defense-in-depth: unreachable while disabled (the listbox drops its
      // keydown handler), so this guard never trips via the UI.
      /* v8 ignore next 3 */
      if (widgetDisabled) {
        return;
      }
      selection.toggle(id);
    },
    [widgetDisabled, selection],
  );

  const onEscape = useCallback(() => {
    // Defense-in-depth: unreachable while disabled (search input + listbox
    // keydown are both inert then), so this guard never trips via the UI.
    /* v8 ignore next 3 */
    if (widgetDisabled) {
      return;
    }
    // Escape targets the search BOX first whenever it holds any text — the same
    // `value.length > 0` that shows SearchField's × button — and only then the
    // selection. Not `isFiltering`: that folds (trims) the query, so a box
    // holding only spaces counted as "not filtering" and Escape skipped the
    // visibly non-empty box to wipe the selection instead — committing state
    // and firing on_change while the spaces (and the × button) stayed put.
    // The two mistakes are not symmetric: clearing text is free, clearing the
    // selection is a state write the user did not ask for. `useFilter` keeps
    // sole ownership of "a query is active" for filtering; this is "the box is
    // non-empty", which is the box's own definition.
    if (query.length > 0) {
      setQuery("");
    } else {
      selection.clear();
    }
  }, [widgetDisabled, query, selection]);

  const onSlash = useCallback(() => {
    searchInputRef.current?.focus();
  }, []);

  // A list shorter than `height` leaves empty space below its last row, and that
  // space is .listview-body itself — not focusable — so a click there moved focus
  // nowhere and the frame never lit up, where st.text_area focuses on the same
  // click. Forward it to the listbox. Only a click on the body ITSELF: rows and
  // the in-flow search field are children that already focus their own target,
  // and taking it would pull the caret out of an input.
  // preventScroll: the listbox is taller than the frame it scrolls in.
  const onBodyClick = useCallback((event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      (listboxRef.current as HTMLDivElement).focus({ preventScroll: true });
    }
  }, []);

  // The first row's height, published on the listbox for the size estimate of
  // the render chunks the browser skips (see ROW_CHUNK_SIZE). A layout effect,
  // so it lands before the first paint and before useScrollToItem's rAF
  // measures where a default row lies. scrollToId measures the first row again
  // through the returned function before it measures a row of its own.
  const remeasureRowHeight = useRowHeight(listboxRef);

  // DOM scroll for a row id, shared by jump-to-default and keyboard navigation.
  // rAF so an auto-expand (or focus-move) re-render commits before we
  // measure/scroll.
  //
  // Scrolls THE LIST BODY ONLY, by container-relative scrollTop math.
  // Element.scrollIntoView() would be shorter but it scrolls every scrollable
  // ancestor, including the Streamlit page: a listview with `default=` below the
  // fold yanked the host page away from whatever the user was reading, on first
  // render and on every rerun that changed `default_ids` by value.
  //
  // Two things must hold before a row's position means anything, and both fail
  // on a key-change remount, whose new shadow root loads the stylesheet again.
  // The stylesheet must have applied: until then the body does not scroll, so
  // the jump waits a frame at a time (whenStyled). And the published row height
  // must match the styled rows: the chunks above the target are sized by it, so
  // a stale height puts the row elsewhere than the browser later draws it. The
  // ResizeObserver in useRowHeight publishes a changed height a frame after
  // the listbox resized, which is a frame after this jump would measure. So
  // attempt() measures the first row again before it measures the target.
  const scrollToId = useCallback(
    (id: Id, block: ScrollBlock = "center") => {
      const attempt = (framesLeft: number): void => {
        const body = bodyRef.current;
        // Unreachable in practice: the body renders unconditionally, and this
        // callback only runs after a commit. It guards an unmount racing the
        // rAF.
        /* v8 ignore next 3 */
        if (!body) {
          return;
        }
        const node = findRowNode(body, optionDomId(id));
        if (node === null) {
          return; // row not rendered (e.g. filtered out) → nothing to scroll to
        }
        // A row's parent is its render chunk. While the chunk carries
        // FORGET_CLASS (content-visibility: hidden, see useResetChunkHeights)
        // the row has no geometry, so a jump to a new default inside a chunk
        // whose rows changed on the same rerun would measure a zero rect. Wait
        // a frame and look again; the class goes after two.
        if (
          framesLeft > 0 &&
          (node.parentElement as HTMLElement).classList.contains(FORGET_CLASS)
        ) {
          requestAnimationFrame(() => attempt(framesLeft - 1));
          return;
        }
        remeasureRowHeight();
        const frame = body.clientHeight;
        const rowBox = node.getBoundingClientRect();
        // The row's offset inside the scrolled content: its position relative
        // to the frame, plus however far the frame is already scrolled.
        // scrollTop is measured from the padding-box edge while the rect is the
        // border box, so the body's top border (clientTop) comes out —
        // otherwise every "nearest" scroll landed one border-width off,
        // clipping the row.
        const top =
          body.scrollTop +
          rowBox.top -
          (body.getBoundingClientRect().top + body.clientTop);
        if (block === "center") {
          // Out-of-range assignments are clamped by the browser, so the first
          // and last rows need no special casing.
          body.scrollTop = top - (frame - rowBox.height) / 2;
        } else {
          // A grouped row's own header is position: sticky; top: 0 — it
          // paints over the top of the scrollport, so the band where a row is
          // actually visible starts BELOW it. Bringing a row's top edge to the
          // frame's top edge parked it exactly under that header: ArrowUp /
          // Home focused a row the user could not see, and Enter selected it. A
          // row always renders in a render chunk inside a group block, and the
          // block's first child is either that header or a chunk, so this is a
          // fixed class-name check with none of the id-escaping hazards of the
          // row lookup; a block without a header (the one block of a list
          // without groups) keeps the frame edge. closest(), not
          // parentElement: a row's parent is its chunk.
          const first = (node.closest(".listview-group") as HTMLElement)
            .firstElementChild as Element;
          const stickyHeight = first.classList.contains("listview-group-header")
            ? first.getBoundingClientRect().height
            : 0;
          if (top - stickyHeight < body.scrollTop) {
            body.scrollTop = top - stickyHeight; // above the visible band → top edge in, under the header
          } else if (top + rowBox.height > body.scrollTop + frame) {
            body.scrollTop = top + rowBox.height - frame; // below → bottom edge in
          }
        }
      };
      const whenStyled = (framesLeft: number): void => {
        const body = bodyRef.current;
        if (!body) {
          return; // unmounted while it waited
        }
        if (framesLeft > 0 && !isStyled(body)) {
          requestAnimationFrame(() => whenStyled(framesLeft - 1));
          return;
        }
        attempt(FORGET_WAIT_FRAMES);
      };
      requestAnimationFrame(() => whenStyled(STYLE_WAIT_FRAMES));
    },
    [remeasureRowHeight],
  );

  // Keyboard focus moves only need the row brought just inside the frame:
  // "nearest" leaves an already-visible row exactly where it is, so arrowing
  // between visible rows never jogs the list under the user, while a step past
  // either edge scrolls by exactly one row.
  const scrollFocusIntoView = useCallback(
    (id: Id) => scrollToId(id, "nearest"),
    [scrollToId],
  );

  const nav = useKeyboardNav({
    items: focusableItems,
    onSelect,
    onSlash: data.enable_search ? onSlash : undefined,
    onEscape,
    // Keyboard focus is virtual (aria-activedescendant), and browsers only
    // auto-scroll for real DOM focus — so the ring has to be scrolled into view
    // here, through the same helper the jump-to-default path uses.
    scrollToId: scrollFocusIntoView,
  });

  // Stable identity (empty deps) via a latest-values ref, so the memoized
  // ListItem rows can bail out when only a sibling row's selected/focused state
  // changed. selection.toggle and nav.setFocusToId are recreated every render
  // (they close over the current selection/focus), so depending on them
  // directly would give every row a new onSelect prop and defeat the memo.
  const itemClickRef = useRef({
    widgetDisabled,
    setFocusToId: nav.setFocusToId,
    toggle: selection.toggle,
  });
  // eslint-disable-next-line react/refs -- a deliberate render-body ref, see above
  itemClickRef.current = {
    widgetDisabled,
    setFocusToId: nav.setFocusToId,
    toggle: selection.toggle,
  };
  const onItemClick = useCallback((id: Id) => {
    const {
      widgetDisabled: disabled,
      setFocusToId,
      toggle,
    } = itemClickRef.current;
    // Defense-in-depth: ListItem already blocks clicks while disabled, so this
    // never fires then.
    /* v8 ignore next 3 */
    if (disabled) {
      return;
    }
    setFocusToId(id);
    toggle(id);
  }, []);

  // The row an add resolved to, scrolled into view once it has rendered. The
  // add field sits in the footer, below the scroll frame, so that row can lie
  // anywhere in the list, and its block may be collapsed. A state and an
  // effect, not a direct scrollToId call from the handler: the effect runs
  // after the commit that renders the row, and a fresh object per request
  // commits even when the add changed nothing else (the typed label of a row
  // that is already selected). scrollToId keeps its identity across renders
  // (remeasureRowHeight does), so the effect runs once per request.
  const [revealRequest, setRevealRequest] = useState<{ id: Id } | null>(null);
  useEffect(() => {
    if (revealRequest !== null) {
      scrollToId(revealRequest.id, "nearest");
    }
  }, [revealRequest, scrollToId]);
  const revealRow = useCallback(
    (id: Id, group: string | null) => {
      expandBlock(group);
      setRevealRequest({ id });
    },
    [expandBlock],
  );

  const onAddNewOption = useCallback(
    (value: string): string | null => {
      // Defense-in-depth: NewOptionInput is disabled then, so this never fires.
      /* v8 ignore next 3 */
      if (widgetDisabled) {
        return null;
      }
      // Resolve a typed value against ALL rendered rows (known options + synthetic
      // ones) by row identity AND by visible label, so it matches an existing row
      // whether that row is a known option or an already-added / selected
      // synthetic one. Resolved here in the cold add path, not as a per-render
      // memo over every row.
      const existing = findExistingRow(allItems, value);
      if (existing !== undefined) {
        // Matches an existing option (a numeric id typed as text, or the label the
        // user can actually see): select that option rather than spawn a
        // duplicate row, and show the user where that row is.
        selection.add(existing.id);
        revealRow(existing.id, existing.group ?? null);
        return null;
      }
      // Genuinely new. With int options (Python's new_option_kind) the entry must
      // be a whole number, added as a NUMBER: the selection, its synthetic row and
      // the persisted state then hold a real int, and listview() returns 42, not
      // "42". Checked before the cap below, so a refused value is explained even
      // when nothing more could be added.
      const newId =
        data.new_option_kind === "int" ? parseNewIntId(value) : value;
      if (newId === undefined) {
        return NOT_A_WHOLE_NUMBER;
      }
      // In multi mode at the cap the add would be rejected by useSelection, so do
      // NOT persist a phantom row that was never actually selected (and that the
      // user then cannot easily remove). Single mode always replaces, so atCap is
      // never set there.
      if (selection.atCap) {
        return null;
      }
      // Remember it so it persists as a row after deselection, then select it.
      setAddedItems((prev) => {
        // Defence in depth, unreachable in practice: once a value is in
        // addedItems it is also in allItems, so findExistingRow above already
        // returned. It only guards a re-entrant add that closed over a stale
        // allItems within a single React batch. Marked as a guard (condition +
        // early return) so the append below stays measured.
        /* v8 ignore next 3 */
        if (prev.some((it) => it.id === newId)) {
          return prev;
        }
        return [...prev, newOptionRow(newId)];
      });
      selection.add(newId);
      // A new entry has no group, so it joins the block without a group.
      revealRow(newId, null);
      return null;
    },
    [widgetDisabled, allItems, selection, data.new_option_kind, revealRow],
  );

  // After a commit that changed the blocks, a skipped chunk whose rows changed
  // forgets the height the browser remembered from its last render (see
  // useResetChunkHeights): otherwise a search after scrolling left every chunk
  // scrolled past at the height of the rows it no longer holds.
  useResetChunkHeights(listboxRef, renderBlocks);

  useScrollToItem({
    defaultIds: data.default_ids,
    items: allItems,
    ensureGroupExpanded: expandBlock,
    scrollToId,
  });

  const rootStyle = useMemo<CSSProperties>(() => {
    const style: Record<string, string> = {
      "--listview-height": `${data.height}px`,
      "--listview-width": data.width === "stretch" ? "100%" : `${data.width}px`,
    };
    if (data.item_height != null) {
      style["--listview-item-height"] = `${data.item_height}px`;
    }
    if (data.content_font_size != null) {
      style["--listview-content-font-size"] = `${data.content_font_size}px`;
    }
    return style as CSSProperties;
  }, [data.height, data.width, data.item_height, data.content_font_size]);

  const rootClassName =
    "listview" +
    (widgetDisabled ? " listview--disabled" : "") +
    (data.show_grid_lines ? "" : " listview--no-grid");
  const isEmpty = allItems.length === 0;
  // The listbox's accessible name (WCAG 4.1.2). Without it a screen reader
  // announced only "list box, N items": the visible label is deliberately
  // aria-hidden, and the help trigger names itself, not the widget (and is absent
  // when help is None or label_visibility is not "visible"). aria-labelledby
  // rather than a duplicated aria-label string, so the name is whatever the label
  // markdown actually renders; WidgetLabel owns the span it points at.
  const labelId = useId();
  const focusedId = nav.focusedId;
  const activeDescendant =
    focusedId != null ? optionDomId(focusedId) : undefined;

  const searchField = data.enable_search ? (
    <SearchField
      value={query}
      placeholder={data.search_placeholder}
      disabled={widgetDisabled}
      onChange={setQuery}
      onEscape={onEscape}
      inputRef={searchInputRef}
    />
  ) : null;

  return (
    <div
      className={rootClassName}
      data-testid="stListview"
      data-color-scheme={colorScheme}
      data-in-sidebar={inSidebar ? "true" : undefined}
      style={rootStyle}
      ref={rootRef}
    >
      <WidgetLabel
        label={data.label}
        help={data.help}
        labelVisibility={data.label_visibility}
        disabled={widgetDisabled}
        textId={labelId}
      />

      {(data.select_all || (data.enable_search && data.pin_search)) && (
        <div className="listview-header">
          {data.enable_search && data.pin_search && searchField}
          {data.select_all && (
            <SelectAllToggle
              label={isFull ? "Deselect all" : "Select all"}
              onClick={
                isFull
                  ? () => selection.deselectVisible(targetIds)
                  : () => selection.selectAllVisible(targetIds)
              }
              disabled={widgetDisabled || targetIds.length === 0 || !canToggle}
            />
          )}
        </div>
      )}

      <div
        className="listview-body"
        ref={bodyRef}
        onClick={widgetDisabled ? undefined : onBodyClick}
      >
        {data.enable_search && !data.pin_search && searchField}

        <div
          className="listview-listbox"
          ref={listboxRef}
          role="listbox"
          aria-labelledby={labelId}
          tabIndex={widgetDisabled ? -1 : 0}
          aria-multiselectable={
            data.selection_mode === "multi" ? true : undefined
          }
          aria-disabled={widgetDisabled || undefined}
          aria-activedescendant={activeDescendant}
          onKeyDown={widgetDisabled ? undefined : nav.onKeyDown}
        >
          {isEmpty ? (
            <div
              className="listview-placeholder"
              data-testid="listview-placeholder"
            >
              {data.placeholder ?? ""}
            </div>
          ) : (
            renderBlocks.map(({ group, hasHeader, chunks }, index) => {
              // A named block shows its group; the block without a group shows
              // ungrouped_label, its header in a grouped list.
              const name = group.name ?? data.ungrouped_label;
              return (
                <div
                  className="listview-group"
                  // Keyed by POSITION, never by the group name: the name is
                  // user-supplied (Python accepts any str), so any string
                  // sentinel for the block without a group — "__ungrouped__" —
                  // is forgeable, and a real group with that name handed two
                  // sibling blocks ONE key. Duplicate keys corrupt React's
                  // reconciliation: measured fallout was blocks that never
                  // unmount, phantom rows accumulating across filter changes, a
                  // repeated option DOM id (ambiguous aria-activedescendant) and
                  // rows on screen that did not match the active query. The
                  // block without a group has no name at all, so no
                  // name-derived scheme could key it anyway. Blocks hold no
                  // state of their own (collapse state lives in useCollapse,
                  // keyed by group name or null), so a positional key costs
                  // nothing.
                  key={index}
                  // Grouping must be perceivable to AT: a named role="group" is
                  // the listbox structure the ARIA practices prescribe, and it
                  // carries the name that the (aria-hidden) header renders
                  // visually. The one block of a list without groups gets no
                  // group role — it has no header to name it by. Every block
                  // with a header gets the role, so an empty ungrouped_label
                  // (the spec allows "") yields an unnamed group
                  // (aria-label="").
                  role={hasHeader ? "group" : "presentation"}
                  aria-label={hasHeader ? name : undefined}
                >
                  {hasHeader && (
                    <GroupHeader
                      name={name}
                      count={group.items.length}
                      collapsible={data.collapsible_groups}
                      // Passed unconditionally: GroupHeader reads neither prop
                      // in its non-collapsible variant, and isCollapsed is
                      // itself gated on collapsibleGroups, so a
                      // `collapsible_groups ? … : undefined` guard here only
                      // restated that twice. NOT `renderBlocks`' `collapsed`
                      // flag: that one folds in the search override, and the
                      // chevron must keep showing the group's real state while
                      // a query is active.
                      collapsed={collapse.isCollapsed(group.name)}
                      onToggle={() => collapse.toggle(group.name)}
                    />
                  )}
                  {chunks.map((run) => (
                    <div
                      key={run.key}
                      className="listview-chunk"
                      role="none"
                      // The row count the skipped chunk's size estimate
                      // multiplies by (listview.css). Unitless: React sets a
                      // custom property as given.
                      style={
                        {
                          "--listview-chunk-rows": run.items.length,
                        } as CSSProperties
                      }
                    >
                      {run.items.map((item) => (
                        <ListItem
                          key={idKey(item.id)}
                          item={item}
                          domId={optionDomId(item.id)}
                          posInSet={rowPosition.get(item) as number}
                          setSize={setSize}
                          selected={selection.isSelected(item.id)}
                          disabled={Boolean(item.disabled) || widgetDisabled}
                          focused={focusedId === item.id}
                          muted={selection.isMuted(item.id)}
                          onSelect={onItemClick}
                        />
                      ))}
                    </div>
                  ))}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* The add field sits in a footer below the scroll frame, not at the end
          of it: there it read as the last row of the last group, and it
          scrolled out of view with the rows. */}
      {data.accept_new_options && (
        <div className="listview-footer">
          <NewOptionInput disabled={widgetDisabled} onAdd={onAddNewOption} />
        </div>
      )}
    </div>
  );
};

export default Listview;
