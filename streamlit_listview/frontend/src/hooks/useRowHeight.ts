import { useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";

/** The custom property the skipped chunks' size estimate reads (listview.css). */
export const ROW_HEIGHT_PROPERTY = "--listview-row-height";

interface Observed {
  row: Element;
  observer: ResizeObserver | null;
}

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
 * to `default` measures where its row lies, and then observed with a
 * ResizeObserver, which reports every later change: `item_height`,
 * `content_font_size`, `show_grid_lines`, a theme with another font, a label
 * that wraps after a width change. An unchanged height is not written again, so
 * a width-only resize invalidates nothing. Without ResizeObserver (jsdom, an old
 * engine) the measurement at each change is all there is.
 *
 * The check is one querySelector that stops at the first option, a handful of
 * nodes below the listbox: cheap on every commit, and it follows the first row
 * through every way it can be replaced, which a dependency list could not name.
 */
export function useRowHeight(listboxRef: RefObject<HTMLElement | null>): void {
  const observed = useRef<Observed | null>(null);

  useLayoutEffect(() => {
    const listbox = listboxRef.current;
    const row = listbox?.querySelector('[role="option"]') ?? null;
    if (row === (observed.current?.row ?? null)) {
      return;
    }
    observed.current?.observer?.disconnect();
    observed.current = null;
    if (row === null) {
      return;
    }
    // `row` was found inside the listbox, so the listbox is mounted.
    const host = listbox as HTMLElement;
    const publish = (): void => {
      const height = row.getBoundingClientRect().height;
      const value = `${height}px`;
      if (
        height > 0 &&
        host.style.getPropertyValue(ROW_HEIGHT_PROPERTY) !== value
      ) {
        host.style.setProperty(ROW_HEIGHT_PROPERTY, value);
      }
    };
    publish();
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(publish);
    observer?.observe(row);
    observed.current = { row, observer };
  });

  useLayoutEffect(
    () => () => {
      observed.current?.observer?.disconnect();
      observed.current = null;
    },
    [],
  );
}
