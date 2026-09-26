import { memo } from "react";
import type { CSSProperties, FC } from "react";
import type { LabelVisibility } from "../types";
import { Markdown } from "./Markdown";
import { HelpTooltip } from "./HelpTooltip";
import { plainTextLabel } from "../utils/text";

export interface WidgetLabelProps {
  /** Raw label Markdown text. Rendered via the restricted (label) tier. */
  label: string;
  /** Raw help Markdown text or null. Rendered via the full (help) tier in the tooltip. */
  help: string | null;
  labelVisibility: LabelVisibility;
  disabled: boolean;
  /**
   * DOM id for the accessible-name copy of the label. The container points the
   * listbox's aria-labelledby at it, so this is what names the widget — required,
   * because a listbox with no accessible name fails WCAG 4.1.2.
   */
  textId: string;
}

/**
 * Streamlit WidgetLabel replica (Milestone B: Markdown).
 *
 * label_visibility:
 *   - "visible"   -> flex row, help tooltip shown when help is set
 *   - "hidden"    -> visibility:hidden (keeps layout space)
 *   - "collapsed" -> display:none (removed from layout)
 *
 * The visible label renders through the restricted Markdown tier inside an
 * aria-hidden span (Streamlit likewise keeps its label markdown out of the a11y
 * tree and names the control itself), plus a screen-reader-only span that carries
 * `textId` and supplies the listbox's accessible name — see the note on that span
 * below for why the name cannot simply reference the visible one.
 *
 * The help affordance is delegated entirely to HelpTooltip, which owns the
 * HelpCircle SVG and the hover/focus popover (full Markdown tier).
 */
const WidgetLabelImpl: FC<WidgetLabelProps> = ({
  label,
  help,
  labelVisibility,
  disabled,
  textId,
}) => {
  const style: CSSProperties = {
    display: labelVisibility === "collapsed" ? "none" : "flex",
    visibility: labelVisibility === "hidden" ? "hidden" : "visible",
  };

  const showHelp = labelVisibility === "visible" && help != null;

  const className =
    "listview-widget-label" +
    (disabled ? " listview-widget-label--disabled" : "");

  return (
    <>
      {/*
       * The widget's accessible name. It lives OUTSIDE the label row and is only
       * clipped out of the layout, because the row itself cannot supply a name in
       * every mode: at label_visibility "hidden" the row is visibility:hidden and
       * CSS visibility inherits into the referenced subtree (a hidden subtree
       * contributes nothing to the name, so the widget goes unnamed), and at
       * "collapsed" the row is display:none. aria-hidden keeps this copy from
       * being announced as loose text — a node referenced DIRECTLY by
       * aria-labelledby still contributes its text — so the name is announced
       * exactly once, as the listbox's name.
       *
       * It holds the label's STRIPPED text (plainTextLabel), not a second
       * <Markdown> render of `label`: rendering the same markdown twice per
       * instance doubled the react-markdown work and the DOM of every widget, and
       * the stripper already exists for the help trigger's "Help for <label>"
       * name. Sharing it is what keeps the widget and its help affordance
       * announcing the same words, instead of two independently-derived
       * reductions of one label. The tradeoff is that `:material/icon:` and
       * `:streamlit:` drop out of the name rather than reducing to their icon
       * text — which is exactly how the help trigger has always named them.
       */}
      <span
        className="listview-widget-label__a11y-name"
        id={textId}
        aria-hidden="true"
      >
        {plainTextLabel(label)}
      </span>
      <div
        className={className}
        data-testid="listview-widget-label"
        style={style}
      >
        <span className="listview-widget-label__text" aria-hidden="true">
          <Markdown source={label} tier="label" />
        </span>
        {showHelp && (
          <div className="listview-widget-label__help-slot">
            <HelpTooltip help={help} label={label} />
          </div>
        )}
      </div>
    </>
  );
};

/**
 * Memoized because the container re-renders it on every click and every search
 * keystroke while none of its five props change. All five are primitives, so the
 * shallow compare is exact — and one bail-out here covers everything the label
 * costs: the `plainTextLabel` strip above, the second strip inside HelpTooltip's
 * "Help for <label>" name, the <Markdown> child, and the label row's DOM.
 */
export const WidgetLabel = memo(WidgetLabelImpl);
