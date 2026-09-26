import { useEffect, useRef } from "react";
import type { Id, ListviewItem } from "../types";
import { idKey, sameIds } from "../utils/ids";

export interface UseScrollToItemArgs {
  /** Resolved default ids from Python (jump targets the FIRST one). */
  defaultIds: Id[];
  /** Current items (including any synthetic new-option rows). */
  items: ListviewItem[];
  /** Force a group open before scrolling (from useCollapse). */
  ensureGroupExpanded: (name: string) => void;
  /** Perform the actual DOM scroll for an id (container-provided). */
  scrollToId: (id: Id) => void;
}

/**
 * Jump-to-default-item. Scrolls the FIRST default id into view on first mount
 * and again whenever `defaultIds` changes between reruns (compared by value).
 * Reruns where `defaultIds` is unchanged never scroll, so the user's scroll
 * position is preserved. If the target sits in a collapsed group it is expanded
 * first. A target absent from `items` is a no-op. Scrolling never changes the
 * selection — it only scrolls.
 */
export function useScrollToItem({
  defaultIds,
  items,
  ensureGroupExpanded,
  scrollToId,
}: UseScrollToItemArgs): void {
  // Sentinel so the very first effect run is always treated as "changed".
  const prevRef = useRef<Id[] | null>(null);

  useEffect(() => {
    const prev = prevRef.current;
    const changed = prev === null || !sameIds(prev, defaultIds);
    prevRef.current = defaultIds;
    if (!changed || defaultIds.length === 0) {
      return;
    }
    const targetId = defaultIds[0];
    // Matched by row identity (idKey), not by raw id: `defaultIds` comes from
    // Python's `default`, the one id list that can spell a row differently than
    // `items` does (accept_new_options permits `default="7"` against an int id
    // 7). A raw comparison called that "not in options" and silently skipped the
    // jump for a row that is on screen — and `scrollToId` finds its DOM node by
    // idKey anyway, so the two agree only this way.
    const target = items.find((it) => idKey(it.id) === idKey(targetId));
    if (!target) {
      return; // not in options → no-op
    }
    if (target.group != null) {
      ensureGroupExpanded(target.group);
    }
    scrollToId(targetId);
    // `items` intentionally excluded from deps: scrolling is triggered by a
    // defaultIds change, not by item churn (re-running on every items change
    // would re-scroll spuriously). We read the latest items via closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultIds, ensureGroupExpanded, scrollToId]);
}
