import type { Id, ListviewItem } from "../types";

/**
 * True iff two id lists are element-wise equal (same length, same order).
 * Shared so the by-value list comparison has a single definition instead of
 * being re-derived inline in each hook.
 */
export function sameIds(a: Id[], b: Id[]): boolean {
  return a.length === b.length && a.every((id, i) => id === b[i]);
}

/**
 * The row-identity key of an id: JavaScript `String(id)`.
 *
 * Rows are keyed by this string everywhere it is observable — React keys, DOM
 * ids, `aria-activedescendant`, the jump-to-default scroll lookup — so it, not
 * the raw id, is what "the same row" means. The distinction is load-bearing:
 * a numeric option id `7` and the `"7"` a user typed into `accept_new_options`
 * are ONE row, yet `7 === "7"` is false. Python's `normalize_options` rejects
 * options that collide after `str()` precisely so that a key identifies exactly
 * one row, which makes this a total identity — but only if every "same row?"
 * comparison actually goes through it instead of comparing raw ids.
 */
export function idKey(id: Id): string {
  return String(id);
}

/**
 * Map from each item's row-identity key (see `idKey`) to its *canonical* id —
 * the id as `items` spells it, which is the one that maps back to a Python
 * option. Doubles as the "is this a known option?" lookup (`.has(key)`).
 */
export function itemIdByKey(items: ListviewItem[]): Map<string, Id> {
  const byKey = new Map<string, Id>();
  for (const item of items) {
    byKey.set(idKey(item.id), item.id);
  }
  return byKey;
}

/**
 * The set of ids of the disabled items. Used for O(1) disabled-membership
 * checks (selection guards, bulk-action scope exclusion).
 *
 * Keyed by the RAW id, not by `idKey`: every caller looks these up with an id
 * taken from the same item list the set was built from, so the raw comparison is
 * exact there. (The selection is the one place ids of a foreign type can show
 * up, and it is reconciled onto the item ids before any disabled check sees it.)
 */
export function disabledIdSet(items: ListviewItem[]): Set<Id> {
  const set = new Set<Id>();
  for (const item of items) {
    if (item.disabled) {
      set.add(item.id);
    }
  }
  return set;
}
