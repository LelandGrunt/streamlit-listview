import { useLayoutEffect, useRef, useState } from "react";
import type { RefObject } from "react";

/** How far the popover keeps from the edges of its bounds, in CSS pixels. */
const EDGE_MARGIN_PX = 8;
/** The gap between the popover and its trigger, in rem: the 0.25rem in listview.css. */
const TRIGGER_GAP_REM = 0.25;
/** The root font size a browser falls back to, for a document that reports none (jsdom). */
const DEFAULT_ROOT_FONT_PX = 16;
/** The `overflow` values that clip an element's content. */
const CLIPPING_OVERFLOW = new Set(["auto", "scroll", "hidden", "clip"]);

/** Where the help popover opens and how much room it takes. */
export interface PopoverPlacement {
  /** Below the trigger rather than above it. */
  below: boolean;
  /** The height the popover may take on its side; null leaves the stylesheet's. */
  maxHeight: number | null;
  /** The width its bounds leave the popover; null leaves the stylesheet's. */
  maxWidth: number | null;
  /** The horizontal move, in CSS pixels, that keeps the popover in its bounds. */
  shift: number;
  /** Whether the help is taller than `maxHeight`, so the popover scrolls. */
  scrolls: boolean;
}

const UNPLACED: PopoverPlacement = {
  below: false,
  maxHeight: null,
  maxWidth: null,
  shift: 0,
  scrolls: false,
};

interface Bounds {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** The element above `node`, through a shadow boundary to the host. */
function ancestorOf(node: Element): Element | null {
  const parent = node.parentNode;
  if (parent instanceof Element) {
    return parent;
  }
  return parent instanceof ShadowRoot ? parent.host : null;
}

/**
 * The box the popover must stay in: the viewport, cut down by every ancestor
 * that clips its content. The viewport alone is not enough: a widget in the
 * sidebar sits in Streamlit's sidebar scroll box, and a popover kept inside
 * the viewport but outside that box is cut off, or gives the sidebar a
 * horizontal scrollbar. Null while the document has no layout (jsdom).
 */
function boundsOf(anchor: Element): Bounds | null {
  const viewport = document.documentElement;
  if (viewport.clientHeight === 0) {
    return null;
  }
  const bounds: Bounds = {
    left: 0,
    top: 0,
    right: viewport.clientWidth,
    bottom: viewport.clientHeight,
  };
  for (let node = ancestorOf(anchor); node !== null; node = ancestorOf(node)) {
    const { overflowX, overflowY } = getComputedStyle(node);
    if (CLIPPING_OVERFLOW.has(overflowX) || CLIPPING_OVERFLOW.has(overflowY)) {
      const box = node.getBoundingClientRect();
      bounds.left = Math.max(bounds.left, box.left);
      bounds.top = Math.max(bounds.top, box.top);
      bounds.right = Math.min(bounds.right, box.right);
      bounds.bottom = Math.min(bounds.bottom, box.bottom);
    }
  }
  return bounds;
}

/** The stylesheet's trigger gap in CSS pixels: rem follows the document root's font size. */
function triggerGapPx(): number {
  const rootFont = parseFloat(
    getComputedStyle(document.documentElement).fontSize,
  );
  return (
    (Number.isNaN(rootFont) ? DEFAULT_ROOT_FONT_PX : rootFont) * TRIGGER_GAP_REM
  );
}

/**
 * The placement that keeps the popover inside its bounds. It opens above the
 * trigger, like Streamlit's tooltip, while the help fits there, and otherwise
 * on the side with more room, where it takes at most that room and scrolls
 * the rest. Horizontally it stays right-aligned to the trigger until that
 * would cross an edge of the bounds, and it is never wider than the bounds.
 *
 * `body` is the popover's scrolling body, whose box is the popover's (the
 * popover has no padding of its own) and whose scrollHeight is the help's
 * full height. `appliedShift` is the shift the popover renders with now: the
 * box already includes it, and the new shift starts from the box without it.
 */
function placementFor(
  anchor: HTMLElement,
  body: HTMLElement,
  appliedShift: number,
): PopoverPlacement {
  const bounds = boundsOf(anchor);
  if (bounds === null) {
    return UNPLACED;
  }
  const gap = triggerGapPx();
  const { top, bottom } = anchor.getBoundingClientRect();
  const roomAbove = top - gap - EDGE_MARGIN_PX - bounds.top;
  const roomBelow = bounds.bottom - bottom - gap - EDGE_MARGIN_PX;
  const height = body.scrollHeight;
  const below = height > roomAbove && roomBelow > roomAbove;
  const maxHeight = Math.max(0, below ? roomBelow : roomAbove);
  const maxWidth = Math.max(0, bounds.right - bounds.left - 2 * EDGE_MARGIN_PX);
  const box = body.getBoundingClientRect();
  const shift = Math.min(
    Math.max(0, bounds.left + EDGE_MARGIN_PX - (box.left - appliedShift)),
    bounds.right - EDGE_MARGIN_PX - (box.right - appliedShift),
  );
  return { below, maxHeight, maxWidth, shift, scrolls: height > maxHeight };
}

function samePlacement(a: PopoverPlacement, b: PopoverPlacement): boolean {
  return (
    a.below === b.below &&
    a.maxHeight === b.maxHeight &&
    a.maxWidth === b.maxWidth &&
    a.shift === b.shift &&
    a.scrolls === b.scrolls
  );
}

/**
 * Places the help popover while it is open (see `placementFor`). It measures
 * in a layout effect, so the first frame already shows the popover in place;
 * again on every scroll (of any scroll container: the listener captures) and
 * resize, because the trigger moves with the page; again when the body's size
 * changes (an image in the help that loads after the first measurement); and
 * once more after a new width cap has applied, because the shift was measured
 * on the old width. A placement equal to the current one re-renders nothing.
 *
 * Positioning stays in the stylesheet's hands: the popover keeps its absolute
 * position inside the label's shadow root (no portal), so it inherits the
 * theme's `--st-*` properties; this only picks the side, caps the size and
 * shifts it sideways.
 */
export function usePopoverPlacement(
  open: boolean,
  anchorRef: RefObject<HTMLElement | null>,
  bodyRef: RefObject<HTMLElement | null>,
  content: string,
): PopoverPlacement {
  const [placement, setPlacement] = useState(UNPLACED);
  const shiftRef = useRef(0);
  const appliedMaxWidth = placement.maxWidth;
  useLayoutEffect(() => {
    if (!open) {
      return undefined;
    }
    const body = bodyRef.current as HTMLElement;
    const place = () => {
      const next = placementFor(
        anchorRef.current as HTMLElement,
        body,
        shiftRef.current,
      );
      shiftRef.current = next.shift;
      setPlacement((current) =>
        samePlacement(current, next) ? current : next,
      );
    };
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    // Absent in jsdom and old engines: the popover then keeps its first size.
    const observer =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(place);
    observer?.observe(body);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
      observer?.disconnect();
    };
  }, [open, content, appliedMaxWidth, anchorRef, bodyRef]);
  return placement;
}
