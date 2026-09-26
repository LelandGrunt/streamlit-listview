import { memo } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import type { PluggableList } from "unified";
import remarkGfm from "remark-gfm";
import remarkDirective from "remark-directive";
// Emoji is statically imported and conditionally INCLUDED in the plugin array
// only when the source contains an emoji shortcode — never dynamic-imported
// (that would split a second JS chunk and break the single-file js="index-*.js"
// glob). LaTeX/KaTeX is intentionally NOT supported (its fonts dominated the
// bundle: ~1.44 MB of inlined CSS); `$…$` renders as literal text.
import remarkEmoji from "remark-emoji";

import {
  LABEL_DISALLOWED_ELEMENTS,
  escapeLabelSource,
  materialIconPreprocess,
  createRemarkColoringAndSmall,
  createRemarkMaterialIcons,
  createRemarkStreamlitLogo,
  createRemarkRestoreIconSentinels,
  createRemarkTypographicalSymbols,
  createRemarkUnsupportedDirectivesCleanup,
} from "../markdown/streamlitPlugins";
import { LinkWithTargetBlank, transformUri } from "../markdown/links";
import { containsEmojiShortcodes } from "../markdown/detect";

export interface MarkdownProps {
  source: string;
  tier: "label" | "help";
}

const COMPONENTS: Components = {
  a: LinkWithTargetBlank,
};

/**
 * react-markdown wrapper matching Streamlit's StreamlitMarkdown.
 *
 * - tier="label": restricted inline tier — block elements blocklisted via
 *   disallowedElements + unwrapDisallowed, and leading block markers
 *   backslash-escaped before parsing (escapeLabelSource).
 * - tier="help": full GitHub-flavored Markdown, no blocklist, source unescaped.
 *
 * materialIconPreprocess rewrites :material/<name>: and :streamlit: in the SOURCE
 * (both tiers) to colon-free Private-Use sentinels before parsing, so the matching
 * createRemarkMaterialIcons / createRemarkStreamlitLogo plugins fire even when a
 * token is glued to an adjacent word (remark-directive can't fragment a sentinel).
 * transformUri is passed as urlTransform so dangerous schemes are sanitized BEFORE
 * react-markdown's `a` override runs.
 *
 * remark-emoji is STATICALLY imported but only placed in the plugin array when
 * the source contains an emoji shortcode (see detect.ts). No dynamic import() ->
 * the build stays a single JS chunk. LaTeX math is not supported (see imports).
 *
 * Output is wrapped in an element with className="listview-markdown" so
 * listview.css (which scopes every markdown rule under .listview-markdown)
 * matches the DOM. The label tier uses a <span> (inline-only); the help tier
 * uses a <div> because it renders block elements.
 *
 * memo() is load-bearing, not a micro-optimization: react-markdown v10 builds its
 * unified processor and runs parse + runSync in its own RENDER BODY, with no
 * internal memoization, so a re-render re-freezes a nine-plugin pipeline and
 * re-parses the label from scratch. WidgetLabel re-renders on every Listview
 * render — i.e. on every click and every keystroke — and memoizing the `text` and
 * `remarkPlugins` inputs did NOT prevent that (stable props do not stop React from
 * re-rendering the child; only a bail-out does). Both props here are primitives,
 * so the shallow comparison is exact and the parse happens once per label.
 */
export const Markdown = memo(function Markdown({ source, tier }: MarkdownProps) {
  const isLabel = tier === "label";
  // Material-icon rewrite runs for BOTH tiers; in the label tier it is applied
  // AFTER escapeLabelSource (escaping leading block markers does not touch the
  // :material/ token).
  const text = isLabel
    ? materialIconPreprocess(escapeLabelSource(source))
    : materialIconPreprocess(source);

  // Fresh per render, which memo() has already reduced to "once per label": there
  // is nothing to cache for, since react-markdown rebuilds its processor from
  // these regardless of whether the array is the same one.
  const remarkPlugins: PluggableList = [
    remarkGfm,
    remarkDirective,
    createRemarkColoringAndSmall(),
    createRemarkMaterialIcons(),
    createRemarkStreamlitLogo(),
    // After the icon/logo plugins: restore any sentinel that survived inside a
    // code node (findAndReplace skips code) to its readable literal source.
    createRemarkRestoreIconSentinels(),
    createRemarkTypographicalSymbols(),
  ];
  if (containsEmojiShortcodes(source)) {
    remarkPlugins.push(remarkEmoji);
  }
  // ALWAYS last: turn any leftover unsupported directives into literal text.
  remarkPlugins.push(createRemarkUnsupportedDirectivesCleanup());

  // No rehype plugins: never rehype-raw (no unsafe_allow_html — raw HTML stays
  // escaped), and LaTeX/KaTeX is not supported.

  // The help tier emits block elements (h2/p/ul/table/blockquote/hr), which are
  // invalid inside a <span>; wrap it in a <div>. The label tier is inline-only
  // (block elements are blocklisted), so it stays a <span>.
  const Wrapper = isLabel ? "span" : "div";
  return (
    <Wrapper className="listview-markdown">
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        components={COMPONENTS}
        urlTransform={transformUri}
        {...(isLabel
          ? {
              disallowedElements: LABEL_DISALLOWED_ELEMENTS,
              unwrapDisallowed: true,
            }
          : {})}
      >
        {text}
      </ReactMarkdown>
    </Wrapper>
  );
});
