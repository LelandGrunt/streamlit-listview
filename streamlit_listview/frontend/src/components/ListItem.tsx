import { memo } from "react";
import type { MouseEvent } from "react";
import type { Id, ListviewItem } from "../types";
import { idKey } from "../utils/ids";

export interface ListItemProps {
  item: ListviewItem;
  /** Stable DOM id so the listbox can target aria-activedescendant. */
  domId: string;
  /**
   * One-based place of the row in the whole, unfiltered list (aria-posinset).
   * The browser leaves the rows of a skipped render chunk out of the
   * accessibility tree, so a screen reader takes the place and the count from
   * these two rather than from the rows it can see.
   */
  posInSet: number;
  /** Number of rows in the whole, unfiltered list (aria-setsize). */
  setSize: number;
  /**
   * The row's aria-level when it is a row of a tree (collapsible_groups): it
   * then renders as a treeitem, and `posInSet` / `setSize` count its group's
   * rows. Absent in a listbox, where it renders as an option.
   */
  level?: number | undefined;
  selected: boolean;
  disabled: boolean;
  focused: boolean;
  /** Multi mode at max_selections and not selected: visually muted. */
  muted: boolean;
  onSelect: (id: Id) => void;
}

/**
 * A single selectable row: role="option" in a listbox, role="treeitem" in the
 * tree that collapsible groups make of the list.
 *
 * Clicking a non-disabled item invokes onSelect(id). Disabled items are inert.
 * Selected/disabled visual state rides the aria-selected/aria-disabled
 * attributes (listview.css styles those selectors directly); focused/muted are
 * modifier classes. The row exposes the locked
 * data-testid="stListviewOption-<id>" that the e2e suite selects on.
 */
export const ListItem = memo(function ListItem({
  item,
  domId,
  posInSet,
  setSize,
  level,
  selected,
  disabled,
  focused,
  muted,
  onSelect,
}: ListItemProps) {
  const handleClick = (_event: MouseEvent<HTMLDivElement>): void => {
    if (disabled) {
      return;
    }
    onSelect(item.id);
  };

  const className =
    "listview-item" +
    (focused ? " listview-item--focused" : "") +
    (muted ? " listview-item--muted" : "");

  return (
    <div
      id={domId}
      className={className}
      data-testid={`stListviewOption-${idKey(item.id)}`}
      role={level === undefined ? "option" : "treeitem"}
      aria-level={level}
      aria-posinset={posInSet}
      aria-setsize={setSize}
      aria-selected={selected}
      aria-disabled={disabled || undefined}
      onClick={handleClick}
    >
      <span className="listview-item__label">{item.label}</span>
    </div>
  );
});
