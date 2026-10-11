/** Switches a render chunk to `content-visibility: hidden` (listview.css). */
export const FORGET_CLASS = "listview-chunk--forget";

/** Selects the render chunks below a listbox (`div.listview-chunk`, components/GroupBlock.tsx). */
export const CHUNK_SELECTOR = ".listview-chunk";

/** True when the browser skips the chunk's rows (content-visibility: auto). */
export function isSkipped(chunk: Element): boolean {
  // A chunk always holds at least one row: runsByKey emits no empty run.
  const row = chunk.firstElementChild as Element;
  return (
    typeof row.checkVisibility === "function" &&
    !row.checkVisibility({ contentVisibilityAuto: true })
  );
}

/**
 * Makes the browser forget the height each chunk had when it last rendered.
 *
 * `content-visibility: auto` implies `contain-intrinsic-size: auto` (CSS
 * Containment 2; Chromium computes the chunk's size as `auto <estimate>`
 * although listview.css writes no `auto`): a chunk the browser has rendered
 * once keeps that rendered height while it is skipped and ignores the
 * estimate. The browser drops a remembered height at a rendering update in
 * which the element has no `auto` in its used `contain-intrinsic-size`. So
 * each chunk carries FORGET_CLASS for two animation frames:
 * `content-visibility: hidden` implies no `auto`, and it keeps the chunk
 * skipped, so nothing paints differently. When the class goes, the chunk takes
 * its estimate until it renders again. Two frames: the first rendering update
 * after the call must see the class, and a callback of the next frame runs
 * before its style recalc. Call it for skipped chunks only: hiding a chunk the
 * browser renders blanks it for a frame, and its remembered height follows its
 * rendered rows by itself. A second call while the class is on needs no second
 * cycle: a hidden chunk renders nothing, so it remembers nothing new.
 */
export function forgetHeights(chunks: Element[]): void {
  if (chunks.length === 0) {
    return;
  }
  for (const chunk of chunks) {
    chunk.classList.add(FORGET_CLASS);
  }
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      for (const chunk of chunks) {
        chunk.classList.remove(FORGET_CLASS);
      }
    });
  });
}
