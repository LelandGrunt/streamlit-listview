import { useCallback, useId, useRef, useState } from "react";
import { flushSync } from "react-dom";
import type { CSSProperties, FC, FocusEvent, KeyboardEvent } from "react";
import { Markdown } from "./Markdown";
import { usePopoverPlacement } from "../hooks/usePopoverPlacement";
import { plainTextLabel } from "../utils/text";

export interface HelpTooltipProps {
  /** Raw help Markdown text. Rendered via the full (help) Markdown tier. */
  help: string;
  /** Raw label Markdown; markdown syntax is stripped for the accessible name. */
  label: string;
}

/**
 * Streamlit help-affordance replica (point-in-time): the react-feather
 * `HelpCircle` inline SVG (Apache/MIT attribution in NOTICE) inside a
 * borderless trigger button, plus a hand-rolled hover/focus popover — no
 * BaseWeb / no third-party tooltip dependency.
 *
 * Open semantics (match Streamlit's TooltipIcon):
 *   - opens on pointer hover AND on keyboard focus of the trigger;
 *   - closes on mouse-leave, on Escape, and when the focus leaves the trigger
 *     and the popover. The focus may move INTO the popover: help can hold
 *     links, and Tab from the trigger reaches them, because the popover
 *     follows the trigger in the DOM.
 *
 * Placement: above the trigger while the help fits there, else on the side
 * with more room, capped to the viewport and scrolled inside
 * (usePopoverPlacement). A popover that scrolls takes the keyboard focus, so
 * the arrow keys can scroll it too.
 *
 * Accessibility: the SVG is aria-hidden/focusable=false; the trigger button
 * carries the accessible name "Help for <label>"; while open, the trigger's
 * aria-describedby points at the popover (role="tooltip").
 */
export const HelpTooltip: FC<HelpTooltipProps> = ({ help, label }) => {
  // Hover and focus are tracked independently and OR'd: releasing one (e.g. the
  // mouse leaving) must NOT close the popover while the other is still active
  // (e.g. the trigger or a link in the help is still keyboard-focused).
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const popoverId = useId();
  const open = hovered || focused;
  const anchorRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const placement = usePopoverPlacement(open, anchorRef, bodyRef, help);

  const showHover = useCallback(() => setHovered(true), []);
  const showFocus = useCallback(() => setFocused(true), []);
  // flushSync ensures the state update is applied synchronously so that callers
  // who invoke .blur()/unhover directly (e.g. test code, or browser focus moves
  // away) see the popover disappear without needing an await/act wrapper.
  const hideHover = useCallback(() => flushSync(() => setHovered(false)), []);
  // The focus counts for the whole help: the trigger and the popover. A move
  // between the two keeps it open. Closing on the trigger's own blur unmounted
  // the popover before Tab could land on a link in it, and the focus fell to
  // <body>.
  const hideFocus = useCallback((event: FocusEvent<HTMLDivElement>) => {
    const next = event.relatedTarget;
    if (next instanceof Node && event.currentTarget.contains(next)) {
      return;
    }
    flushSync(() => setFocused(false));
  }, []);

  const onKeyDown = useCallback((event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      // From inside the popover, the focus would go down with it: hand it
      // back to the trigger first (a no-op when the trigger has it).
      (triggerRef.current as HTMLButtonElement).focus();
      setHovered(false);
      setFocused(false);
    }
  }, []);

  // The width cap goes through a custom property, so the stylesheet keeps its
  // own 20rem cap beside it (an inline max-width would replace it).
  const popoverStyle = {
    transform:
      placement.shift === 0 ? undefined : `translateX(${placement.shift}px)`,
    "--listview-popover-max-width":
      placement.maxWidth === null ? undefined : `${placement.maxWidth}px`,
  } as CSSProperties;

  return (
    <div
      ref={anchorRef}
      onMouseEnter={showHover}
      onMouseLeave={hideHover}
      onFocus={showFocus}
      onBlur={hideFocus}
      onKeyDown={onKeyDown}
    >
      <button
        ref={triggerRef}
        type="button"
        className="listview-help-trigger"
        aria-label={`Help for ${plainTextLabel(label)}`}
        aria-describedby={open ? popoverId : undefined}
      >
        <svg
          className="listview-help-icon"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          focusable="false"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </button>
      {open && (
        <div
          id={popoverId}
          role="tooltip"
          className="listview-help-popover"
          data-placement={placement.below ? "below" : "above"}
          style={popoverStyle}
        >
          {/* The body scrolls, not the popover: a scrolling popover would
              clip its own hover bridge, which lies outside its box. */}
          <div
            ref={bodyRef}
            className="listview-help-popover__body"
            tabIndex={placement.scrolls ? 0 : undefined}
            style={{ maxHeight: placement.maxHeight ?? undefined }}
          >
            <Markdown source={help} tier="help" />
          </div>
        </div>
      )}
    </div>
  );
};
