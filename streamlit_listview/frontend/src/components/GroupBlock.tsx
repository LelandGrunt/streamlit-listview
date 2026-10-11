import type { CSSProperties, FC, HTMLAttributes } from "react";
import type { Id, ListviewItem } from "../types";
import type { BlockPlace, RenderBlock } from "../hooks/useRenderBlocks";
import type { GroupKey } from "../hooks/useCollapse";
import { groupDomId, idKey, optionDomId } from "../utils/ids";
import { GroupHeader } from "./GroupHeader";
import { ListItem } from "./ListItem";

export interface GroupBlockProps {
  block: RenderBlock;
  /** The header of the block without a group, in a grouped list. */
  ungroupedLabel: string;
  collapsibleGroups: boolean;
  /** Whether the list is a WAI-ARIA tree (`useGroupCollapse`). */
  asTree: boolean;
  /**
   * Each row's one-based place (aria-posinset): in a listbox in the whole
   * list, in a tree in its block.
   */
  rowPosition: Map<ListviewItem, number>;
  /** The number of rows in the whole list (a listbox row's aria-setsize). */
  listSize: number;
  /** Each block's place among the unfiltered blocks and its row count. */
  blockPlace: Map<GroupKey, BlockPlace>;
  isSelected: (id: Id) => boolean;
  isMuted: (id: Id) => boolean;
  widgetDisabled: boolean;
  /** The row that holds the virtual keyboard focus, or null. */
  focusedId: Id | null;
  /** The group whose header holds the virtual keyboard focus, or undefined. */
  focusedGroup: GroupKey | undefined;
  /** The row click handler; a stable identity, so the memoized rows bail out. */
  onItemClick: (id: Id) => void;
  /** A click on a header: opens or closes its group and focuses the header. */
  onHeaderClick: (group: GroupKey) => void;
}

/**
 * The role and ARIA state of a block's element.
 *
 * - With collapsible_groups the list is a WAI-ARIA tree, and each block is a
 *   treeitem: it carries the group name, aria-expanded and its place among the
 *   groups, and its rows sit one level down. A listbox may own only options and
 *   groups of options, so a toggle inside it was invalid ARIA (axe-core's
 *   aria-required-children); a treeitem is the role that opens and closes.
 *   aria-expanded follows the group's own state, as the chevron does, also
 *   while a search shows the rows of a closed group.
 * - In a listbox, a block under a header is a role="group" named by it: the
 *   grouping the ARIA practices prescribe. An empty ungrouped_label (the spec
 *   allows "") yields an unnamed group (aria-label="").
 * - The one block of a list without groups has no header to name it by, and
 *   gets no role.
 */
function blockAria(
  group: GroupKey,
  name: string,
  hasHeader: boolean,
  tree: { expanded: boolean; place: BlockPlace; count: number } | null,
): HTMLAttributes<HTMLDivElement> {
  if (tree !== null) {
    return {
      role: "treeitem",
      id: groupDomId(group),
      "aria-label": name,
      "aria-expanded": tree.expanded,
      "aria-level": 1,
      "aria-posinset": tree.place.position,
      "aria-setsize": tree.count,
    };
  }
  return hasHeader
    ? { role: "group", "aria-label": name }
    : { role: "presentation" };
}

/**
 * One block of the list (`div.listview-group`): its header, when it has one,
 * and its rows in `div.listview-group-rows`, in render chunks of
 * ROW_CHUNK_SIZE (`useRenderBlocks`). A chunk is a `div.listview-chunk` with
 * role="none", so assistive technology sees its rows as children of the
 * block's group, and scrollToId finds the block with
 * closest(".listview-group"), because a row's parent is its chunk.
 */
export const GroupBlock: FC<GroupBlockProps> = ({
  block: { group, hasHeader, open, chunks },
  ungroupedLabel,
  collapsibleGroups,
  asTree,
  rowPosition,
  listSize,
  blockPlace,
  isSelected,
  isMuted,
  widgetDisabled,
  focusedId,
  focusedGroup,
  onItemClick,
  onHeaderClick,
}) => {
  // A named block shows its group; the block without a group shows
  // ungrouped_label, its header in a grouped list.
  const name = group.name ?? ungroupedLabel;
  const place = blockPlace.get(group.name) as BlockPlace;
  return (
    <div
      className="listview-group"
      {...blockAria(
        group.name,
        name,
        hasHeader,
        asTree ? { expanded: open, place, count: blockPlace.size } : null,
      )}
    >
      {hasHeader && (
        <GroupHeader
          name={name}
          count={group.items.length}
          collapsible={collapsibleGroups}
          // Passed unconditionally: GroupHeader reads neither prop
          // in its non-collapsible variant, and isCollapsed is
          // itself gated on collapsibleGroups, so a
          // `collapsible_groups ? … : undefined` guard here only
          // restated that twice. `open`, NOT `collapsed`: that one
          // folds in the search override, and the chevron must
          // keep showing the group's real state while a query is
          // active.
          collapsed={!open}
          focused={focusedGroup === group.name}
          onToggle={() => onHeaderClick(group.name)}
        />
      )}
      {/* The rows' own element: the tree's role="group" one level
          below the group's treeitem, and nothing in a listbox,
          where the block itself is the group. The chunks stay its
          children (see ROW_CHUNK_SIZE). */}
      <div className="listview-group-rows" role={asTree ? "group" : "none"}>
        {chunks.map((run) => (
          <div
            key={run.key}
            className="listview-chunk"
            role="none"
            // The row count the skipped chunk's size estimate
            // multiplies by (listview.css). Unitless: React sets a
            // custom property as given.
            style={
              {
                "--listview-chunk-rows": run.items.length,
              } as CSSProperties
            }
          >
            {run.items.map((item) => (
              <ListItem
                key={idKey(item.id)}
                item={item}
                domId={optionDomId(item.id)}
                posInSet={rowPosition.get(item) as number}
                setSize={asTree ? place.size : listSize}
                level={asTree ? 2 : undefined}
                selected={isSelected(item.id)}
                disabled={Boolean(item.disabled) || widgetDisabled}
                focused={focusedId === item.id}
                muted={isMuted(item.id)}
                onSelect={onItemClick}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};
