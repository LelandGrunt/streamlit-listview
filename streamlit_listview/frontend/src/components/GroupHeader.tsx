import type { FC } from "react";

export interface GroupHeaderProps {
  /** Group name; rendered as plain text. */
  name: string;
  /** Number of items in the group; rendered as a muted "(N)" after the name. */
  count: number;
  /** When true, render an interactive toggle (chevron + aria-expanded). */
  collapsible?: boolean;
  /** Current collapsed state (only meaningful when collapsible). */
  collapsed?: boolean;
  /** Toggle handler (only when collapsible). */
  onToggle?: () => void;
}

/**
 * Group header. Static (presentational) by default — the Milestone-A behavior.
 * When `collapsible`, it becomes a <button> carrying aria-expanded and a chevron
 * that rotates with state; click / Enter / Space toggle it (native button keys).
 *
 * The item count renders as a muted "(N)" span after the name in both variants.
 *
 * a11y: the static header is aria-hidden. Its enclosing block is a named
 * role="group" (the container passes the group name as its aria-label), so this
 * text would otherwise be announced a second time — and as non-option content
 * inside a listbox, which owns only options, AT can read it out as if it were an
 * item. aria-hidden, not role="presentation": presentation drops the element's
 * own role but leaves its text in the accessibility tree. The collapsible variant
 * cannot be hidden that way — it is a focusable button, and aria-hidden on a
 * focusable element is invalid — so it stays exposed and its name doubles as the
 * group name.
 */
export const GroupHeader: FC<GroupHeaderProps> = ({
  name,
  count,
  collapsible = false,
  collapsed = false,
  onToggle,
}) => {
  if (!collapsible) {
    return (
      <div
        className="listview-group-header"
        data-testid="stListviewGroup"
        aria-hidden="true"
      >
        <span className="listview-group-header__name">{name}</span>
        <span className="listview-group-header__count">({count})</span>
      </div>
    );
  }

  return (
    <button
      type="button"
      className="listview-group-header listview-group-header--collapsible"
      data-testid="stListviewGroup"
      aria-expanded={!collapsed}
      onClick={onToggle}
    >
      <svg
        className="listview-group-header__chevron"
        viewBox="0 0 24 24"
        width="1em"
        height="1em"
        aria-hidden="true"
        focusable="false"
        data-collapsed={collapsed ? "true" : "false"}
      >
        {/* chevron-down; CSS rotates it -90deg when collapsed */}
        <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="listview-group-header__name">{name}</span>
      <span className="listview-group-header__count">({count})</span>
    </button>
  );
};
