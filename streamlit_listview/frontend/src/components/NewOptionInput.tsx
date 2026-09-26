import { useState } from "react";
import type { FC, KeyboardEvent } from "react";

export interface NewOptionInputProps {
  disabled: boolean;
  /** Called with the trimmed, non-empty value the user wants to add. */
  onAdd: (value: string) => void;
}

/**
 * The `accept_new_options` entry row: a small input. Pressing Enter hands the
 * trimmed value to the container, which adds it to the selection; the new entry
 * then renders as a synthetic, selected row. Whitespace-only input is ignored.
 */
export const NewOptionInput: FC<NewOptionInputProps> = ({ disabled, onAdd }) => {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      return;
    }
    onAdd(trimmed);
    setValue("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    // An IME (Japanese/Chinese/Korean) commits its converted candidate with
    // Enter, so that Enter must not mean "add this option": submitting would add
    // the pre-conversion buffer, clear the field mid-composition, and — via
    // preventDefault() — swallow the IME's own commit, losing the user's text.
    // React's synthetic event omits the flag; the native one carries it. Caveat:
    // WebKit does not reliably dispatch the committing Enter to authors at all,
    // so there this guard is a no-op rather than a fix.
    if (event.nativeEvent.isComposing) {
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="listview-new-option">
      {/* inline plus glyph (no icon dependency); decorative only */}
      <svg
        className="listview-new-option__icon"
        data-testid="stListviewNewOptionIcon"
        viewBox="0 0 24 24"
        width="1em"
        height="1em"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M12 5v14M5 12h14"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
      <input
        type="text"
        aria-label="Add option"
        className="listview-new-option__input"
        data-testid="stListviewNewOption"
        placeholder="Add option"
        value={value}
        disabled={disabled}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
      />
    </div>
  );
};
