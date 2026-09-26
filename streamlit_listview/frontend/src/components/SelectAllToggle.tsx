import type { FC } from "react";

export interface SelectAllToggleProps {
  /** Visible label text; also the accessible name. Owned by Listview.tsx. */
  label: string;
  onClick: () => void;
  disabled: boolean;
}

/**
 * A plain text toggle button for bulk select/deselect of the visible set.
 * Not a checkbox (D2). Placement-agnostic: it renders only a button and the
 * container decides where it lives. The label is always a prop, never
 * hardcoded here, so the two literals ("Select all" / "Deselect all") stay
 * owned solely by Listview.tsx.
 */
export const SelectAllToggle: FC<SelectAllToggleProps> = ({
  label,
  onClick,
  disabled,
}) => (
  <button
    type="button"
    className="listview-select-all"
    data-testid="stListviewSelectAllToggle"
    disabled={disabled}
    onClick={onClick}
  >
    {label}
  </button>
);
