import { useCallback, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { Id, ListviewItem } from "../types";
import { elementAt } from "../utils/arrays";
import { idKey } from "../utils/ids";
import type { GroupKey } from "./useCollapse";

/**
 * A group header as a navigation node. With collapsible_groups the list is a
 * tree (WAI-ARIA Tree View): each header is a node of its own, placed before
 * its rows, and the arrow keys reach it like a row. A class, so `instanceof`
 * tells a header from a row; a field on a plain object could clash with a key
 * of the caller's option.
 */
export class GroupNode {
  /** The group's name, or null for the block without a group. */
  readonly group: GroupKey;
  /** The group's own state (its chevron), not whether a search shows its rows. */
  readonly expanded: boolean;

  constructor(group: GroupKey, expanded: boolean) {
    this.group = group;
    this.expanded = expanded;
  }
}

/** A row, or in a tree a group header, in the order the list renders them. */
export type NavNode = ListviewItem | GroupNode;

export interface UseKeyboardNavArgs {
  /**
   * The visible nodes in render order: the rows, and in a tree the group
   * headers, each before its rows. Disabled rows are skipped for focus. A
   * row's header is the closest header above it.
   */
  nodes: NavNode[];
  /** Invoked when Enter/Space selects the focused row. */
  onSelect: (id: Id) => void;
  /**
   * Opens or closes a group: Enter/Space on its header, ArrowRight on a closed
   * header, ArrowLeft on an open one. Optional.
   */
  onToggleGroup?: ((group: GroupKey) => void) | undefined;
  /** "/" pressed in the listbox (e.g. focus the search field). Optional. */
  onSlash?: (() => void) | undefined;
  /** Escape pressed in the listbox (e.g. clear search then selection). Optional. */
  onEscape?: (() => void) | undefined;
  /**
   * Scroll a row into view (container-provided, the same helper the
   * jump-to-default path uses). Called ONLY when a key moves focus — never for
   * `setFocusToId`, so clicking a row cannot jog the list. Optional.
   */
  scrollToId?: ((id: Id) => void) | undefined;
  /** Scroll a header into view, under the same rule as `scrollToId`. Optional. */
  scrollToGroup?: ((group: GroupKey) => void) | undefined;
}

export interface UseKeyboardNavResult {
  /**
   * Id of the focused row (for aria-activedescendant and the row's `focused`
   * prop), or null when no row is focused.
   */
  focusedId: Id | null;
  /**
   * The group whose header is focused, or undefined when no header is. `null`
   * is a group: the block without a group.
   */
  focusedGroup: GroupKey | undefined;
  /** Attach to the listbox (or tree) element itself. */
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
  /** Programmatically set focus to a row id (e.g. on click). No-op if not focusable. */
  setFocusToId: (id: Id) => void;
  /** Programmatically set focus to a group's header (e.g. on click). No-op if it has none. */
  setFocusToGroup: (group: GroupKey) => void;
}

/**
 * What a key does: move the focus to a node, select a row, open or close a
 * group, or nothing at all (Enter with nothing focused; the key is still the
 * list's).
 */
type Action =
  | { type: "move"; index: number }
  | { type: "select"; id: Id }
  | { type: "toggle"; group: GroupKey }
  | { type: "none" };

/** The focus: a row id, or a group whose header is focused. */
interface Focus {
  row: Id | null;
  group: GroupKey | undefined;
}

const ACTIVATE_KEYS = new Set(["Enter", " ", "Spacebar"]);

/** Where a focus-moving key puts the focus, or undefined for any other key. */
function moveIndex(
  key: string,
  current: number,
  last: number,
): number | undefined {
  switch (key) {
    case "ArrowDown":
      return current < 0 ? 0 : Math.min(current + 1, last);
    case "ArrowUp":
      return current < 0 ? last : Math.max(current - 1, 0);
    case "Home":
      return 0;
    case "End":
      return last;
    default:
      return undefined;
  }
}

/** Enter/Space: select a row, open or close a header. */
function activate(node: NavNode | undefined): Action {
  if (node === undefined) {
    return { type: "none" };
  }
  return node instanceof GroupNode
    ? { type: "toggle", group: node.group }
    : { type: "select", id: node.id };
}

/** ArrowRight: open a closed header; on an open one, step to its first row. */
function arrowRight(nodes: NavNode[], current: number): Action | undefined {
  const node = elementAt(nodes, current);
  if (!(node instanceof GroupNode)) {
    return undefined;
  }
  if (!node.expanded) {
    return { type: "toggle", group: node.group };
  }
  // A group without a focusable row is followed by the next header, or by
  // nothing.
  const next = nodes[current + 1];
  return next === undefined || next instanceof GroupNode
    ? undefined
    : { type: "move", index: current + 1 };
}

/** ArrowLeft: close an open header; on a row, step to its header. */
function arrowLeft(nodes: NavNode[], current: number): Action | undefined {
  const node = elementAt(nodes, current);
  if (node instanceof GroupNode) {
    return node.expanded ? { type: "toggle", group: node.group } : undefined;
  }
  // A list without headers walks to the top and finds none.
  for (let index = current - 1; index >= 0; index -= 1) {
    if (elementAt(nodes, index) instanceof GroupNode) {
      return { type: "move", index };
    }
  }
  return undefined;
}

/** What `key` does with the focus at `current`; undefined leaves the key alone. */
function actionFor(
  key: string,
  nodes: NavNode[],
  current: number,
): Action | undefined {
  const index = moveIndex(key, current, nodes.length - 1);
  if (index !== undefined) {
    return { type: "move", index };
  }
  if (ACTIVATE_KEYS.has(key)) {
    return activate(current < 0 ? undefined : elementAt(nodes, current));
  }
  if (current < 0) {
    return undefined;
  }
  if (key === "ArrowRight") {
    return arrowRight(nodes, current);
  }
  return key === "ArrowLeft" ? arrowLeft(nodes, current) : undefined;
}

/**
 * Roving-focus keyboard navigation for the listbox, and for the tree that
 * collapsible groups make of it.
 *
 * Arrow keys move focus, Home/End jump to the ends, Enter/Space select the
 * focused row. Disabled rows can never receive focus. In a tree the headers
 * are nodes too: ArrowRight opens a closed header or steps into an open one,
 * ArrowLeft closes an open header or steps from a row to its header, and
 * Enter/Space on a header opens or closes it (the WAI-ARIA Tree View keys).
 *
 * Focus is stored as the focused row's **id**, or the focused header's group,
 * and the position in `focusable` is derived from it while rendering. Storing
 * an index instead would be wrong for exactly one render whenever the focusable
 * subset shrinks or reorders (filtering, a collapse toggle, a rerun that changed
 * `options`): the index still points at the slot the old node occupied, so that
 * committed render puts the ring — and what Enter would select — on a row the
 * user never focused, and re-resolving the index in a post-paint effect
 * corrects it one render too late. Two primitive states rather than one object,
 * so a key that lands where the focus already is bails out of the re-render.
 *
 * A focus whose node is no longer focusable reads as "nothing focused"
 * *without* being cleared: the ring disappears while a search hides the node
 * and comes back on the node the user actually left it on once the query is
 * backed out. While the node is hidden, arrows behave as if nothing were
 * focused (ArrowDown starts at the top).
 *
 * The handler takes every key that reaches the list: neither rows nor headers
 * are focusable, so the list itself always holds DOM focus.
 */
export function useKeyboardNav({
  nodes,
  onSelect,
  onToggleGroup,
  onSlash,
  onEscape,
  scrollToId,
  scrollToGroup,
}: UseKeyboardNavArgs): UseKeyboardNavResult {
  const focusable = useMemo(
    () => nodes.filter((node) => node instanceof GroupNode || !node.disabled),
    [nodes],
  );

  const [rowState, setRowState] = useState<Id | null>(null);
  const [groupState, setGroupState] = useState<GroupKey | undefined>(undefined);
  // Synchronous mirror of the state, so a key handler resolves the CURRENT
  // focus even for keydowns React batches into a single render (reading state
  // would give every key in the batch the same pre-batch position).
  const focusRef = useRef<Focus>({ row: null, group: undefined });

  // Both writers go through here, so the ref and the state can never drift.
  const setFocused = useCallback((focus: Focus) => {
    focusRef.current = focus;
    setRowState(focus.row);
    setGroupState(focus.group);
  }, []);

  // Rows are keyed by `idKey`, the one row identity, not by the raw id: a
  // rerun can ship the focused row with its id in another type (`7` becomes
  // `"7"` when a DataFrame column changes type), and a raw key then lost the
  // focus while the row stayed on screen.
  //
  // Maps rather than a scan because `indexOf` runs in the render body: a
  // findIndex compared every row and returned -1 on EVERY render while nothing
  // was focused (twice per click, once per keystroke), and each arrow key paid
  // two more scans — ~5000 comparisons apiece at the design target. The build
  // is O(rows) at the same cadence as the `focusable` filter above it.
  const { rowIndex, groupIndex } = useMemo(() => {
    const rows = new Map<string, number>();
    const groups = new Map<GroupKey, number>();
    focusable.forEach((node, index) => {
      if (node instanceof GroupNode) {
        groups.set(node.group, index);
      } else {
        rows.set(idKey(node.id), index);
      }
    });
    return { rowIndex: rows, groupIndex: groups };
  }, [focusable]);

  const indexOf = useCallback(
    ({ row, group }: Focus): number => {
      if (group !== undefined) {
        return groupIndex.get(group) ?? -1;
      }
      return row === null ? -1 : (rowIndex.get(idKey(row)) ?? -1);
    },
    [rowIndex, groupIndex],
  );

  // One of the two is set at a time (setFocused writes both).
  const index = indexOf({ row: rowState, group: groupState });
  const focusedNode = index >= 0 ? elementAt(focusable, index) : undefined;
  // The row's id as `nodes` spells it now, which GroupBlock compares with `===`.
  const focusedId =
    focusedNode === undefined || focusedNode instanceof GroupNode
      ? null
      : focusedNode.id;
  const focusedGroup =
    focusedNode instanceof GroupNode ? focusedNode.group : undefined;

  const setFocusToId = useCallback(
    (id: Id) => {
      if (rowIndex.has(idKey(id))) {
        setFocused({ row: id, group: undefined });
      }
    },
    [rowIndex, setFocused],
  );

  const setFocusToGroup = useCallback(
    (group: GroupKey) => {
      if (groupIndex.has(group)) {
        setFocused({ row: null, group });
      }
    },
    [groupIndex, setFocused],
  );

  // A key-driven focus move must also scroll the node into view: focus here is
  // virtual (aria-activedescendant), and browsers only auto-scroll for REAL DOM
  // focus, so without this the ring silently leaves the scroll frame after a
  // few ArrowDowns (End leaves it a whole list away) and Enter then selects a
  // row the user cannot see.
  const moveFocusTo = useCallback(
    (index: number) => {
      const node = elementAt(focusable, index);
      if (node instanceof GroupNode) {
        setFocused({ row: null, group: node.group });
        scrollToGroup?.(node.group);
      } else {
        setFocused({ row: node.id, group: undefined });
        scrollToId?.(node.id);
      }
    },
    [focusable, setFocused, scrollToId, scrollToGroup],
  );

  const perform = useCallback(
    (action: Action) => {
      if (action.type === "move") {
        moveFocusTo(action.index);
      } else if (action.type === "select") {
        onSelect(action.id);
      } else if (action.type === "toggle") {
        onToggleGroup?.(action.group);
      }
    },
    [moveFocusTo, onSelect, onToggleGroup],
  );

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "/" || event.key === "Escape") {
        const handler = event.key === "/" ? onSlash : onEscape;
        if (handler) {
          event.preventDefault();
          handler();
        }
        return;
      }
      if (focusable.length === 0) {
        return;
      }
      // -1 when nothing is focused *or* the focused node is currently hidden.
      const action = actionFor(event.key, focusable, indexOf(focusRef.current));
      if (action !== undefined) {
        event.preventDefault();
        perform(action);
      }
    },
    [focusable, indexOf, perform, onSlash, onEscape],
  );

  return { focusedId, focusedGroup, onKeyDown, setFocusToId, setFocusToGroup };
}
