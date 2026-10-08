import { useCallback, useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";
import { CHUNK_SELECTOR, forgetHeights, isSkipped } from "../utils/chunks";

/** The custom property the skipped chunks' size estimate reads (listview.css). */
export const ROW_HEIGHT_PROPERTY = "--listview-row-height";

/**
 * Publishes the height of the list's first rendered row as
 * `--listview-row-height` on the listbox. A render chunk the browser skips
 * (`.listview-chunk`, `content-visibility: auto`) is as tall as its row count
 * times this height, so the scrollbar and every scroll position match the
 * rendered list before the chunk has ever been laid out.
 *
 * On the listbox, not the container root: React gives the listbox no `style`,
 * so no rerun can overwrite or remove the property, and every chunk inherits
 * it from there.
 *
 * After every commit the hook checks which element is the first option. A new
 * one — at mount, after a search, a collapse or an options change — is measured
 * at once, so the estimate is exact before the first paint and before the jump
 * to `default` measures where its row lies. The check is one querySelector
 * that stops at the first option, a handful of nodes below the listbox: cheap
 * on every commit, and it follows the first row through every way it can be
 * replaced, which a dependency list could not name. A commit that keeps its
 * first row measures nothing: a measurement forces a layout, and the observer
 * reports a changed height anyway.
 *
 * A ResizeObserver on the listbox reports every later change of the row
 * height: `item_height`, `content_font_size`, `show_grid_lines`, a theme with
 * another font, a label that wraps after a width change. On the listbox, not
 * on the first row: the browser does not lay out a row inside a skipped chunk,
 * so an observer on the row reported nothing while the list was scrolled away
 * from its top, and a rerun that changed `item_height` there left every
 * skipped chunk at the old estimate — 37,205 px of scroll range for 1,000
 * rows that render 50,354 px tall (Chromium, 2026-10-08) — until the first
 * chunk rendered again. The listbox is as tall as its rendered chunks, so it
 * resizes whenever the rows do. The observer measures the first row in the
 * next animation frame, not in its callback: the published height resizes the
 * listbox again, which inside the callback ends the browser's delivery loop
 * with an undelivered notification and a window error event ("ResizeObserver
 * loop completed with undelivered notifications"). A frame later the write
 * lands before that frame's layout, and the observer then finds the measured
 * height already published. getBoundingClientRect lays out a row inside a
 * skipped chunk on request, so the measurement is of the row as styled now.
 * An unchanged height is not written again, so a width-only resize
 * invalidates nothing. Without ResizeObserver (jsdom, an old engine) the
 * measurement at each new first row is all there is.
 *
 * A changed height also reaches the chunks the browser rendered before and
 * skips now: such a chunk keeps the height it last rendered at
 * (`contain-intrinsic-size: auto`, see utils/chunks.ts) and ignores the new
 * estimate. After the rerun above the first chunk stayed 3,539 px tall among
 * chunks of 5,000 px, and a forced layout of its rows changed nothing. So one
 * frame after a write, once the browser has laid the write out, the hook
 * compares each skipped chunk's box with its row count times the published
 * height and makes the chunks at another height forget it (`forgetHeights`).
 * Only those: hiding a chunk whose height is right would blank it for a frame
 * if the resize moved the visible frame onto it. A chunk whose rows wrap is at
 * another height too, so it forgets its height and takes the estimate until
 * it renders again.
 *
 * The returned function measures the first row at once and publishes it;
 * scrollToId calls it right before it measures a row. A key-change remount
 * applies the stylesheet after its first commit, while every chunk is
 * skipped, so the first measurement is of an unstyled row (25.6 px instead of
 * 35.4 px), and the observer's write would land a frame after the jump has
 * measured its target. The function keeps its identity across renders.
 */
export function useRowHeight(
  listboxRef: RefObject<HTMLElement | null>,
): () => void {
  /** The first option as of the last commit; null while the list is empty. */
  const rowRef = useRef<Element | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);

  const forgetStaleHeights = useCallback((): void => {
    const host = listboxRef.current;
    if (host === null) {
      return;
    }
    const height = parseFloat(host.style.getPropertyValue(ROW_HEIGHT_PROPERTY));
    const stale: Element[] = [];
    for (const chunk of host.querySelectorAll(CHUNK_SELECTOR)) {
      if (
        isSkipped(chunk) &&
        Math.abs(
          chunk.getBoundingClientRect().height -
            chunk.childElementCount * height,
        ) > 0.5
      ) {
        stale.push(chunk);
      }
    }
    forgetHeights(stale);
  }, [listboxRef]);

  const publish = useCallback((): void => {
    const host = listboxRef.current;
    const row = rowRef.current;
    if (host === null || row === null) {
      return;
    }
    const height = row.getBoundingClientRect().height;
    const value = `${height}px`;
    if (
      height > 0 &&
      host.style.getPropertyValue(ROW_HEIGHT_PROPERTY) !== value
    ) {
      host.style.setProperty(ROW_HEIGHT_PROPERTY, value);
      requestAnimationFrame(forgetStaleHeights);
    }
  }, [listboxRef, forgetStaleHeights]);

  useLayoutEffect(() => {
    const host = listboxRef.current;
    if (host === null) {
      return;
    }
    if (observerRef.current === null && typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => requestAnimationFrame(publish));
      observer.observe(host);
      observerRef.current = observer;
    }
    const row = host.querySelector('[role="option"]');
    if (row !== rowRef.current) {
      rowRef.current = row;
      publish();
    }
  });

  useLayoutEffect(
    () => () => {
      observerRef.current?.disconnect();
      observerRef.current = null;
      rowRef.current = null;
    },
    [],
  );

  return publish;
}
