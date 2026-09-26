import { memo } from "react";
import type { MouseEvent } from "react";
import type { Id, ListviewItem } from "../types";
import { idKey } from "../utils/ids";

export interface ListItemProps {
  item: ListviewItem;
  /** Stable DOM id so the listbox can target aria-activedescendant. */
  domId: string;
  selected: boolean;
  disabled: boolean;
  focused: boolean;
  /** Multi mode at max_selections and not selected: visually muted. */
  muted: boolean;
  onSelect: (id: Id) => void;
}

/**
 * A single selectable option row (role="option").
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
      role="option"
      aria-selected={selected}
      aria-disabled={disabled || undefined}
      onClick={handleClick}
    >
      <span className="listview-item__label">{item.label}</span>
    </div>
  );
});
