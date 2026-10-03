import { Fragment, useCallback, useId, useMemo, useRef, useState } from "react";
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
import { useCollapse } from "./hooks/useCollapse";
import { useScrollToItem } from "./hooks/useScrollToItem";
import { useColorScheme } from "./hooks/useColorScheme";
import { disabledIdSet, idKey, itemIdByKey } from "./utils/ids";
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

// A block renders its rows in keyed Fragment chunks, not as one flat run. When
// an update brings many new rows into ONE parent at once — clearing or
// backspacing the search, expanding a big group, options growing on a rerun —
// React places each new row on its own and, for each, searches forward through
// the following siblings for a settled DOM node to insert before
// (`getHostSibling`). Across thousands of new siblings that search is O(k²):
// clearing the search over 50k ungrouped rows took ~7 s (~40 s on a 4×-slowed
// CPU), against ~0.85 s for the same rows grouped 100 to a block.
//
// A row's chunk is fixed by its place in the UNFILTERED list (`chunkOf` below),
// never by the filtered rows: a filter then cannot move a row into another
// chunk, so narrowing keeps every surviving row's DOM node, and the rows a
// broadening filter brings back land either in a chunk that still holds a
// settled survivor — which ends each sibling search within that chunk — or in a
// wholly new chunk, inserted with one search for all of its rows. (Keying a
// chunk by its first FILTERED row instead remounted the survivors on every
// scattered narrowing keystroke: 2–3× slower at 50k.) Fragments add no DOM, so
// rows stay direct children of their block, which scrollToId's sticky-header
// check and the role="group" structure rely on. 100 is the group size that
// measured fine.
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

function groupItems(items: ListviewItem[]): RenderGroup[] {
  const groups: RenderGroup[] = [];
  const indexByName = new Map<string | null, number>();
  for (const item of items) {
    const name = item.group ?? null;
    let idx = indexByName.get(name);
    if (idx === undefined) {
      idx = groups.length;
      indexByName.set(name, idx);
      groups.push({ name, items: [] });
    }
    groups[idx].items.push(item);
  }
  return groups;
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
      (item, i) => idKey(item.id) === idKey(b[i].id) && item.label === b[i].label,
    )
  );
}

/** Where a scrolled-to row lands in the frame (the ScrollLogicalPosition subset we implement). */
type ScrollBlock = "center" | "nearest";

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
 * The id of the row a typed `accept_new_options` value refers to, or undefined
 * when the value is genuinely new.
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
function findExistingId(items: ListviewItem[], value: string): Id | undefined {
  const exact = itemIdByKey(items).get(value);
  if (exact !== undefined) {
    return exact;
  }
  const folded = foldForMatch(value);
  const byLabel = items.find((item) => foldForMatch(item.label) === folded);
  if (byLabel !== undefined) {
    return byLabel.id;
  }
  return items.find((item) => foldForMatch(idKey(item.id)) === folded)?.id;
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
  const items = reuseUnchangedItems(prevItemsRef.current, data.items);
  prevItemsRef.current = items;

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
  const newOptionItems = sameNewOptionRows(
    prevNewOptionItemsRef.current,
    builtNewOptionItems,
  )
    ? prevNewOptionItemsRef.current
    : builtNewOptionItems;
  prevNewOptionItemsRef.current = newOptionItems;

  const allItems = useMemo(
    () => [...items, ...newOptionItems],
    [items, newOptionItems],
  );

  const { visibleItems, isFiltering } = useFilter({ items: allItems, query });

  const groupNames = useMemo(
    () =>
      Array.from(
        new Set(
          items
            .map((i) => i.group)
            .filter((g): g is string => g != null),
        ),
      ),
    [items],
  );
  const collapse = useCollapse({
    collapsibleGroups: data.collapsible_groups,
    collapsedGroups: data.collapsed_groups,
    groupNames,
  });

  // Render blocks, in render order: the caller's options grouped as given, then
  // the accept_new_options rows in a block of their OWN at the very bottom.
  // Grouping the two sets separately is what makes the documented promise true —
  // "entries added via accept_new_options are appended at the bottom": a single
  // pass merges each ungrouped added row into the FIRST ungrouped block, which
  // for a list that mixes grouped and ungrouped options can sit ABOVE the group
  // headers, so an added entry appeared in the middle of the list.
  const renderGroups = useMemo(() => {
    if (newOptionItems.length === 0) {
      return groupItems(visibleItems);
    }
    const addedKeys = new Set(newOptionItems.map((it) => idKey(it.id)));
    const known: ListviewItem[] = [];
    const added: ListviewItem[] = [];
    for (const item of visibleItems) {
      (addedKeys.has(idKey(item.id)) ? added : known).push(item);
    }
    // groupItems([]) is [], so a fully filtered-out set adds no empty block.
    return [...groupItems(known), ...groupItems(added)];
  }, [visibleItems, newOptionItems]);

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

  // Each block plus whether it renders collapsed (a group is only visually
  // collapsed while no search is active — search overrides collapse) and the
  // chunks its rows render in. Computed once so the render below and
  // focusableItems cannot disagree, and so the chunks are split only when the
  // blocks change rather than on every render (each arrow key, each click).
  // A block keeps the order of `allItems`, so its chunk numbers never decrease
  // and each one is a single run — unique as a React key within the block.
  const renderBlocks = useMemo(
    () =>
      renderGroups.map((group) => {
        const collapsed =
          group.name != null &&
          !isFiltering &&
          collapse.isCollapsed(group.name);
        return {
          group,
          collapsed,
          chunks: collapsed
            ? []
            : runsByKey(group.items, (item) => chunkOf.get(item) as number),
        };
      }),
    [renderGroups, isFiltering, collapse, chunkOf],
  );

  // Items that can take keyboard focus: the rendered blocks flattened, minus
  // collapsed ones. Derived from the BLOCKS rather than from visibleItems so
  // arrow-key order is exactly the order the rows appear on screen — grouping
  // reorders items whenever a group's options are not contiguous in `options`,
  // and the added-options block always renders last.
  const focusableItems = useMemo(
    () =>
      renderBlocks.flatMap(({ group, collapsed }) => (collapsed ? [] : group.items)),
    [renderBlocks],
  );

  // Bulk-action scope (D3): the post-filter visible set MINUS disabled rows,
  // in list order. Sourced from visibleItems (NOT focusableItems), so rows in
  // collapsed groups stay in scope (collapse is visual, not a filter). Because
  // visibleItems derives from allItems, accept_new_options synthetic rows are
  // included automatically.
  //
  // Gated on select_all, because the toggle is the ONLY consumer of this scope
  // and of everything derived from it (allVisibleSelected / someVisibleSelected /
  // isFull / canToggle all read targetIds and nothing else reads them). With the
  // gate off the empty scope makes those short-circuit, so the whole chain costs
  // nothing instead of two n-sized allocations plus four passes over every
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
    return visibleItems.filter((it) => !disabledIds.has(it.id)).map((it) => it.id);
  }, [data.select_all, disabledIds, visibleItems]);

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
  // click. Forward it to the listbox. Only a click on the body ITSELF: rows, the
  // search field and the add-option row are children that already focus their
  // own target, and taking it would pull the caret out of an input.
  // preventScroll: the listbox is taller than the frame it scrolls in.
  const onBodyClick = useCallback((event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      (listboxRef.current as HTMLDivElement).focus({ preventScroll: true });
    }
  }, []);

  // DOM scroll for a row id, shared by jump-to-default and keyboard navigation.
  // rAF so an auto-expand (or focus-move) re-render commits before we
  // measure/scroll.
  //
  // Scrolls THE LIST BODY ONLY, by container-relative scrollTop math.
  // Element.scrollIntoView() would be shorter but it scrolls every scrollable
  // ancestor, including the Streamlit page: a listview with `default=` below the
  // fold yanked the host page away from whatever the user was reading, on first
  // render and on every rerun that changed `default_ids` by value.
  const scrollToId = useCallback(
    (id: Id, block: ScrollBlock = "center") => {
      requestAnimationFrame(() => {
        const body = bodyRef.current;
        // Unreachable in practice: the body renders unconditionally, and this
        // callback only runs after a commit. It guards an unmount racing the rAF.
        /* v8 ignore next 3 */
        if (!body) {
          return;
        }
        const node = findRowNode(body, optionDomId(id));
        if (node === null) {
          return; // row not rendered (e.g. filtered out) → nothing to scroll to
        }
        const frame = body.clientHeight;
        const rowBox = node.getBoundingClientRect();
        // The row's offset inside the scrolled content: its position relative to
        // the frame, plus however far the frame is already scrolled. scrollTop is
        // measured from the padding-box edge while the rect is the border box, so
        // the body's top border (clientTop) comes out — otherwise every "nearest"
        // scroll landed one border-width off, clipping the row.
        const top =
          body.scrollTop + rowBox.top - (body.getBoundingClientRect().top + body.clientTop);
        if (block === "center") {
          // Out-of-range assignments are clamped by the browser, so the first and
          // last rows need no special casing.
          body.scrollTop = top - (frame - rowBox.height) / 2;
        } else {
          // A grouped row's own header is position: sticky; top: 0 — it paints over
          // the top of the scrollport, so the band where a row is actually visible
          // starts BELOW it. Bringing a row's top edge to the frame's top edge
          // parked it exactly under that header: ArrowUp / Home focused a row the
          // user could not see, and Enter selected it. A row always renders inside
          // a group block whose first child is either that header or a row, so this
          // is a fixed class-name check with none of the id-escaping hazards of the
          // row lookup; an ungrouped block has no header and keeps the frame edge.
          const first = (node.parentElement as HTMLElement).firstElementChild as Element;
          const stickyHeight = first.classList.contains("listview-group-header")
            ? first.getBoundingClientRect().height
            : 0;
          if (top - stickyHeight < body.scrollTop) {
            body.scrollTop = top - stickyHeight; // above the visible band → top edge in, under the header
          } else if (top + rowBox.height > body.scrollTop + frame) {
            body.scrollTop = top + rowBox.height - frame; // below → bottom edge in
          }
        }
      });
    },
    [],
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
  itemClickRef.current = {
    widgetDisabled,
    setFocusToId: nav.setFocusToId,
    toggle: selection.toggle,
  };
  const onItemClick = useCallback((id: Id) => {
    const { widgetDisabled: disabled, setFocusToId, toggle } =
      itemClickRef.current;
    // Defense-in-depth: ListItem already blocks clicks while disabled, so this
    // never fires then.
    /* v8 ignore next 3 */
    if (disabled) {
      return;
    }
    setFocusToId(id);
    toggle(id);
  }, []);

  const onAddNewOption = useCallback(
    (value: string) => {
      // Defense-in-depth: NewOptionInput is disabled then, so this never fires.
      /* v8 ignore next 3 */
      if (widgetDisabled) {
        return;
      }
      // Resolve a typed value against ALL rendered rows (known options + synthetic
      // ones) by row identity AND by visible label, so it matches an existing row
      // whether that row is a known option or an already-added / selected
      // synthetic one. Resolved here in the cold add path, not as a per-render
      // memo over every row.
      const existingId = findExistingId(allItems, value);
      if (existingId !== undefined) {
        // Matches an existing option (a numeric id typed as text, or the label the
        // user can actually see): select that option rather than spawn a
        // duplicate row.
        selection.add(existingId);
        return;
      }
      // Genuinely new. In multi mode at the cap the add would be rejected by
      // useSelection, so do NOT persist a phantom row that was never actually
      // selected (and that the user then cannot easily remove). Single mode
      // always replaces, so atCap is never set there.
      if (selection.atCap) {
        return;
      }
      // Remember it so it persists as a row after deselection, then select it.
      setAddedItems((prev) => {
        // Defence in depth, unreachable in practice: once a value is in
        // addedItems it is also in allItems, so findExistingId above already
        // returned. It only guards a re-entrant add that closed over a stale
        // allItems within a single React batch. Marked as a guard (condition +
        // early return) so the append below stays measured.
        /* v8 ignore next 3 */
        if (prev.some((it) => it.id === value)) {
          return prev;
        }
        return [...prev, newOptionRow(value)];
      });
      selection.add(value);
    },
    [widgetDisabled, allItems, selection],
  );

  useScrollToItem({
    defaultIds: data.default_ids,
    items: allItems,
    ensureGroupExpanded: collapse.expand,
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
  const activeDescendant = focusedId != null ? optionDomId(focusedId) : undefined;

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
          aria-multiselectable={data.selection_mode === "multi" ? true : undefined}
          aria-disabled={widgetDisabled || undefined}
          aria-activedescendant={activeDescendant}
          onKeyDown={widgetDisabled ? undefined : nav.onKeyDown}
        >
          {isEmpty ? (
            <div className="listview-placeholder" data-testid="listview-placeholder">
              {data.placeholder ?? ""}
            </div>
          ) : (
            renderBlocks.map(({ group, chunks }, index) => (
              <div
                className="listview-group"
                // Keyed by POSITION, never by the group name: the name is
                // user-supplied (Python accepts any str), so any string sentinel
                // for the ungrouped block — "__ungrouped__" — is forgeable, and a
                // real group with that name handed two sibling blocks ONE key.
                // Duplicate keys corrupt React's reconciliation: measured fallout
                // was blocks that never unmount, phantom rows accumulating across
                // filter changes, a repeated option DOM id (ambiguous
                // aria-activedescendant) and rows on screen that did not match the
                // active query. The added-options block is a second ungrouped
                // block, so no name-derived scheme could be unique anyway. Blocks
                // hold no state of their own (collapse state lives in useCollapse,
                // keyed by name), so a positional key costs nothing.
                key={index}
                // Grouping must be perceivable to AT: a named role="group" is the
                // listbox structure the ARIA practices prescribe, and it carries
                // the group name that the (aria-hidden) header renders visually.
                // The ungrouped block gets no group role — there is no name to
                // give it, and an unnamed group is worse than none.
                role={group.name != null ? "group" : "presentation"}
                aria-label={group.name ?? undefined}
              >
                {group.name != null && (
                  <GroupHeader
                    name={group.name}
                    count={group.items.length}
                    collapsible={data.collapsible_groups}
                    // Passed unconditionally: GroupHeader reads neither prop in
                    // its non-collapsible variant, and isCollapsed is itself
                    // gated on collapsibleGroups, so a `collapsible_groups ?
                    // … : undefined` guard here only restated that twice.
                    // NOT `renderBlocks`' `collapsed` flag: that one folds in the
                    // search override, and the chevron must keep showing the
                    // group's real state while a query is active.
                    collapsed={collapse.isCollapsed(group.name)}
                    onToggle={() => collapse.toggle(group.name as string)}
                  />
                )}
                {chunks.map((run) => (
                  <Fragment key={run.key}>
                    {run.items.map((item) => (
                      <ListItem
                        key={idKey(item.id)}
                        item={item}
                        domId={optionDomId(item.id)}
                        selected={selection.isSelected(item.id)}
                        disabled={Boolean(item.disabled) || widgetDisabled}
                        focused={focusedId === item.id}
                        muted={selection.isMuted(item.id)}
                        onSelect={onItemClick}
                      />
                    ))}
                  </Fragment>
                ))}
              </div>
            ))
          )}
        </div>

        {data.accept_new_options && (
          <NewOptionInput disabled={widgetDisabled} onAdd={onAddNewOption} />
        )}
      </div>
    </div>
  );
};

export default Listview;
