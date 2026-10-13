import { useCallback } from "react";
import type { RefObject } from "react";
import type { Id } from "../types";
import { FORGET_CLASS } from "../utils/chunks";
import { groupDomId, optionDomId } from "../utils/ids";
import type { GroupKey } from "./useCollapse";

/** Where a scrolled-to row lands in the frame (the ScrollLogicalPosition subset we implement). */
export type ScrollBlock = "center" | "nearest";

/**
 * How many frames scrollToId waits for the target row's chunk to drop
 * FORGET_CLASS before it measures the row anyway. useResetChunkHeights keeps
 * the class on for two frames; the bound only keeps a class that somehow
 * stayed from parking the scroll forever.
 */
const FORGET_WAIT_FRAMES = 4;

/**
 * How many frames scrollToId waits for the list's stylesheet before it measures
 * the row anyway: about ten seconds at 60 Hz. A remounted instance fetches its
 * stylesheet again, so on a slow connection the sheet arrives frames after the
 * first commit. The bound only stops the wait for a sheet that never loads.
 */
const STYLE_WAIT_FRAMES = 600;

/**
 * True once listview.css applies to the list: it makes the body a scroll
 * container (overflow-y: auto), and until then the computed value is the
 * initial `visible`. Before that the rows are unstyled and a scrollTop written
 * to the body is lost.
 */
function isStyled(body: HTMLElement): boolean {
  return getComputedStyle(body).overflowY !== "visible";
}

/**
 * Where `rect` (a box inside the scrolled content of `body`) starts, measured
 * from the top of that content: its position relative to the frame, plus
 * however far the frame is already scrolled. scrollTop is measured from the
 * padding-box edge while the rect is the border box, so the body's top border
 * (clientTop) comes out — otherwise every "nearest" scroll landed one
 * border-width off, clipping the row.
 */
function contentTop(body: HTMLElement, rect: DOMRect): number {
  return (
    body.scrollTop +
    rect.top -
    (body.getBoundingClientRect().top + body.clientTop)
  );
}

/**
 * The rendered element carrying `domId` inside `body` — a row (`selector`
 * ".listview-item") or a group's block (".listview-group") — or null when it is
 * not rendered (filtered out, in a collapsed group).
 *
 * Looked up through the tree scope the body lives in. In production that is
 * THIS instance's ShadowRoot (`isolate_styles=True`, Streamlit's default — the
 * renderer is handed the ShadowRoot as `parentElement`), so `getElementById` is
 * an id-map hit rather than a walk over every rendered row per arrow key, and
 * sibling listviews cannot see each other's rows even though `optionDomId`
 * carries no instance prefix — the same per-tree scoping `aria-activedescendant`
 * already relies on. It also takes a RAW string, so an id holding a newline, a
 * quote or a backslash needs no CSS escaping: with plain (non-dict) options the
 * id IS the option string, and a `[id="…"]` selector threw SyntaxError from
 * inside the rAF callback, where no React error boundary can catch it (even
 * CSS.escape was not a full answer — jsdom's selector engine fails to match a
 * correctly escaped backslash).
 *
 * A hit that is not inside this body — a light-DOM mount (`isolate_styles=False`,
 * or the jsdom test tree) where a same-id row of ANOTHER instance answered first
 * — falls back to scanning this body's own rows by `id` property, so every mount
 * mode resolves the right row; only the hot path changes. The scan is bounded by
 * the rendered rows (this list is not virtualized) and walked by index rather
 * than `Array.from(…).find(…)`, which materialized all rows into a fresh array
 * first.
 */
function findNode(
  body: HTMLElement,
  domId: string,
  selector: string,
): Element | null {
  const root = body.getRootNode();
  // A subtree not (yet) attached to a document has its topmost ELEMENT as
  // root, and an element has no id map — the renderer can be invoked on a
  // detached host — so only a Document / ShadowRoot root takes the fast path.
  const hit =
    "getElementById" in root
      ? (root as Document | ShadowRoot).getElementById(domId)
      : null;
  if (hit !== null && body.contains(hit)) {
    return hit;
  }
  for (const node of body.querySelectorAll(selector)) {
    if (node.id === domId) {
      return node;
    }
  }
  return null;
}

/**
 * The DOM scroll for a row id, shared by jump-to-default, keyboard navigation
 * and the reveal of an added row. rAF so an auto-expand (or focus-move)
 * re-render commits before we measure/scroll.
 *
 * Scrolls THE LIST BODY ONLY, by container-relative scrollTop math.
 * Element.scrollIntoView() would be shorter but it scrolls every scrollable
 * ancestor, including the Streamlit page: a listview with `default=` below the
 * fold yanked the host page away from whatever the user was reading, on first
 * render and on every rerun that changed `default_ids` by value.
 *
 * Two things must hold before a row's position means anything, and both fail
 * on a key-change remount, whose new shadow root loads the stylesheet again.
 * The stylesheet must have applied: until then the body does not scroll, so
 * the jump waits a frame at a time (whenStyled). And the published row height
 * must match the styled rows: the chunks above the target are sized by it, so
 * a stale height puts the row elsewhere than the browser later draws it. The
 * ResizeObserver in useRowHeight publishes a changed height a frame after
 * the listbox resized, which is a frame after this jump would measure. So
 * attempt() measures the first row again before it measures the target.
 *
 * Both waits span frames, so a later request can overtake an earlier one:
 * End waits for a forgetting chunk, Home scrolls, and the End retry then
 * scrolled the list away from the focused row. `beginRequest` (the `begin`
 * of useLatestRequest) numbers the requests, and a request that is no longer
 * the latest stops at its next frame. useScrollToGroup counts with the same
 * `begin`, so a header the keyboard lands on supersedes a waiting row too.
 *
 * `remeasureRowHeight` is the function useRowHeight returns. The returned
 * callback keeps its identity across renders (its inputs do), which the
 * reveal effect in useAddNewOption relies on.
 */
export function useScrollToId(
  bodyRef: RefObject<HTMLDivElement | null>,
  remeasureRowHeight: () => void,
  beginRequest: () => () => boolean,
): (id: Id, block?: ScrollBlock) => void {
  return useCallback(
    (id: Id, block: ScrollBlock = "center") => {
      const isLatest = beginRequest();
      const attempt = (framesLeft: number): void => {
        if (!isLatest()) {
          return;
        }
        const body = bodyRef.current;
        // Unreachable in practice: the body renders unconditionally, and this
        // callback only runs after a commit. It guards an unmount racing the
        // rAF.
        /* v8 ignore next 3 */
        if (!body) {
          return;
        }
        const node = findNode(body, optionDomId(id), ".listview-item");
        if (node === null) {
          return; // row not rendered (e.g. filtered out) → nothing to scroll to
        }
        // A row's parent is its render chunk. While the chunk carries
        // FORGET_CLASS (content-visibility: hidden, see useResetChunkHeights)
        // the row has no geometry, so a jump to a new default inside a chunk
        // whose rows changed on the same rerun would measure a zero rect. Wait
        // a frame and look again; the class goes after two.
        if (
          framesLeft > 0 &&
          (node.parentElement as HTMLElement).classList.contains(FORGET_CLASS)
        ) {
          requestAnimationFrame(() => attempt(framesLeft - 1));
          return;
        }
        remeasureRowHeight();
        const frame = body.clientHeight;
        const rowBox = node.getBoundingClientRect();
        const top = contentTop(body, rowBox);
        if (block === "center") {
          // Out-of-range assignments are clamped by the browser, so the first
          // and last rows need no special casing.
          body.scrollTop = top - (frame - rowBox.height) / 2;
        } else {
          // A grouped row's own header is position: sticky; top: 0 — it
          // paints over the top of the scrollport, so the band where a row is
          // actually visible starts BELOW it. Bringing a row's top edge to the
          // frame's top edge parked it exactly under that header: ArrowUp /
          // Home focused a row the user could not see, and Enter selected it. A
          // row always renders in a render chunk inside a group block, and the
          // block's first child is either that header or the rows' own
          // element (.listview-group-rows), so this is a fixed class-name
          // check with none of the id-escaping hazards of the row lookup; a
          // block without a header (the one block of a list without groups)
          // keeps the frame edge. closest(), not parentElement: a row's parent
          // is its chunk.
          const first = (node.closest(".listview-group") as HTMLElement)
            .firstElementChild as Element;
          const stickyHeight = first.classList.contains("listview-group-header")
            ? first.getBoundingClientRect().height
            : 0;
          if (top - stickyHeight < body.scrollTop) {
            body.scrollTop = top - stickyHeight; // above the visible band → top edge in, under the header
          } else if (top + rowBox.height > body.scrollTop + frame) {
            body.scrollTop = top + rowBox.height - frame; // below → bottom edge in
          }
        }
      };
      const whenStyled = (framesLeft: number): void => {
        const body = bodyRef.current;
        if (!body || !isLatest()) {
          return; // unmounted, or a later request took over, while it waited
        }
        if (framesLeft > 0 && !isStyled(body)) {
          requestAnimationFrame(() => whenStyled(framesLeft - 1));
          return;
        }
        attempt(FORGET_WAIT_FRAMES);
      };
      requestAnimationFrame(() => whenStyled(STYLE_WAIT_FRAMES));
    },
    [bodyRef, remeasureRowHeight, beginRequest],
  );
}

/**
 * A header the keyboard lands on, scrolled into view. The header is sticky:
 * it shows at the top of the frame while any row of its group does, so only
 * a group wholly outside the frame needs a scroll. A group below comes in by
 * the header's bottom edge, the way a row does; a group scrolled away above
 * comes back to the frame's top, header and first rows. Measured from the
 * group's block, which is not sticky. The list body only, as in useScrollToId.
 *
 * It scrolls in its first frame, so no later request can overtake it; it only
 * starts a request with the `beginRequest` useScrollToId gets, so a row
 * request still waiting for its chunk gives up.
 */
export function useScrollToGroup(
  bodyRef: RefObject<HTMLDivElement | null>,
  beginRequest: () => () => boolean,
): (group: GroupKey) => void {
  return useCallback(
    (group: GroupKey) => {
      beginRequest();
      requestAnimationFrame(() => {
        const body = bodyRef.current;
        // Unreachable in practice: it guards an unmount racing the rAF.
        /* v8 ignore next 3 */
        if (!body) {
          return;
        }
        const block = findNode(body, groupDomId(group), ".listview-group");
        if (block === null) {
          return; // a rerun took the group away before this frame
        }
        const header = (
          block.firstElementChild as HTMLElement
        ).getBoundingClientRect().height;
        const box = block.getBoundingClientRect();
        const top = contentTop(body, box);
        if (top + header > body.scrollTop + body.clientHeight) {
          body.scrollTop = top + header - body.clientHeight;
        } else if (top + box.height - header < body.scrollTop) {
          body.scrollTop = top;
        }
      });
    },
    [bodyRef, beginRequest],
  );
}
