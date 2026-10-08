import { useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";

/** Switches a render chunk to `content-visibility: hidden` (listview.css). */
export const FORGET_CLASS = "listview-chunk--forget";

/**
 * Makes the browser forget the height a skipped render chunk had when it last
 * rendered, once the chunk's rows change.
 *
 * `content-visibility: auto` implies `contain-intrinsic-size: auto` (CSS
 * Containment 2; Chromium computes the chunk's size as `auto <estimate>`
 * although listview.css writes no `auto`): a chunk the browser has rendered
 * once keeps that rendered height while it is skipped and ignores the
 * row-count estimate. A search or an options change that altered the rows of
 * such a chunk while it was off-screen therefore left it at its old height —
 * after scrolling through a 100k list and searching, the list was 3,504 px too
 * tall for one chunk that had shrunk from 100 rows to 1 — until the user
 * scrolled the chunk back into view.
 *
 * The browser drops a remembered height at a rendering update in which the
 * element has no `auto` in its used `contain-intrinsic-size`. So after a commit
 * that changed the blocks, every chunk whose row count changed while it is
 * skipped carries FORGET_CLASS for two animation frames: `content-visibility:
 * hidden` implies no `auto`, and it keeps the chunk skipped, so nothing paints
 * differently. When the class goes, the chunk takes its estimate until it
 * renders again. A chunk the browser is rendering is left alone: its
 * remembered height follows its rendered rows by itself, and hiding it would
 * blank it for a frame. A second change while the class is on needs no second
 * cycle: a hidden chunk renders nothing, so it remembers nothing new.
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
    for (const chunk of listbox.querySelectorAll(".listview-chunk")) {
      const rows = chunk.childElementCount;
      const before = rowCounts.current.get(chunk);
      rowCounts.current.set(chunk, rows);
      if (before !== undefined && before !== rows && isSkipped(chunk)) {
        forget.push(chunk);
      }
    }
    if (forget.length === 0) {
      return;
    }
    for (const chunk of forget) {
      chunk.classList.add(FORGET_CLASS);
    }
    // Two frames: the first rendering update after this commit must see the
    // class, and a callback of the next frame runs before its style recalc.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        for (const chunk of forget) {
          chunk.classList.remove(FORGET_CLASS);
        }
      });
    });
  }, [listboxRef, blocks]);
}

/** True when the browser skips the chunk's rows (content-visibility: auto). */
function isSkipped(chunk: Element): boolean {
  // A chunk always holds at least one row: runsByKey emits no empty run.
  const row = chunk.firstElementChild as Element;
  return (
    typeof row.checkVisibility === "function" &&
    !row.checkVisibility({ contentVisibilityAuto: true })
  );
}
