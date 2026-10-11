import { useMemo } from "react";
import type { Id, ListviewItem } from "../types";
import type { RenderGroup } from "../utils/blocks";
import { disabledIdSet } from "../utils/ids";
import type { UseSelectionResult } from "./useSelection";

// Module-level empty results for the select_all=false path, kept for their
// IDENTITY (see NO_NEW_OPTIONS in useNewOptionRows): each is returned from a
// useMemo, and a fresh value per render would invalidate the memos after it.
const NO_TARGET_IDS: Id[] = [];
const NO_DISABLED_IDS: Set<Id> = new Set();

export interface UseSelectAllArgs {
  /** The caller's `select_all`; off, the hook computes nothing. */
  selectAll: boolean;
  widgetDisabled: boolean;
  /** Every row the list renders: the options and the synthetic rows. */
  allItems: ListviewItem[];
  /** The rendered (filtered) blocks, in render order (`useRenderBlocks`). */
  renderGroups: RenderGroup[];
  selection: UseSelectionResult;
}

/** What the select-all toggle shows and does: the props of `SelectAllToggle`. */
export interface UseSelectAllResult {
  /** "Select all", or "Deselect all" while the action is to clear the visible scope. */
  label: string;
  onClick: () => void;
  disabled: boolean;
}

/**
 * The select-all toggle's scope and state: which rows it acts on, whether it
 * reads "Select all" or "Deselect all", and whether it can act at all. The two
 * label literals live here and nowhere else.
 */
export function useSelectAll({
  selectAll,
  widgetDisabled,
  allItems,
  renderGroups,
  selection,
}: UseSelectAllArgs): UseSelectAllResult {
  // Bulk-action scope (D3): the post-filter visible set MINUS disabled rows,
  // in render order. Sourced from renderGroups (NOT navNodes), so rows in
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
    () => (selectAll ? disabledIdSet(allItems) : NO_DISABLED_IDS),
    [selectAll, allItems],
  );

  const targetIds = useMemo(() => {
    if (!selectAll) {
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
  }, [selectAll, disabledIds, renderGroups]);

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

  return {
    label: isFull ? "Deselect all" : "Select all",
    onClick: isFull
      ? () => selection.deselectVisible(targetIds)
      : () => selection.selectAllVisible(targetIds),
    disabled: widgetDisabled || targetIds.length === 0 || !canToggle,
  };
}
