/**
 * Detection regex ported from Streamlit's
 * frontend/lib/src/components/shared/StreamlitMarkdown/utils.ts (Apache-2.0;
 * see root NOTICE).
 *
 * Our V2 single-file build forbids dynamic import() (it would emit a second JS
 * chunk and break the js="index-*.js" glob), so remark-emoji is statically
 * imported and this detector decides whether to INCLUDE it in the plugin array
 * for a given source — same behavior (the plugin only acts when its syntax is
 * present) without code-splitting. See Markdown.tsx. (LaTeX/KaTeX is not
 * supported — its fonts dominated the bundle — so no math detector is needed.)
 */

/**
 * True when `source` contains an emoji shortcode like `:tada:`, excluding the
 * Streamlit `:material/...:` icon and `:streamlit:` logo directives (handled by
 * dedicated remark plugins, not remark-emoji).
 */
export function containsEmojiShortcodes(source: string): boolean {
  return /:(?!material\/|streamlit:)[\w+-][\w_+-]*:/.test(source);
}
