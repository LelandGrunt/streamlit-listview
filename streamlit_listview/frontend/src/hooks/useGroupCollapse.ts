import { useCallback, useMemo } from "react";
import type { ListviewItem } from "../types";
import { blockKeyOf } from "../utils/blocks";
import { useCollapse } from "./useCollapse";
import type { GroupKey, UseCollapseResult } from "./useCollapse";

export interface UseGroupCollapseArgs {
  /** The caller's options: `Listview`'s `items`, never `data.items`. */
  items: ListviewItem[];
  ungroupedLabel: string;
  /**
   * The synthetic rows (`useNewOptionRows`): while one exists, the block
   * without a group carries a header, so it counts as a group of its own.
   */
  newOptionItems: ListviewItem[];
  collapsibleGroups: boolean;
  /** The caller's `collapsed_groups`, naming headers: `ungrouped_label` names the block without a group. */
  collapsedGroups: string[] | "all" | null;
}

export interface UseGroupCollapseResult {
  /**
   * True when one of the options names a group, the one named like
   * `ungrouped_label` included. Only then does the block without a group
   * carry a header. Judged on the unfiltered options, so a search never adds
   * or drops that header.
   */
  isGrouped: boolean;
  /**
   * True when the list is a WAI-ARIA tree: its groups open and close
   * (`collapsible_groups`) and it has groups. A list without groups has
   * nothing to open and stays a listbox (see `blockAria` in GroupBlock).
   */
  asTree: boolean;
  collapse: UseCollapseResult;
  /**
   * Opens the block a row with `group` renders in, before a scroll to that
   * row. Takes the row's group, or `null` when it has none.
   */
  expandBlock: (group: string | null) => void;
}

/**
 * The groups the caller's options name, and the open/closed state of their
 * blocks (`useCollapse`), keyed as `blockKeyOf` keys them.
 */
export function useGroupCollapse({
  items,
  ungroupedLabel,
  newOptionItems,
  collapsibleGroups,
  collapsedGroups,
}: UseGroupCollapseArgs): UseGroupCollapseResult {
  // One pass over the caller's options (blocks as in blockKeyOf):
  //  - groupNames: the named blocks, in the order they first appear;
  //  - isGrouped: one of the options names a group, the one named like
  //    ungrouped_label included. Only then does the block without a group
  //    carry a header and count as a group of its own. Judged on the unfiltered
  //    options, so a search never adds or drops that header;
  //  - hasUngroupedOption: one of the options renders in that block.
  const { groupNames, isGrouped, hasUngroupedOption } = useMemo(() => {
    const names = new Set<string>();
    let grouped = false;
    let ungrouped = false;
    for (const item of items) {
      grouped ||= item.group != null;
      const key = blockKeyOf(item.group, ungroupedLabel);
      if (key === null) {
        ungrouped = true;
      } else {
        names.add(key);
      }
    }
    return {
      groupNames: Array.from(names),
      isGrouped: grouped,
      hasUngroupedOption: ungrouped,
    };
  }, [items, ungroupedLabel]);
  // The groups useCollapse tracks: every named group, plus `null` for the block
  // without a group while it carries a header — that is, while some row renders
  // in it, among the caller's options or the added ones.
  const groupKeys = useMemo<GroupKey[]>(() => {
    if (!isGrouped) {
      return groupNames;
    }
    return hasUngroupedOption || newOptionItems.length > 0
      ? [...groupNames, null]
      : groupNames;
  }, [groupNames, isGrouped, hasUngroupedOption, newOptionItems]);
  // collapsed_groups names headers, so ungrouped_label in it names the block
  // without a group.
  const collapsedKeys = useMemo(
    () =>
      Array.isArray(collapsedGroups)
        ? collapsedGroups.map((name) => blockKeyOf(name, ungroupedLabel))
        : collapsedGroups,
    [collapsedGroups, ungroupedLabel],
  );
  const collapse = useCollapse({
    collapsibleGroups,
    collapsedGroups: collapsedKeys,
    groupKeys,
  });
  // Opens the block a row with `group` renders in, before a scroll to that row.
  // A block without a header — the one block of a list without groups — cannot
  // be collapsed, and expanding its `null` key anyway would count as a
  // sighting: a later rerun that brings in groups would then skip the
  // collapsed_groups="all" seed for the block without a group.
  const expandGroup = collapse.expand;
  const expandBlock = useCallback(
    (group: string | null) => {
      const key = blockKeyOf(group, ungroupedLabel);
      if (key !== null || isGrouped) {
        expandGroup(key);
      }
    },
    [expandGroup, isGrouped, ungroupedLabel],
  );

  return {
    isGrouped,
    asTree: collapsibleGroups && isGrouped,
    collapse,
    expandBlock,
  };
}
