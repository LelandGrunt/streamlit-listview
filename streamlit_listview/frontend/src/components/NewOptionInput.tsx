import { useId, useState } from "react";
import type { FC, KeyboardEvent } from "react";

export interface NewOptionInputProps {
  disabled: boolean;
  /**
   * Called with the trimmed, non-empty value the user wants to add. Returns
   * `null` when the value was taken — added, matched to an existing row, or
   * ignored at the cap — and otherwise the hint that says why it was refused.
   * The rule lives with the caller, which knows what the options accept.
   */
  onAdd: (value: string) => string | null;
}

/**
 * The `accept_new_options` entry row: a small input. Pressing Enter hands the
 * trimmed value to the container, which adds it to the selection; the new entry
 * then renders as a synthetic, selected row. Whitespace-only input is ignored.
 * A refused value stays in the field, and the container's hint shows below the
 * row until the text changes.
 */
export const NewOptionInput: FC<NewOptionInputProps> = ({ disabled, onAdd }) => {
  const [value, setValue] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  // Counts refusals, to key the hint's node: a second Enter on the same refused
  // text sets the same hint, which changes nothing in the DOM, so the live
  // region would stay silent. A new key mounts a new node, which it announces.
  const [refusals, setRefusals] = useState(0);
  const hintId = useId();

  const submit = () => {
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      return;
    }
    const refusal = onAdd(trimmed);
    if (refusal !== null) {
      // Keep the text so the user can correct it, and say what was wrong.
      setHint(refusal);
      setRefusals((n) => n + 1);
      return;
    }
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
    <>
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
          aria-invalid={hint !== null || undefined}
          aria-describedby={hint !== null ? hintId : undefined}
          className="listview-new-option__input"
          data-testid="stListviewNewOption"
          placeholder="Add option"
          value={value}
          disabled={disabled}
          onChange={(e) => {
            setValue(e.target.value);
            setHint(null);
          }}
          onKeyDown={onKeyDown}
        />
      </div>
      {/* Below the row, not inside it: the plus glyph is absolutely positioned
          and centres on the row's height, so a second line inside the row
          would pull it down. A role="status" live region that stays in the DOM
          and is filled only on a refusal: focus stays in the input, and a
          screen reader announces only a change to a region it already tracks.
          The stylesheet pads it only when filled, so empty it has no height. */}
      <div
        id={hintId}
        role="status"
        className="listview-new-option__hint"
        data-testid="stListviewNewOptionHint"
      >
        {hint !== null && <span key={refusals}>{hint}</span>}
      </div>
    </>
  );
};
