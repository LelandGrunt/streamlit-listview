import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  FrontendRendererArgs,
} from "@streamlit/component-v2-lib";
import type { Id, ListviewItem, SelectionMode, ListviewState } from "../types";
import { disabledIdSet, idKey, itemIdByKey, sameIds } from "../utils/ids";

export interface UseSelectionArgs {
  items: ListviewItem[];
  selectionMode: SelectionMode;
  maxSelections: number | null;
  /**
   * Whether unknown selected ids are legitimate (data.accept_new_options).
   * Decides the one policy question reconciliation cannot answer on its own:
   * an id absent from `items` is a typed value with a synthetic row when this is
   * on, and a phantom to drop when it is off.
   */
  acceptNewOptions: boolean;
  /**
   * Ids seeded from Python for the first render (mirrors
   * data.state_selection ?? data.default_ids: the persisted selection when this
   * mount is a remount that kept the Python-side widget state, else `default`).
   * Read once, at mount: neither source ever re-selects (see the hook
   * docstring).
   */
  initialSelection: Id[];
  setStateValue: FrontendRendererArgs<ListviewState>["setStateValue"];
}

export interface UseSelectionResult {
  selection: Id[];
  isSelected: (id: Id) => boolean;
  /** True in multi mode once the selection has reached max_selections (the cap blocks further adds). */
  atCap: boolean;
  /** True only in multi mode at the cap for an item that is not currently selected. */
  isMuted: (id: Id) => boolean;
  /** Apply the click/keyboard selection rules for the given id. Inert for disabled items. */
  toggle: (id: Id) => void;
  /** Add an id without toggling it off. single→replace; multi→append if room & absent. Inert for disabled/at-cap; no-op if already selected. */
  add: (id: Id) => void;
  /** Clear the selection, preserving any disabled (locked) selected ids. */
  clear: () => void;
  /** Bulk-select the given ids in order, skipping disabled/already-selected, capped at max_selections (total). Single atomic commit; skips commit on no-op. */
  selectAllVisible: (ids: Id[]) => void;
  /** Remove the given ids from the selection, preserving all others. Single atomic commit; skips commit on no-op. */
  deselectVisible: (ids: Id[]) => void;
  /** Pure predicate: true iff every id is currently selected. Never commits. */
  allVisibleSelected: (ids: Id[]) => boolean;
}

/**
 * Bring a selection into agreement with the data that describes it.
 *
 * The selection is frontend-owned state that outlives the payload it was made
 * against: a keyed instance keeps it across reruns while `options`,
 * `max_selections` and `selection_mode` are all free to change underneath it.
 * Each of those changes can leave the selection describing data that is no
 * longer there, and they all have the same resolution — re-derive the selection
 * from the current data, in selection order:
 *
 *   * an id whose row-identity key matches an option is replaced by that
 *     option's id, so a typed `"7"` becomes the numeric `7` once the caller
 *     promotes it into `options`: one row, one entry, mapping back to the
 *     option object rather than to a bare string beside it.
 *   * an id absent from `options` is dropped — nothing renders it and
 *     `map_selection` discards it Python-side, so keeping it only lets a phantom
 *     consume a `max_selections` slot. Kept when `accept_new_options` is on,
 *     where an unknown id is a typed value with a synthetic row.
 *   * ids past the cap are dropped, earliest-selected surviving. Single mode is
 *     just a cap of one (Python rejects any other max_selections there), so one
 *     cap covers both the lowered-cap and the multi→single cases.
 *   * a key seen twice collapses to one entry, because it is one row.
 *
 * Deliberately NOT reconciled: a selected id that has become `disabled`. A
 * disabled selection is locked, not removed — `toggle`, `clear` and
 * `deselectVisible` all refuse to drop it, so reconciliation must not either.
 *
 * Returns the input array itself when there is nothing to correct; the caller
 * relies on that identity to decide whether a write-back is needed.
 *
 * Takes the row-identity map and the cap as VALUES rather than deriving them
 * from `items`/`selectionMode`/`maxSelections`: both are shared with the rest of
 * the hook (see `canonicalIds` and `cap` below), so the map is built once per
 * `items` instead of once per reconcile, and there is one definition of the cap.
 */
function reconcileSelection(
  selection: Id[],
  canonicalIds: Map<string, Id>,
  cap: number | null,
  acceptNewOptions: boolean,
): Id[] {
  const next: Id[] = [];
  const seen = new Set<string>();
  for (const id of selection) {
    if (cap != null && next.length >= cap) {
      break;
    }
    const key = idKey(id);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    const canonical = canonicalIds.get(key);
    if (canonical !== undefined) {
      next.push(canonical);
    } else if (acceptNewOptions) {
      next.push(id);
    }
  }
  return sameIds(next, selection) ? selection : next;
}

/**
 * Owns the single piece of widget state: the selected ids (in selection order).
 *
 * Seeds from `initialSelection` at mount only — the persisted Python-side
 * selection (data.state_selection) when this mount is a remount that kept the
 * widget state (a keyed instance moved between containers), else
 * data.default_ids. A later change to either never re-selects — not the value
 * and not the display: the committed value is owned by the V2 default= state,
 * and echoing a new `default` into the display would show a selection that
 * `listview()` does not return. Changing the `key` remains the way to reset
 * the widget: a new key has no persisted state, so its mount seeds from
 * `default` again.
 *
 * Every user-driven change writes through `setStateValue("selection", …)`, which
 * triggers a Streamlit rerun + on_selection_change. So does a reconciliation
 * write-back (see `reconcileSelection`): the rendered selection is always the
 * reconciled one, and committing it is what keeps the value `listview()` returns
 * from disagreeing with what the widget shows.
 */
export function useSelection({
  items,
  selectionMode,
  maxSelections,
  acceptNewOptions,
  initialSelection,
  setStateValue,
}: UseSelectionArgs): UseSelectionResult {
  const disabledIds = useMemo(() => disabledIdSet(items), [items]);

  // Row identity -> the option's own id, for the canonicalization pass. Keyed on
  // `items` alone: reconciliation re-runs on every selection change, and
  // rebuilding this Map there walked every row per click (5000 String() + Map.set
  // at the design target) for data that had not moved.
  const canonicalIds = useMemo(() => itemIdByKey(items), [items]);

  // How many ids the selection may hold. Single mode is a cap of one (Python
  // rejects any other max_selections there), which is what lets ONE notion serve
  // reconciliation, the toggle guard and the bulk select — three places that
  // previously each re-derived their own variant, two of them with no mode clause
  // at all.
  const cap = selectionMode === "single" ? 1 : maxSelections;

  const [committed, setCommitted] = useState<Id[]>(initialSelection);

  // The selection every consumer sees — and that every mutator below extends —
  // is the reconciled one, derived during render so the very first render after
  // a data change already shows the corrected value (a reconciliation deferred
  // to the effect below would render one frame of stale rows: phantom-driven
  // muting, two rows selected in single mode).
  const selection = useMemo(
    () => reconcileSelection(committed, canonicalIds, cap, acceptNewOptions),
    [committed, canonicalIds, cap, acceptNewOptions],
  );

  // Write the correction back, so the value listview() returns matches what is
  // rendered. Gated on reconcileSelection having actually changed something (it
  // returns its input array untouched otherwise), which is what keeps mount
  // quiet: Python validates `default` against the same rules — deduplicated, in
  // options, within max_selections, one id in single mode, and spelled the way
  // the option spells it (`_resolve_default_ids` ships the option's own id for
  // `default="7"` against the int option 7) — so a fresh mount has nothing to
  // correct and fires no value change for a non-user action. The seed can still
  // disagree with the options when it comes from `state_selection`: a persisted
  // "7" typed under accept_new_options, later promoted into `options` as the int
  // 7. That commits once on the remount, which is the point — the alternative
  // is a row that renders selected while listview() returns a bare string
  // beside the option.
  useEffect(() => {
    if (selection === committed) {
      return;
    }
    setCommitted(selection);
    setStateValue("selection", selection);
  }, [selection, committed, setStateValue]);

  // O(1) membership for the per-row isSelected/isMuted lookups, which the
  // container calls once per visible row on every render (Array.includes would
  // make that O(rows × selection)). Keyed by idKey, not by the raw id: "is this
  // row selected?" is a question about row identity.
  const selectionSet = useMemo(
    () => new Set<string>(selection.map(idKey)),
    [selection],
  );

  const isSelected = useCallback(
    (id: Id) => selectionSet.has(idKey(id)),
    [selectionSet],
  );

  // Keeps its own mode clause: the meaning is "adds are blocked", which single
  // mode never has (it replaces rather than appends).
  const atCap =
    selectionMode === "multi" && cap != null && selection.length >= cap;

  const isMuted = useCallback(
    (id: Id) => atCap && !selectionSet.has(idKey(id)),
    [atCap, selectionSet],
  );

  const commit = useCallback(
    (next: Id[]) => {
      setCommitted(next);
      setStateValue("selection", next);
    },
    [setStateValue],
  );

  const toggle = useCallback(
    (id: Id) => {
      if (disabledIds.has(id)) {
        return;
      }
      const key = idKey(id);
      const wasSelected = selectionSet.has(key);
      if (selectionMode === "single") {
        // clicking the current selection clears it; otherwise replace. Single
        // mode holds at most one id (reconciliation guarantees it), so "this row
        // is selected" and "this row IS the selection" are the same test.
        commit(wasSelected ? [] : [id]);
        return;
      }
      // multi
      if (wasSelected) {
        commit(selection.filter((existing) => idKey(existing) !== key));
        return;
      }
      // at the cap: ignore adds. `atCap` IS this test — it carries a
      // `selectionMode === "multi"` clause that holds by construction here.
      if (atCap) {
        return;
      }
      commit([...selection, id]);
    },
    [disabledIds, selectionMode, selection, selectionSet, atCap, commit],
  );

  // `add` IS `toggle` minus the deselect — every other rule (the disabled guard,
  // single-mode replace, the multi-mode cap, appending in selection order) is
  // inherited rather than restated. Deliberately not a second copy of those
  // rules: only the accept_new_options path calls `add`, so a divergence between
  // the two copies would sit in the one no click or keypress exercises.
  const add = useCallback(
    (id: Id) => {
      // The one difference: an id that is already selected stays selected, in
      // either mode. Everything past this point is toggle's decision.
      if (selectionSet.has(idKey(id))) {
        return;
      }
      toggle(id);
    },
    [selectionSet, toggle],
  );

  const clear = useCallback(() => {
    // Keep disabled-selected ids. A disabled item is locked: toggle and the bulk
    // deselect already refuse to remove it, so Escape's clear must not be a
    // back-door that wipes it — that would make a disabled selection
    // inconsistently removable. Clears every non-disabled id, keeps the rest.
    const next = selection.filter((id) => disabledIds.has(id));
    if (next.length === selection.length) {
      return;
    }
    commit(next);
  }, [selection, disabledIds, commit]);

  const selectAllVisible = useCallback(
    (ids: Id[]) => {
      const next = [...selection];
      // A mutable copy of the memoized key set, so the ids appended in this pass
      // are seen too (which is what makes the loop skip duplicates). Copying it
      // rather than re-folding `selection` keeps ONE definition of "the
      // selection's row-identity keys": a second fold here could drift from the
      // one isSelected uses, and Select-all would re-append an already-selected
      // row for reconciliation to silently collapse — a click that did nothing.
      const have = new Set(selectionSet);
      for (const id of ids) {
        if (cap != null && next.length >= cap) {
          break;
        }
        const key = idKey(id);
        if (disabledIds.has(id) || have.has(key)) {
          continue;
        }
        next.push(id);
        have.add(key);
      }
      if (sameIds(next, selection)) {
        return;
      }
      commit(next);
    },
    [selection, selectionSet, cap, disabledIds, commit],
  );

  const deselectVisible = useCallback(
    (ids: Id[]) => {
      const targetKeys = new Set<string>(ids.map(idKey));
      const next = selection.filter((id) => !targetKeys.has(idKey(id)));
      if (next.length === selection.length) {
        return;
      }
      commit(next);
    },
    [selection, commit],
  );

  const allVisibleSelected = useCallback(
    (ids: Id[]) => ids.every((id) => selectionSet.has(idKey(id))),
    [selectionSet],
  );

  return {
    selection,
    isSelected,
    atCap,
    isMuted,
    toggle,
    add,
    clear,
    selectAllVisible,
    deselectVisible,
    allVisibleSelected,
  };
}
