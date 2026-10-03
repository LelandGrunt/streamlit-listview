import type { Id, ListviewItem } from "../types";

/**
 * True iff two items carry the same fields with the same values.
 *
 * Generic over the item's own keys rather than a list of the fields `types.ts`
 * declares today: a field the payload grows later must count as a change, or an
 * edited value would be dropped for the previous object. The items arrive as
 * parsed JSON — plain objects whose values are primitives, none `undefined` — so
 * equal key counts plus `===` on each of one side's keys is the whole
 * comparison. Counted with `for…in` rather than `Object.keys`: this runs for
 * every row on every rerun, and two key arrays per row were pure garbage.
 */
function sameItem(a: ListviewItem, b: ListviewItem): boolean {
  let aCount = 0;
  for (const key in a) {
    if (a[key as keyof ListviewItem] !== b[key as keyof ListviewItem]) {
      return false;
    }
    aCount += 1;
  }
  let bCount = 0;
  for (const _key in b) {
    bCount += 1;
  }
  return aCount === bCount;
}

/**
 * `next`, with every item that is unchanged since `prev` replaced by `prev`'s own
 * object — and `prev` itself when nothing changed at all.
 *
 * Every Streamlit rerun delivers the options as freshly parsed JSON, so without
 * this a rerun that changed nothing still handed the container a new array of
 * new objects: every memo keyed on the items (grouping, the folded search labels,
 * the selection lookups) recomputed, and every memoized row re-rendered because
 * its `item` prop was a new object. Keeping `prev` is what lets that whole chain
 * stand still; keeping the per-item objects is what lets the unchanged rows bail
 * out when only some options changed.
 *
 * Items are matched by id, so a reorder keeps every object. Deliberately by the
 * RAW id, not `idKey`: this asks "is it the same object's content?", not "is it
 * the same row?" — an id spelled differently (`7` vs `"7"`) is one row but a
 * change, because the id is what maps a selection back to the Python option,
 * and a Map already keeps the two spellings apart.
 */
export function reuseUnchangedItems(
  prev: ListviewItem[],
  next: ListviewItem[],
): ListviewItem[] {
  // One positional pass, and no id index unless a row LEFT its position.
  //
  // The common reruns are "nothing changed" and "one option edited, disabled
  // or relabelled in place" — in both every row is still where it was, so its
  // previous object is `prev[j]` and a Map over `prev` has nothing to add. An
  // earlier version bailed out of the positional compare at the first mismatch
  // and fell back to a Map over every previous row plus a second full pass:
  // ~9–11 ms per rerun at 50k rows for a single edit, against ~2.5 ms here.
  // Only a row whose id is not at its old position (a reorder, an insertion
  // or a removal before it) needs the index, built once on first demand.
  const n = next.length;
  const m = prev.length;
  const limit = Math.min(n, m);
  let i = 0;
  while (i < limit && sameItem(prev[i], next[i])) {
    i += 1;
  }
  // Every row of `next` matched positionally — but only an equal LENGTH makes
  // that "unchanged": with `prev` longer, the trailing options were removed and
  // `prev` would keep rendering them.
  if (i === n && n === m) {
    return prev;
  }
  const out: ListviewItem[] = new Array<ListviewItem>(n);
  for (let j = 0; j < i; j++) {
    out[j] = prev[j];
  }
  let prevById: Map<Id, ListviewItem> | null = null;
  for (let j = i; j < n; j++) {
    const item = next[j];
    if (j < m && prev[j].id === item.id) {
      // Still at its position: ids are unique, so prev[j] IS the previous
      // object for this id, and the index cannot know anything more.
      out[j] = sameItem(prev[j], item) ? prev[j] : item;
      continue;
    }
    if (prevById === null) {
      prevById = new Map<Id, ListviewItem>(prev.map((p) => [p.id, p]));
    }
    const old = prevById.get(item.id);
    out[j] = old !== undefined && sameItem(old, item) ? old : item;
  }
  return out;
}

/**
 * `list` split into maximal runs of consecutive elements that share a key, each
 * run tagged with that key. A key that comes back after a different one starts
 * a new run; callers that use the key as a React key therefore pass keys that
 * never decrease along the list. The elements are not copied, so a memoized row
 * keeps bailing out on its unchanged `item`.
 */
export function runsByKey<T>(
  list: T[],
  keyOf: (element: T) => number,
): { key: number; items: T[] }[] {
  const runs: { key: number; items: T[] }[] = [];
  for (const element of list) {
    const key = keyOf(element);
    const last = runs[runs.length - 1];
    if (last !== undefined && last.key === key) {
      last.items.push(element);
    } else {
      runs.push({ key, items: [element] });
    }
  }
  return runs;
}
