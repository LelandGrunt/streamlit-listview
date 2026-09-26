import { useMemo } from "react";
import type { ListviewItem } from "../types";
import { foldForMatch } from "../utils/text";

export interface UseFilterArgs {
  items: ListviewItem[];
  /** Raw search text; trimmed + lowercased before matching. */
  query: string;
}

export interface UseFilterResult {
  /** Items whose label matches the query (all items when not filtering). */
  visibleItems: ListviewItem[];
  /** True when a non-empty query is active. */
  isFiltering: boolean;
}

/**
 * Case-insensitive substring filter over item labels, folding both sides through
 * the shared `foldForMatch` (see utils/text) so "findable by searching" and
 * "already in the list" — the accept_new_options check — cannot drift apart. An
 * empty or whitespace-only query is "not filtering" and returns every item
 * unchanged (referential identity preserved so downstream memoization stays
 * stable).
 */
export function useFilter({ items, query }: UseFilterArgs): UseFilterResult {
  const normalized = foldForMatch(query);
  const isFiltering = normalized.length > 0;

  // The folded labels, parallel to `items` by index — or null while no query is
  // active, which is also the "not filtering" signal for the memo below (one
  // source of truth, so the two cannot disagree about whether to filter).
  //
  // The fold IS the cost of the filter: it allocates a lowercased copy of every
  // label (plus a ß replace) and does not depend on the query at all, so folding
  // inside the filter re-folded every label on every keystroke — and again on
  // every selection click taken while a query was active, since a click can give
  // `items` a new identity. At the 5000-row design target a 5-character query
  // paid ~25,000 label folds where 5,000 suffice. Keyed on `items` only, so
  // typing narrows the query against labels folded once.
  //
  // Deliberately null rather than an eagerly-built array: a list with search off
  // (or an empty search box) is the common case, and it must not start folding
  // labels it will never match against.
  const foldedLabels = useMemo(
    () => (isFiltering ? items.map((item) => foldForMatch(item.label)) : null),
    [items, isFiltering],
  );

  const visibleItems = useMemo(() => {
    if (foldedLabels === null) {
      return items;
    }
    return items.filter((_item, index) => foldedLabels[index].includes(normalized));
  }, [items, foldedLabels, normalized]);

  return { visibleItems, isFiltering };
}
