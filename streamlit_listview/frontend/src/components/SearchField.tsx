import type { FC, KeyboardEvent } from "react";

export interface SearchFieldProps {
  value: string;
  placeholder: string;
  disabled: boolean;
  onChange: (value: string) => void;
  /** Called when Escape is pressed inside the input. */
  onEscape?: () => void;
  /** Forwarded to the <input> so the container can focus it (e.g. on "/"). */
  inputRef?: React.Ref<HTMLInputElement>;
}

/**
 * Search box: a themed text input plus a clear (×) button shown only when there
 * is text. Placement (pinned header strip vs in-flow top of the scroll body) is
 * decided by the container; this component is placement-agnostic.
 */
export const SearchField: FC<SearchFieldProps> = ({
  value,
  placeholder,
  disabled,
  onChange,
  onEscape,
  inputRef,
}) => {
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    // While an IME composition is active, Escape discards the candidate rather
    // than meaning "clear the search" — running onEscape would wipe the whole
    // query instead. React's synthetic event omits the flag; the native one
    // carries it. Caveat: WebKit does not reliably dispatch composition keydowns
    // to authors, so there this guard is a no-op rather than a fix.
    if (event.nativeEvent.isComposing) {
      return;
    }
    if (event.key === "Escape" && onEscape) {
      event.preventDefault();
      onEscape();
    }
  };

  const clearAndRefocus = () => {
    onChange("");
    // The clear button unmounts once the value is empty (it only renders while
    // value.length > 0), which would drop focus to <body>; return focus to the
    // input so a keyboard user keeps their place.
    if (inputRef && typeof inputRef === "object") {
      inputRef.current?.focus();
    }
  };

  return (
    <div className="listview-search">
      {/* inline magnifying-glass glyph (no icon dependency); decorative only */}
      <svg
        className="listview-search__icon"
        data-testid="stListviewSearchIcon"
        viewBox="0 0 24 24"
        width="1em"
        height="1em"
        aria-hidden="true"
        focusable="false"
      >
        <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" strokeWidth="2" />
        <path
          d="M15.5 15.5L21 21"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
      <input
        ref={inputRef}
        type="text"
        role="searchbox"
        aria-label="Search"
        className="listview-search__input"
        data-testid="stListviewSearch"
        placeholder={placeholder}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
      />
      {value.length > 0 && (
        <button
          type="button"
          className="listview-search__clear"
          data-testid="stListviewSearchClear"
          aria-label="Clear search"
          disabled={disabled}
          onClick={clearAndRefocus}
        >
          {/* inline glyph (no icon dependency) */}
          <svg viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true" focusable="false">
            <path
              d="M6 6l12 12M18 6L6 18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
      )}
    </div>
  );
};
