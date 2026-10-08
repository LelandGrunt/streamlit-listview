import { useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";
import { CHUNK_SELECTOR, forgetHeights, isSkipped } from "../utils/chunks";

/**
 * Makes the browser forget the height a skipped render chunk had when it last
 * rendered, once the chunk's rows change (the mechanism: utils/chunks.ts,
 * `forgetHeights`).
 *
 * A search or an options change that altered the rows of a chunk while it was
 * off-screen left it at its old height — after scrolling through a 100k list
 * and searching, the list was 3,504 px too tall for one chunk that had shrunk
 * from 100 rows to 1 — until the user scrolled the chunk back into view. So
 * after a commit that changed the blocks, every chunk whose row count changed
 * while it is skipped forgets its height. A chunk the browser is rendering is
 * left alone. A change of the row height is the other way a remembered height
 * goes stale; useRowHeight handles it after it publishes a changed height.
 *
 * `blocks` is only a dependency: Listview passes its renderBlocks, which change
 * whenever a chunk's rows may have. Without checkVisibility (jsdom, an old
 * engine) the hook cannot tell a skipped chunk from a rendered one and hides
 * nothing.
 */
export function useResetChunkHeights(
  listboxRef: RefObject<HTMLElement | null>,
  blocks: unknown,
): void {
  const rowCounts = useRef(new WeakMap<Element, number>());

  useLayoutEffect(() => {
    const listbox = listboxRef.current;
    if (listbox === null) {
      return;
    }
    const forget: Element[] = [];
    for (const chunk of listbox.querySelectorAll(CHUNK_SELECTOR)) {
      const rows = chunk.childElementCount;
      const before = rowCounts.current.get(chunk);
      rowCounts.current.set(chunk, rows);
      if (before !== undefined && before !== rows && isSkipped(chunk)) {
        forget.push(chunk);
      }
    }
    forgetHeights(forget);
  }, [listboxRef, blocks]);
}
