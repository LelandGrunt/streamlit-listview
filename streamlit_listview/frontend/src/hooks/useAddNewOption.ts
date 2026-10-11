import { useCallback, useEffect, useState } from "react";
import type { Id, ListviewItem, NewOptionKind } from "../types";
import { idKey, parseNewIntId } from "../utils/ids";
import { foldForMatch } from "../utils/text";
import type { ScrollBlock } from "./useScrollToId";
import type { UseSelectionResult } from "./useSelection";

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

export interface UseAddNewOptionArgs {
  widgetDisabled: boolean;
  /** Every rendered row: the options and the synthetic rows (`useNewOptionRows`). */
  allItems: ListviewItem[];
  selection: UseSelectionResult;
  /** The type a new entry comes back as in Python; the add field refuses what "int" cannot hold. */
  newOptionKind: NewOptionKind | null;
  /** Opens the block a row with `group` renders in (`useGroupCollapse`). */
  expandBlock: (group: string | null) => void;
  /** The DOM scroll for a row (`useScrollToId`). */
  scrollToId: (id: Id, block: ScrollBlock) => void;
  /** Persists a genuinely new entry as a row (`useNewOptionRows`). */
  rememberAdded: (id: Id) => void;
}

/**
 * The handler for the add field (`NewOptionInput`'s `onAdd`): resolves the
 * typed value to an existing row or adds it as a new entry, selects the row,
 * and scrolls it into view. Returns `null` when the value was taken, else the
 * hint that says why it was refused.
 */
export function useAddNewOption({
  widgetDisabled,
  allItems,
  selection,
  newOptionKind,
  expandBlock,
  scrollToId,
  rememberAdded,
}: UseAddNewOptionArgs): (value: string) => string | null {
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

  return useCallback(
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
      const newId = newOptionKind === "int" ? parseNewIntId(value) : value;
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
      rememberAdded(newId);
      selection.add(newId);
      // A new entry has no group, so it joins the block without a group.
      revealRow(newId, null);
      return null;
    },
    [
      widgetDisabled,
      allItems,
      selection,
      newOptionKind,
      rememberAdded,
      revealRow,
    ],
  );
}
