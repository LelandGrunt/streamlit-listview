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
import { elementAt } from "./arrays";
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

// What renders verbatim, and so must reach the name verbatim: a code span's
// content, a backslash-escaped ASCII punctuation character and a backtick run
// that closes no code span. Matched left to right, as CommonMark reads them:
// an escape first, then a code span — an opening run that closes at the next
// run of EXACTLY its length — then a lone run. The lookarounds keep both runs
// whole: without the one after the opening run, "``a`" backtracked to an
// opening "`" and read "`a" as code. A code span shows no emphasis, icon,
// emoji or directive, so stripping its markers like the rest of the label
// left "`*`" without a name and announced "`__init__`" as "init".
const LITERAL_SOURCE =
  /\\([!-/:-@[-`{-~])|(`+)(?!`)([\s\S]*?)(?<!`)\2(?!`)|`+/g;

// Each literal crosses the strip passes below as a placeholder: a marker and
// two characters that encode its index (up to 65,536 literals). None of the
// passes matches a Private-Use character, so a placeholder moves only as
// text around it does, and one inside a link's URL leaves with the URL. The
// marker is removed from the source first, so a label cannot forge one.
const LITERAL_MARK = "\uE010";
const INDEX_BASE = 0xe100;
const LITERAL_RE = /\uE010([\uE100-\uE1FF])([\uE100-\uE1FF])/g;

/** A code span's text as CommonMark renders it (line endings become spaces, one space trimmed from each end). */
function codeSpanText(code: string): string {
  const text = code.replace(/\r\n|\r|\n/g, " ");
  const padded = text.startsWith(" ") && text.endsWith(" ");
  return padded && /[^ ]/.test(text) ? text.slice(1, -1) : text;
}

function protectLiterals(md: string, literals: string[]): string {
  return md
    .replaceAll(LITERAL_MARK, "")
    .replace(
      LITERAL_SOURCE,
      (match, escaped?: string, fence?: string, code?: string) => {
        // A fence always comes with its (possibly empty) code group.
        const literal =
          escaped ??
          (fence === undefined ? match : codeSpanText(code as string));
        const index = literals.push(literal) - 1;
        return (
          LITERAL_MARK +
          String.fromCharCode(
            INDEX_BASE + (index >> 8),
            INDEX_BASE + (index & 0xff),
          )
        );
      },
    );
}

function restoreLiterals(text: string, literals: string[]): string {
  return text.replace(LITERAL_RE, (_match, high: string, low: string) =>
    elementAt(
      literals,
      ((high.charCodeAt(0) - INDEX_BASE) << 8) + low.charCodeAt(0) - INDEX_BASE,
    ),
  );
}

// A run of `*`, `~` or `_` emphasizes (or strikes through) only where it
// touches text: with whitespace or the label's edge on BOTH sides it renders
// literally ("2 * 3", "a ~ b", and the leading "* " escapeLabelSource keeps).
// CommonMark also never reads an intraword `_` as emphasis, so an identifier
// like user_id survives; an intraword `*` does emphasize.
function reduceMarkerRun(run: string, offset: number, str: string): string {
  const before = str[offset - 1] ?? " ";
  const after = str[offset + run.length] ?? " ";
  if (/\s/.test(before) && /\s/.test(after)) {
    return run;
  }
  const intraword = /\w/.test(before) && /\w/.test(after);
  return run.startsWith("_") && intraword ? run : "";
}

/**
 * Reduce a label's Markdown to plain text for an accessible name, so a screen
 * reader announces "Pick a fruit" rather than the raw
 * "**Pick** a :red[fruit] :material/check:". Best-effort, inline-only.
 *
 * Shared by the help trigger's name ("Help for <label>") and the listbox's own
 * name, so the widget and its help affordance always announce the SAME label
 * text, and there is one stripper to fix when a directive is added.
 *
 * Code spans, escaped punctuation and unmatched backticks keep their text
 * (see LITERAL_SOURCE); everything else goes through the strip passes.
 */
export function plainTextLabel(md: string): string {
  const literals: string[] = [];
  const stripped = protectLiterals(md, literals)
    // Material icons and the Streamlit logo -> drop (grammars shared with the
    // renderer — see MATERIAL_ICON_RE above). Both render as iconography (an
    // icon span / an inline logo image), which this name has always omitted
    // rather than read out.
    .replace(MATERIAL_ICON_RE, "")
    .replace(STREAMLIT_LOGO_RE, "")
    .replace(CLAIMED_DIRECTIVE, reduceClaimedDirective) // :red[x] -> x, :red[] -> :red
    .replace(EMOJI_SHORTCODE, reduceEmojiShortcode) // :tada: -> 🎉, unknown -> literal
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1") // [text](url)/image -> text
    .replace(/[*~]+|_+/g, reduceMarkerRun); // emphasis and strikethrough markers
  return restoreLiterals(stripped, literals).replace(/\s+/g, " ").trim();
}
