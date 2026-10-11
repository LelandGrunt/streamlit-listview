import type { FC } from "react";

export interface GroupHeaderProps {
  /** Group name; rendered as plain text. */
  name: string;
  /** Number of items in the group; rendered as a muted "(N)" after the name. */
  count: number;
  /** When true, render the toggle: a chevron, and a click opens or closes the group. */
  collapsible?: boolean;
  /** Current collapsed state (only meaningful when collapsible). */
  collapsed?: boolean;
  /** The tree's keyboard focus is on this header (only when collapsible). */
  focused?: boolean;
  /** Toggle handler (only when collapsible). */
  onToggle?: () => void;
}

/**
 * Group header. Static (presentational) by default — the Milestone-A behavior.
 * When `collapsible`, it adds a chevron that rotates with state, and a click
 * toggles the group.
 *
 * The item count renders as a muted "(N)" span after the name in both variants.
 *
 * a11y: both variants are aria-hidden. The enclosing block carries the group
 * name for assistive technology — a named role="group" in a listbox, or with
 * collapsible_groups a role="treeitem" that also carries aria-expanded — so this
 * text would otherwise be announced a second time, and as content the listbox
 * or tree does not own. aria-hidden, not role="presentation": presentation drops
 * the element's own role but leaves its text in the accessibility tree.
 *
 * The collapsible header takes no focus and is no <button>: a button inside a
 * listbox or tree is a child neither may own (axe-core's aria-required-children).
 * The keyboard reaches the header through the tree instead: it is a node of the
 * tree's aria-activedescendant navigation (useKeyboardNav), and `focused` draws
 * its ring.
 */
export const GroupHeader: FC<GroupHeaderProps> = ({
  name,
  count,
  collapsible = false,
  collapsed = false,
  focused = false,
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
    <div
      className={
        "listview-group-header listview-group-header--collapsible" +
        (focused ? " listview-group-header--focused" : "")
      }
      data-testid="stListviewGroup"
      aria-hidden="true"
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
        <path
          d="M6 9l6 6 6-6"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="listview-group-header__name">{name}</span>
      <span className="listview-group-header__count">({count})</span>
    </div>
  );
};
