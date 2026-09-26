/**
 * Fold a string for case-insensitive matching, approximating Python's
 * str.casefold() (used by the sort) for the common European cases: a
 * locale-INDEPENDENT lowercase plus ß -> "ss" (which no built-in JS lowercase
 * performs). Without the ß fold, a query "STRASSE" would not match a "Straße"
 * label even though the casefolded sort treats them as equal.
 *
 * toLowerCase (NOT toLocaleLowerCase) is deliberate: it matches Python's
 * locale-independent casefold, so search and the sort agree everywhere, and it
 * avoids the Turkish/Azeri-locale trap where "I" would fold to dotless "ı" and
 * break ordinary ASCII matches (e.g. "FILE" vs "file").
 *
 * ONE definition, shared by the search filter (useFilter) and the
 * accept_new_options "is this already in the list?" lookup, because those two
 * answer the same question — "is this the same text?" — about the same rows. Two
 * copies drift: if the fold changed on one side only, what the user can FIND and
 * what the user can ADD would silently disagree, and typing the visible text of
 * a row the search does match would spawn a duplicate.
 *
 * Leading/trailing whitespace is folded away (a typed " apple " means the row
 * "apple"); internal whitespace is left alone, so a search for "a  b" does not
 * match "a b" and neither does an added option.
 */
import { get as getEmoji } from "node-emoji";
import {
  BRACKETED_DIRECTIVES,
  MATERIAL_ICON_TOKEN,
  STREAMLIT_LOGO_TOKEN,
} from "../markdown/streamlitPlugins";

// Hoisted out of the function below: a regex LITERAL is a fresh RegExp on every
// evaluation, and foldForMatch runs once per row (5000 allocations per fold pass
// at the design target). Sharing one is safe because String.replace resets a
// global regex's lastIndex, so no call can observe another's position.
const SHARP_S = /ß/g;

export function foldForMatch(value: string): string {
  return value.trim().toLowerCase().replace(SHARP_S, "ss");
}

// Only the directives the renderer actually claims reduce to their own text; the
// name list comes FROM the renderer (see BRACKETED_DIRECTIVES) rather than being
// re-spelled as `:[a-z]+(-[a-z]+)?` here. A pattern of its own would keep
// claiming names the renderer leaves literal: `:rainbow[Hi]` (rainbow has no
// token, so it renders as the text ":rainbow[Hi]") was announced as "Hi", and the
// two would drift apart again on the next palette edit.
//
// Case-SENSITIVE, like the renderer: canonicalColor matches its lowercase
// palette exactly and the shimmer/small checks compare literal names, so
// `:RED[Hot]` renders as the literal text ":RED[Hot]" and must be announced as
// such, not unwrapped to "Hot".
//
// The trailing group consumes an optional {foreground=… background=…} block so it
// never leaks into the name (":color[Fruit]{foreground=#f00}" -> "Fruit").
// Residual, and inherent to a stripper that does not re-run the renderer: a
// `:color[…]` whose attributes are absent or fail the CSS-color gate also renders
// literally, but is reduced here.
const CLAIMED_DIRECTIVE = new RegExp(
  `:(${BRACKETED_DIRECTIVES.join("|")})\\[([^\\]]*)\\](?:\\{[^}]*\\})?`,
  "g",
);

// The material-icon and :streamlit: token grammars come FROM the renderer
// (materialIconPreprocess compiles its sentinel rewrites from the same
// sources), for the same reason CLAIMED_DIRECTIVE above takes its names from
// BRACKETED_DIRECTIVES: a second spelling here would drift, stripping tokens
// the renderer leaves literal. Case-SENSITIVE, like the rewrite
// (":MATERIAL/check:" renders literally).
const MATERIAL_ICON_RE = new RegExp(MATERIAL_ICON_TOKEN, "g");
const STREAMLIT_LOGO_RE = new RegExp(STREAMLIT_LOGO_TOKEN, "g");

// A claimed directive with EMPTY brackets reduces to `:name` — the renderer's
// childless-directive guard bails on it and the literal-text cleanup emits only
// the `:name` prefix (`:red[]` parses identically to a bare `:red`, so the
// brackets are not part of what renders). Deleting the whole token here
// announced nothing where the user sees ":red".
function reduceClaimedDirective(
  _match: string,
  name: string,
  content: string,
): string {
  return content === "" ? `:${name}` : content;
}

// The exact token pattern remark-emoji scans for (its RE_EMOJI), so this
// stripper considers precisely the tokens the renderer would. Each token
// reduces to what the renderer leaves visible: the emoji character when
// node-emoji knows the shortcode, the literal token otherwise — a blanket
// delete announced "Standup 1245" for a label reading "Standup 12:30:45",
// whose ":30:" is no shortcode and renders untouched.
const EMOJI_SHORTCODE = /:\+1:|:-1:|:[\w-]+:/g;

function reduceEmojiShortcode(token: string): string {
  return getEmoji(token) ?? token;
}

/**
 * Reduce a label's Markdown to plain text for an accessible name, so a screen
 * reader announces "Pick a fruit" rather than the raw
 * "**Pick** a :red[fruit] :material/check:". Best-effort, inline-only.
 *
 * Shared by the help trigger's name ("Help for <label>") and the listbox's own
 * name, so the widget and its help affordance always announce the SAME label
 * text, and there is one stripper to fix when a directive is added.
 */
export function plainTextLabel(md: string): string {
  return md
    // Material icons and the Streamlit logo -> drop (grammars shared with the
    // renderer — see MATERIAL_ICON_RE above). Both render as iconography (an
    // icon span / an inline logo image), which this name has always omitted
    // rather than read out.
    .replace(MATERIAL_ICON_RE, "")
    .replace(STREAMLIT_LOGO_RE, "")
    .replace(CLAIMED_DIRECTIVE, reduceClaimedDirective) // :red[x] -> x, :red[] -> :red
    .replace(EMOJI_SHORTCODE, reduceEmojiShortcode) // :tada: -> 🎉, unknown -> literal
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1") // [text](url)/image -> text
    .replace(/[*~`]+/g, "") // bold/italic(*)/strike/code markers
    // Underscores: strip emphasis delimiters (_em_, __strong__) but KEEP
    // intraword underscores — CommonMark does not treat those as emphasis, so an
    // identifier like user_id must survive in the accessible name.
    .replace(/_+/g, (run, offset: number, str: string) => {
      const wordBefore = /\w/.test(str[offset - 1] ?? "");
      const wordAfter = /\w/.test(str[offset + run.length] ?? "");
      return wordBefore && wordAfter ? run : "";
    })
    .replace(/\s+/g, " ")
    .trim();
}
