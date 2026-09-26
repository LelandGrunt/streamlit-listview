import { useCallback, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { Id, ListviewItem } from "../types";

export interface UseKeyboardNavArgs {
  /** Visible items in render order; disabled items are skipped for focus. */
  items: ListviewItem[];
  /** Invoked when Enter/Space selects the focused item. */
  onSelect: (id: Id) => void;
  /** "/" pressed in the listbox (e.g. focus the search field). Optional. */
  onSlash?: () => void;
  /** Escape pressed in the listbox (e.g. clear search then selection). Optional. */
  onEscape?: () => void;
  /**
   * Scroll a row into view (container-provided, the same helper the
   * jump-to-default path uses). Called ONLY when a key moves focus — never for
   * `setFocusToId`, so clicking a row cannot jog the list. Optional.
   */
  scrollToId?: (id: Id) => void;
}

export interface UseKeyboardNavResult {
  /**
   * Id of the focused item (for aria-activedescendant and the row's `focused`
   * prop), or null when nothing focusable is focused.
   */
  focusedId: Id | null;
  /**
   * Attach to the listbox element itself. Keydowns that bubbled up from a focused
   * descendant control (the collapsible group-header button) are left alone.
   */
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
  /** Programmatically set focus to an item id (e.g. on click). No-op if not focusable. */
  setFocusToId: (id: Id) => void;
}

/**
 * Roving-focus keyboard navigation for the listbox.
 *
 * Arrow keys move focus, Home/End jump to the ends, Enter/Space select the
 * focused item via `onSelect`. Disabled items can never receive focus.
 *
 * Focus is stored as the focused row's **id**, and the position in `focusable`
 * is derived from it while rendering. Storing an index instead would be wrong
 * for exactly one render whenever the focusable subset shrinks or reorders
 * (filtering, a collapse toggle, a rerun that changed `options`): the index
 * still points at the slot the old item occupied, so that committed render puts
 * the ring — and what Enter would select — on a row the user never focused, and
 * re-resolving the index in a post-paint effect corrects it one render too late.
 *
 * An id whose row is no longer focusable reads as "nothing focused" *without*
 * being cleared: the ring disappears while a search hides the row and comes back
 * on the row the user actually left it on once the query is backed out. While
 * the row is hidden, arrows behave as if nothing were focused (ArrowDown starts
 * at the top).
 */
export function useKeyboardNav({
  items,
  onSelect,
  onSlash,
  onEscape,
  scrollToId,
}: UseKeyboardNavArgs): UseKeyboardNavResult {
  const focusable = useMemo(
    () => items.filter((item) => !item.disabled),
    [items],
  );

  const [focusedIdState, setFocusedIdState] = useState<Id | null>(null);
  // Synchronous mirror of the state, so a key handler resolves the CURRENT
  // focus even for keydowns React batches into a single render (reading state
  // would give every key in the batch the same pre-batch position).
  const focusedIdRef = useRef<Id | null>(null);

  // Both writers go through here, so the ref and the state can never drift.
  const setFocused = useCallback((id: Id) => {
    focusedIdRef.current = id;
    setFocusedIdState(id);
  }, []);

  // Raw id keys (not `idKey`) are exact here: every focus id originates from
  // `items` itself — either read off a row or handed to `setFocusToId` as that
  // row's own id — so it is never a foreign spelling of the same key. Map lookup
  // is SameValueZero, which agrees with the `===` this replaced for every id the
  // boundary admits (`7` and `"7"` stay distinct; Python rejects float ids, so
  // NaN — the one case the two differ on — cannot occur).
  //
  // A Map rather than a scan because `indexOfId` runs in the render body: with
  // nothing focused, the findIndex it replaces compared every row and returned
  // -1 on EVERY render (twice per click, once per keystroke), and each arrow key
  // paid two more scans — ~5000 comparisons apiece at the design target. The
  // build is O(rows) at the same cadence as the `focusable` filter above it.
  const indexByRawId = useMemo(
    () => new Map<Id, number>(focusable.map((item, index) => [item.id, index])),
    [focusable],
  );

  const indexOfId = useCallback(
    (id: Id | null): number => (id === null ? -1 : (indexByRawId.get(id) ?? -1)),
    [indexByRawId],
  );

  const focusedId = indexOfId(focusedIdState) >= 0 ? focusedIdState : null;

  const setFocusToId = useCallback(
    (id: Id) => {
      if (indexOfId(id) >= 0) {
        setFocused(id);
      }
    },
    [indexOfId, setFocused],
  );

  // A key-driven focus move must also scroll the row into view: focus here is
  // virtual (aria-activedescendant), and browsers only auto-scroll for REAL DOM
  // focus, so without this the ring silently leaves the scroll frame after a
  // few ArrowDowns (End leaves it a whole list away) and Enter then selects a
  // row the user cannot see.
  const moveFocusTo = useCallback(
    (index: number) => {
      const id = focusable[index].id;
      setFocused(id);
      scrollToId?.(id);
    },
    [focusable, setFocused, scrollToId],
  );

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      // Keys aimed at a focused descendant control belong to that control. This
      // handler sits on an ancestor of the collapsible group-header <button>, so
      // its keydowns bubble through here: without this guard Enter/Space on a
      // header was preventDefault()ed (the button never activated, the group
      // never collapsed) *and* toggled the unrelated roving-focus row. Rows are
      // not focusable, so a target other than the listbox is always such a
      // control — which deliberately makes Escape and "/" listbox-only too:
      // Escape must not clear the selection while a header button has focus.
      if (event.target !== event.currentTarget) {
        return;
      }
      if (event.key === "/") {
        if (onSlash) {
          event.preventDefault();
          onSlash();
        }
        return;
      }
      if (event.key === "Escape") {
        if (onEscape) {
          event.preventDefault();
          onEscape();
        }
        return;
      }
      const last = focusable.length - 1;
      if (last < 0) {
        return;
      }
      // -1 when nothing is focused *or* the focused row is currently hidden.
      const current = indexOfId(focusedIdRef.current);
      switch (event.key) {
        case "ArrowDown": {
          event.preventDefault();
          moveFocusTo(current < 0 ? 0 : Math.min(current + 1, last));
          break;
        }
        case "ArrowUp": {
          event.preventDefault();
          moveFocusTo(current < 0 ? last : Math.max(current - 1, 0));
          break;
        }
        case "Home": {
          event.preventDefault();
          moveFocusTo(0);
          break;
        }
        case "End": {
          event.preventDefault();
          moveFocusTo(last);
          break;
        }
        case "Enter":
        case " ":
        case "Spacebar": {
          event.preventDefault();
          if (current >= 0) {
            onSelect(focusable[current].id);
          }
          break;
        }
        default:
          break;
      }
    },
    [focusable, indexOfId, moveFocusTo, onSelect, onSlash, onEscape],
  );

  return { focusedId, onKeyDown, setFocusToId };
}
