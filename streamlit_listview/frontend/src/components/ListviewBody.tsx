import type {
  FC,
  KeyboardEvent,
  MouseEvent,
  ReactNode,
  RefObject,
} from "react";
import type { GroupKey } from "../hooks/useCollapse";
import type { Id, SelectionMode } from "../types";
import { groupDomId, optionDomId } from "../utils/ids";

export interface ListviewBodyProps {
  bodyRef: RefObject<HTMLDivElement | null>;
  listboxRef: RefObject<HTMLDivElement | null>;
  widgetDisabled: boolean;
  /**
   * A click on the body's own empty space (Listview's `onBodyClick`). Not
   * attached while the widget is disabled.
   */
  onBodyClick: (event: MouseEvent<HTMLDivElement>) => void;
  enableSearch: boolean;
  pinSearch: boolean;
  /** The search field element (null when search is off); it renders here while not pinned. */
  searchField: ReactNode;
  /** The id of the element that names the listbox (aria-labelledby). */
  labelId: string;
  selectionMode: SelectionMode;
  /** Whether the list is a WAI-ARIA tree (`useGroupCollapse`). */
  asTree: boolean;
  /** The row that holds the virtual keyboard focus, or null. */
  focusedId: Id | null;
  /** The group whose header holds the virtual keyboard focus, or undefined. */
  focusedGroup: GroupKey | undefined;
  /** The listbox's key handler (`useKeyboardNav`). Not attached while the widget is disabled. */
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
  /** The listbox's content (`ListBlocks`). */
  children: ReactNode;
}

/**
 * The DOM id that aria-activedescendant names: the focused row's, else the
 * focused header's group treeitem, else none.
 */
function activeDescendantOf(
  focusedId: Id | null,
  focusedGroup: GroupKey | undefined,
): string | undefined {
  if (focusedId !== null) {
    return optionDomId(focusedId);
  }
  return focusedGroup !== undefined ? groupDomId(focusedGroup) : undefined;
}

/**
 * The scroll frame (`div.listview-body`) and the list inside it
 * (`div.listview-listbox`, role="listbox", or role="tree" while groups open
 * and close): the in-flow search field at the top of the frame, then the
 * rows. Keyboard focus is virtual: the list is the one focusable element, and
 * `aria-activedescendant` names the focused row or header.
 */
export const ListviewBody: FC<ListviewBodyProps> = ({
  bodyRef,
  listboxRef,
  widgetDisabled,
  onBodyClick,
  enableSearch,
  pinSearch,
  searchField,
  labelId,
  selectionMode,
  asTree,
  focusedId,
  focusedGroup,
  onKeyDown,
  children,
}) => (
  <div
    className="listview-body"
    ref={bodyRef}
    onClick={widgetDisabled ? undefined : onBodyClick}
  >
    {enableSearch && !pinSearch && searchField}

    <div
      className="listview-listbox"
      ref={listboxRef}
      // The class stays listview-listbox in a tree: the stylesheet and the
      // tests address the element by it in both roles.
      role={asTree ? "tree" : "listbox"}
      aria-labelledby={labelId}
      tabIndex={widgetDisabled ? -1 : 0}
      aria-multiselectable={selectionMode === "multi" ? true : undefined}
      aria-disabled={widgetDisabled || undefined}
      aria-activedescendant={activeDescendantOf(focusedId, focusedGroup)}
      onKeyDown={widgetDisabled ? undefined : onKeyDown}
    >
      {children}
    </div>
  </div>
);
