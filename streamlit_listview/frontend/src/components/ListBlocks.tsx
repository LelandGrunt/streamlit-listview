import type { FC } from "react";
import type { RenderBlock } from "../hooks/useRenderBlocks";
import { groupDomId } from "../utils/ids";
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
      {renderBlocks.map((block) => (
        <GroupBlock
          // Keyed by the block's identity, never by its position: a
          // search that hides an earlier block shifts every later one,
          // and under a positional key React handed each of them the
          // previous block's element and rebuilt all of its rows, the
          // survivors included. Never by the raw group name either: the
          // name is user-supplied (Python accepts any str), so a plain
          // string sentinel for the block without a group
          // ("__ungrouped__") was forgeable, and a real group with that
          // name gave two sibling blocks ONE key, which corrupted
          // React's reconciliation (blocks that never unmounted, phantom
          // rows, a repeated option DOM id). groupDomId tags the two
          // kinds apart: every named group carries a prefix the block
          // without a group lacks, and blocksFor yields each key once.
          key={groupDomId(block.group.name)}
          block={block}
          {...blockProps}
        />
      ))}
    </>
  );
};
