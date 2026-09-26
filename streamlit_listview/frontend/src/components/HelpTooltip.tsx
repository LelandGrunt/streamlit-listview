import { useCallback, useId, useState } from "react";
import { flushSync } from "react-dom";
import type { FC } from "react";
import { Markdown } from "./Markdown";
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
 *   - closes on blur, mouse-leave, and Escape.
 *
 * Accessibility: the SVG is aria-hidden/focusable=false; the trigger button
 * carries the accessible name "Help for <label>"; while open, the trigger's
 * aria-describedby points at the popover (role="tooltip").
 */
export const HelpTooltip: FC<HelpTooltipProps> = ({ help, label }) => {
  // Hover and keyboard-focus are tracked independently and OR'd: releasing one
  // (e.g. the mouse leaving) must NOT close the popover while the other is still
  // active (e.g. the trigger is still keyboard-focused).
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const popoverId = useId();
  const open = hovered || focused;

  const showHover = useCallback(() => setHovered(true), []);
  const showFocus = useCallback(() => setFocused(true), []);
  // flushSync ensures the state update is applied synchronously so that callers
  // who invoke .blur()/unhover directly (e.g. test code, or browser focus moves
  // away) see the popover disappear without needing an await/act wrapper.
  const hideHover = useCallback(() => flushSync(() => setHovered(false)), []);
  const hideFocus = useCallback(() => flushSync(() => setFocused(false)), []);

  const onKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      setHovered(false);
      setFocused(false);
    }
  }, []);

  return (
    <div onMouseEnter={showHover} onMouseLeave={hideHover}>
      <button
        type="button"
        className="listview-help-trigger"
        aria-label={`Help for ${plainTextLabel(label)}`}
        aria-describedby={open ? popoverId : undefined}
        onFocus={showFocus}
        onBlur={hideFocus}
        onKeyDown={onKeyDown}
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
        >
          <Markdown source={help} tier="help" />
        </div>
      )}
    </div>
  );
};
