import { useCallback, useMemo, useRef, useState } from "react";
import type { Id, ListviewItem } from "../types";
import { elementAt } from "../utils/arrays";
import { idKey, itemIdByKey } from "../utils/ids";

// Module-level empty results for the "nothing to compute" paths below. Safe to
// share because every consumer only reads them: the render spreads, filters and
// maps them, and no caller mutates the array or the map.
//
// They exist for their IDENTITY, not to save an allocation: each is returned from
// a useMemo, and a fresh `[]` per render would count as a change and invalidate
// every memo downstream of it. `NO_NEW_OPTIONS` is the load-bearing one —
// newOptionItems has to depend on the live selection, so with accept_new_options
// OFF (the common case) a fresh `[]` gave `allItems` a new identity on every
// click, re-running the filter, the folded labels, the grouping and the scope
// passes over every row for a list that cannot have added rows at all.
const NO_NEW_OPTIONS: ListviewItem[] = [];
const EMPTY_ID_MAP: Map<string, Id> = new Map();

/**
 * The synthetic row an id absent from `options` renders as, under
 * accept_new_options: its own text as the label, because there is no option
 * object to take one from.
 *
 * ONE definition, because such a row can arrive by three routes — seeded from
 * `default`, found selected-but-unknown, or just typed — and a rule applied to
 * one route only would give a single entry two different labels depending on how
 * it got there. Labelling via `idKey` rather than a second `String(id)` for the
 * same reason row identity funnels through it (see utils/ids). Python builds
 * the same row in `_options._new_entry`; change both copies together.
 */
function newOptionRow(id: Id): ListviewItem {
  return { id, label: idKey(id) };
}

/**
 * Element-wise equality for two synthetic-row lists: the same rows (by `idKey`)
 * carrying the same labels. The rows are freshly allocated per rebuild (see
 * `newOptionRow`), so object identity cannot answer this; the hook uses it to
 * keep the previous ARRAY's identity when a rebuild changed nothing.
 */
function sameNewOptionRows(a: ListviewItem[], b: ListviewItem[]): boolean {
  return (
    a.length === b.length &&
    a.every((item, i) => {
      const other = elementAt(b, i);
      return idKey(item.id) === idKey(other.id) && item.label === other.label;
    })
  );
}

export interface UseNewOptionRowsArgs {
  /** The caller's options: `Listview`'s `items`, never `data.items`. */
  items: ListviewItem[];
  acceptNewOptions: boolean;
  /**
   * What the mount seeds the selection from (the persisted selection, else
   * `default`). Read at mount only, like the selection seed itself.
   */
  seedSelection: Id[];
  /** The live selection (`useSelection`'s `selection`). */
  selection: Id[];
}

export interface UseNewOptionRowsResult {
  /**
   * The synthetic rows for the ids absent from `items`, in render order:
   * the added options, then any other selected-but-unknown id. Empty unless
   * accept_new_options is on.
   */
  newOptionItems: ListviewItem[];
  /** Every row the list renders: `items`, then `newOptionItems`. */
  allItems: ListviewItem[];
  /**
   * Persists a genuinely new entry as a row, so it stays in the list after it
   * is deselected. Stable identity.
   */
  rememberAdded: (id: Id) => void;
}

/**
 * The rows that `accept_new_options` adds to the caller's options, and the
 * list of every row the list renders.
 */
export function useNewOptionRows({
  items,
  acceptNewOptions,
  seedSelection,
  selection,
}: UseNewOptionRowsArgs): UseNewOptionRowsResult {
  // Options the user added via accept_new_options, persisted in frontend state
  // so an added option stays in the list (as a re-selectable row) after it is
  // deselected — in single mode, picking another option would otherwise drop it
  // entirely. Seeded with any unknown ids in the mount's seed selection: a
  // persisted selection carries the values the user typed before a remount, and
  // Python permits unknown ids in `default` when accept_new_options is on. Like
  // other UI-only state this survives reruns when the instance is keyed; a
  // keyless instance remounts and re-seeds.
  const [addedItems, setAddedItems] = useState<ListviewItem[]>(() => {
    if (!acceptNewOptions) {
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
    () => (acceptNewOptions ? itemIdByKey(items) : EMPTY_ID_MAP),
    [acceptNewOptions, items],
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
    if (!acceptNewOptions) {
      return NO_NEW_OPTIONS;
    }
    const seen = new Set<string>();
    const out: ListviewItem[] = [];
    // Persisted added options first (keep their typed label), then any other
    // selected-but-unknown id.
    const candidates: ListviewItem[] = [
      ...addedItems,
      ...selection.map((id) => newOptionRow(id)),
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
  }, [acceptNewOptions, knownIds, addedItems, selection]);

  // The non-empty counterpart of NO_NEW_OPTIONS above: the memo depends on the
  // live selection, so once one synthetic row exists every click rebuilt an
  // equal-but-new array and invalidated that same chain per click. Same
  // resolution as reconcileSelection (useSelection): hand back the previous
  // value when the rebuild is element-wise identical. A deliberate render-body
  // ref write, like the `items` reuse in Listview.
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

  // Remembers a new entry so it persists as a row after deselection.
  const rememberAdded = useCallback((newId: Id) => {
    setAddedItems((prev) => {
      // Defence in depth, unreachable in practice: once a value is in
      // addedItems it is also in allItems, so findExistingRow (useAddNewOption)
      // already returned. It only guards a re-entrant add that closed over a
      // stale allItems within a single React batch. Marked as a guard
      // (condition + early return) so the append below stays measured.
      /* v8 ignore next 3 */
      if (prev.some((it) => it.id === newId)) {
        return prev;
      }
      return [...prev, newOptionRow(newId)];
    });
  }, []);

  return { newOptionItems, allItems, rememberAdded };
}
