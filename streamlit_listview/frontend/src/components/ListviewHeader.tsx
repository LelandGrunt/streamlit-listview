import type { FC, ReactNode } from "react";
import { SelectAllToggle } from "./SelectAllToggle";
import type { SelectAllToggleProps } from "./SelectAllToggle";

export interface ListviewHeaderProps {
  enableSearch: boolean;
  pinSearch: boolean;
  /** The search field element (null when search is off); it renders here while pinned. */
  searchField: ReactNode;
  selectAll: boolean;
  /** What the select-all toggle shows and does (`useSelectAll`). */
  toggle: SelectAllToggleProps;
}

/**
 * The strip above the scroll frame (`div.listview-header`): the pinned search
 * field and the select-all toggle, in that order. Renders nothing while
 * neither is on. listview.css paints the seam under it as a background, not a
 * border, because focus recolors the borders of header and body.
 */
export const ListviewHeader: FC<ListviewHeaderProps> = ({
  enableSearch,
  pinSearch,
  searchField,
  selectAll,
  toggle,
}) => {
  if (!(selectAll || (enableSearch && pinSearch))) {
    return null;
  }
  return (
    <div className="listview-header">
      {enableSearch && pinSearch && searchField}
      {selectAll && <SelectAllToggle {...toggle} />}
    </div>
  );
};
