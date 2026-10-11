import type { FC } from "react";
import type { RenderBlock } from "../hooks/useRenderBlocks";
import { GroupBlock } from "./GroupBlock";
import type { GroupBlockProps } from "./GroupBlock";

export interface ListBlocksProps extends Omit<GroupBlockProps, "block"> {
  /** The blocks the list renders (`useRenderBlocks`). */
  renderBlocks: RenderBlock[];
  /** True while the list has no row at all (the placeholder shows then). */
  empty: boolean;
  /** The text shown instead of the rows while the list has none. */
  placeholder: string | null;
}

/**
 * The listbox's content: the placeholder while the list has no row, else one
 * `GroupBlock` per rendered block. A search that matches nothing shows no
 * placeholder: the list still has its rows.
 */
export const ListBlocks: FC<ListBlocksProps> = ({
  renderBlocks,
  empty,
  placeholder,
  ...blockProps
}) => {
  if (empty) {
    return (
      <div className="listview-placeholder" data-testid="listview-placeholder">
        {placeholder ?? ""}
      </div>
    );
  }
  return (
    <>
      {renderBlocks.map((block, index) => (
        <GroupBlock
          // Keyed by POSITION, never by the group name: the name is
          // user-supplied (Python accepts any str), so any string
          // sentinel for the block without a group — "__ungrouped__" —
          // is forgeable, and a real group with that name handed two
          // sibling blocks ONE key. Duplicate keys corrupt React's
          // reconciliation: measured fallout was blocks that never
          // unmount, phantom rows accumulating across filter changes, a
          // repeated option DOM id (ambiguous aria-activedescendant) and
          // rows on screen that did not match the active query. The
          // block without a group has no name at all, so no
          // name-derived scheme could key it anyway. Blocks hold no
          // state of their own (collapse state lives in useCollapse,
          // keyed by group name or null), so a positional key costs
          // nothing.
          key={index}
          block={block}
          {...blockProps}
        />
      ))}
    </>
  );
};
