/**
 * Ported Streamlit remark directive plugins + label helpers.
 *
 * Faithfully ported from Streamlit's StreamlitMarkdown.tsx (Apache-2.0,
 * attributed in /NOTICE), with ONE deliberate adaptation: Streamlit injects
 * resolved theme colors from a JS EmotionTheme object. We have no JS theme
 * object — our colors live in --st-* CSS custom properties in listview.css.
 * So colored / background / badge directives emit OUR own class scheme
 *   <span class="listview-md-color listview-md-color--<name>">      (text)
 *   <span class="listview-md-bg listview-md-bg--<name>">            (background)
 *   <span class="listview-md-badge listview-md-badge--<name>">      (badge)
 *   <span class="listview-md-small">  /  <span class="listview-md-shimmer">
 * and listview.css (owned by area css-notice) maps each modifier class to the
 * matching --st-<name>-* token. For an ARBITRARY CSS color (the directive's
 * {foreground=… background=…} attributes) the span carries an inline `style`
 * instead of a modifier class. Producer (this file) and consumer (listview.css)
 * agree on this exact class scheme; the <name> set is
 * red/orange/yellow/green/blue/violet/gray, with `grey` accepted as an alias of
 * `gray`. Which spans wrap which content matches Streamlit exactly.
 */
import { visit } from "unist-util-visit";
import { findAndReplace } from "mdast-util-find-and-replace";
import type { Nodes, PhrasingContent, Root, Text } from "mdast";
// Importing from mdast-util-directive also loads its module augmentation, so
// TextDirective (and siblings) are recognised by the production tsc program.
// Without it the production tsconfig has nothing in src/ importing directive
// types, narrowing the `visit` node to `never` and causing TS2339 errors.
import type {
  Directives,
  LeafDirective,
  TextDirective,
} from "mdast-util-directive";

/**
 * Replace ASCII shorthands with typographical symbols in plain text nodes.
 * Skips text inside link / linkReference targets so URLs are not mangled.
 * Ported verbatim (regex + replacement chars) from Streamlit.
 */
// The trailing boundary is a lookahead `(?=\s|$)`, NOT a captured `(\s|$)`: a
// consumed trailing space would be unavailable as the leading boundary of an
// immediately adjacent match, so "-- --" would convert only the first dash pair.
// Hoisted to module scope so the regexes compile once rather than per text node.
const TYPOGRAPHICAL_REPLACEMENTS: [RegExp, string][] = [
  [/(^|\s)<->(?=\s|$)/g, "$1↔"],
  [/(^|\s)->(?=\s|$)/g, "$1→"],
  [/(^|\s)<-(?=\s|$)/g, "$1←"],
  [/(^|\s)--(?=\s|$)/g, "$1—"],
  [/(^|\s)>=(?=\s|$)/g, "$1≥"],
  [/(^|\s)<=(?=\s|$)/g, "$1≤"],
  [/(^|\s)~=(?=\s|$)/g, "$1≈"],
];

export function createRemarkTypographicalSymbols() {
  return () => (tree: Root) => {
    visit(tree, (node, _index, parent) => {
      if (
        parent &&
        (parent.type === "link" || parent.type === "linkReference")
      ) {
        return;
      }
      if (node.type === "text" && node.value) {
        let newValue = node.value;
        for (const [pattern, replacement] of TYPOGRAPHICAL_REPLACEMENTS) {
          newValue = newValue.replace(pattern, replacement);
        }
        if (newValue !== node.value) {
          node.value = newValue;
        }
      }
    });
    return tree;
  };
}

/**
 * Canonical Streamlit colored-text / badge palette. Each name maps 1:1 to
 * --st-<name>-text-color / --st-<name>-background-color tokens defined in
 * listview.css. `grey` is accepted on input and normalized to `gray`, so only
 * these canonical names are ever emitted in a listview-md-*--<name> class.
 * `rainbow`/`primary` are intentionally unsupported (they have no token here),
 * so a `:rainbow[…]` / `:rainbow-badge[…]` directive falls through to the
 * unsupported-directive cleanup and renders as literal text.
 */
export const MARKDOWN_COLORS = [
  "red",
  "orange",
  "yellow",
  "green",
  "blue",
  "violet",
  "gray",
] as const;
type MarkdownColor = (typeof MARKDOWN_COLORS)[number];

/** Map an input color name (incl. the `grey` alias) to a canonical token, or undefined. */
function canonicalColor(name: string): MarkdownColor | undefined {
  const normalized = name === "grey" ? "gray" : name;
  return (MARKDOWN_COLORS as readonly string[]).includes(normalized)
    ? (normalized as MarkdownColor)
    : undefined;
}

/**
 * Every bracketed directive name this renderer CLAIMS — i.e. turns into a span
 * instead of leaving as literal text. Derived from the palette above rather than
 * listed by hand, so a color added there is claimed here too.
 *
 * Exported for `plainTextLabel` (utils/text), which reduces a label to its
 * accessible name and must reduce exactly the directives that render as
 * formatting: a name it strips but this renderer leaves literal announces
 * something the user cannot see (`:rainbow[Hi]` renders as ":rainbow[Hi]" —
 * rainbow is deliberately unsupported — and must not be announced as "Hi").
 *
 * Longest-first, so the alternation built from it prefers `red-badge` over `red`.
 */
const COLOR_NAMES = [...MARKDOWN_COLORS, "grey"];
export const BRACKETED_DIRECTIVES: string[] = [
  ...COLOR_NAMES.flatMap((name) => [`${name}-background`, `${name}-badge`]),
  ...COLOR_NAMES,
  "shimmer",
  "small",
  "color",
];

// Strict CSS <color> grammar for the arbitrary-color directive attributes
// (:color[…]{foreground=… background=…}). remark-directive parses a QUOTED
// attribute value verbatim — including ';', ':', spaces and url(...) — so the
// raw value must never be interpolated into an inline `style` string unchecked:
// that is a CSS-injection sink (clickjacking overlays via position/z-index,
// resource-load beacons via background-image:url()). Accept only a single
// well-formed color token; reject anything carrying a declaration-breakout
// character. Covers:
//   - hex:        #rgb #rgba #rrggbb #rrggbbaa
//   - functional: rgb()/rgba()/hsl()/hsla() with numeric / % / whitespace / ',' '/'
//   - keyword:    a bare CSS identifier (named colors, transparent, currentColor)
const HEX_COLOR_RE = /^#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
const FUNCTIONAL_COLOR_RE = /^(?:rgb|rgba|hsl|hsla)\(\s*[0-9.,%\s/]+\)$/i;
const KEYWORD_COLOR_RE = /^[a-z]+$/i;

/**
 * True when `value` is a single, well-formed CSS color token safe to drop into
 * an inline `style`. An invalid value is rejected (and then dropped by the
 * caller) rather than sanitized, so a multi-declaration payload can never
 * contribute extra CSS.
 */
function isSafeCssColor(value: string): boolean {
  const v = value.trim();
  return (
    HEX_COLOR_RE.test(v) ||
    FUNCTIONAL_COLOR_RE.test(v) ||
    KEYWORD_COLOR_RE.test(v)
  );
}

/**
 * Handle the inline Streamlit color/format directives, emitting OUR class scheme:
 *   :shimmer[…]                -> span.listview-md-shimmer
 *   :small[…]                  -> span.listview-md-small
 *   :color[…]                  -> span.listview-md-color  .listview-md-color--<name>
 *   :color-background[…]       -> span.listview-md-bg     .listview-md-bg--<name>
 *   :color-badge[…]            -> span.listview-md-badge   .listview-md-badge--<name>
 *   :color[…]{foreground=… background=…}
 *                              -> span.listview-md-color|listview-md-bg with inline
 *                                 style (arbitrary CSS colors, no modifier class)
 * Adapted from Streamlit: OUR modifier classes replace the JS theme color lookup;
 * `grey` is normalized to `gray` so only canonical token names reach listview.css.
 */
export function createRemarkColoringAndSmall() {
  return () => (tree: Root) => {
    visit(tree, "textDirective", (node) => {
      const nodeName = String(node.name);
      const data = node.data || (node.data = {});
      const setSpan = (className: string) => {
        data.hName = "span";
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const props: any = data.hProperties || {};
        props.className = className;
        data.hProperties = props;
        return props as Record<string, unknown>;
      };

      // A directive with NO children is prose the author typed, not a formatting
      // request: remark-directive still parses the name out of "Ampel :red",
      // "key:blue value" or ":red[unterminated", and claiming it here would emit
      // an EMPTY span and DELETE the visible ":red" from the output. Bail out so
      // the unsupported-directive cleanup renders it literally instead.
      // DELIBERATE divergence: upstream Streamlit's guard has this same shape and
      // does eat the text. We diverge in the direction this file already diverges
      // below (its cleanup keeps the directive's children where Streamlit's drops
      // them) — never silently losing the author's text wins over exact parity.
      // Note `:red[]` parses identically to a bare `:red`, so the empty brackets
      // are (unavoidably) not part of the literal text that gets rendered.
      if (node.children.length === 0) {
        return;
      }

      // :shimmer[…]
      if (nodeName === "shimmer") {
        setSpan("listview-md-shimmer");
        return;
      }

      // :small[…]
      if (nodeName === "small") {
        setSpan("listview-md-small");
        return;
      }

      // :color[…] with arbitrary CSS colors via {foreground=… background=…}
      if (nodeName === "color" && node.attributes) {
        const { foreground, background } = node.attributes as {
          foreground?: string;
          background?: string;
        };
        // Validate each value against a strict CSS <color> grammar before
        // interpolating it into the inline style. A value that is not a single
        // well-formed color token is dropped (not sanitized), so a quoted
        // multi-declaration payload can never inject extra CSS. See
        // isSafeCssColor for why this gate exists.
        const safeForeground =
          foreground && isSafeCssColor(foreground) ? foreground : undefined;
        const safeBackground =
          background && isSafeCssColor(background) ? background : undefined;
        const styles: string[] = [];
        if (safeForeground) styles.push(`color: ${safeForeground}`);
        if (safeBackground) styles.push(`background-color: ${safeBackground}`);
        if (styles.length) {
          const props = setSpan(
            safeBackground ? "listview-md-bg" : "listview-md-color",
          );
          props.style = styles.join("; ");
        }
        return;
      }

      // :color-badge[…]
      const badgeMatch = nodeName.match(/^(.+)-badge$/);
      if (badgeMatch) {
        const color = canonicalColor(badgeMatch[1]);
        if (color) {
          setSpan(`listview-md-badge listview-md-badge--${color}`);
        }
        return;
      }

      // :color-background[…]
      const bgMatch = nodeName.match(/^(.+)-background$/);
      if (bgMatch) {
        const color = canonicalColor(bgMatch[1]);
        if (color) {
          setSpan(`listview-md-bg listview-md-bg--${color}`);
        }
        return;
      }

      // :color[…]  (palette color name)
      const color = canonicalColor(nodeName);
      if (color) {
        setSpan(`listview-md-color listview-md-color--${color}`);
        return;
      }
    });
    return tree;
  };
}

// Private-Use sentinels (U+E000–U+E002) used to neutralise the Streamlit
// icon/logo tokens in the source BEFORE remark parses it. They contain no ':',
// so remark-directive never fragments them — unlike the ':material_<name>:' /
// ':streamlit:' colon forms, which the directive parser splits when the token is
// glued to a following word (":material/star:5", ":streamlit:app"), stranding the
// pieces so the downstream findAndReplace misses them and the raw (corrupted)
// text leaks. Stripped from user input first so a sentinel cannot be injected.
const ICON_OPEN = "\uE000";
const ICON_CLOSE = "\uE001";
const STREAMLIT_MARK = "\uE002";
const SENTINELS_RE = /[\uE000\uE001\uE002]/g;

/**
 * The Streamlit icon/logo token grammars, as regex SOURCES (case-sensitive, like
 * everything this renderer claims). The preprocess below compiles its sentinel
 * rewrites from them \u2014 wrapping the icon name in a capture group \u2014 and
 * `plainTextLabel` (utils/text) compiles its strip regexes from them verbatim,
 * so the tokens the accessible name drops are exactly the tokens this preprocess
 * claims: the same one-spelling rule BRACKETED_DIRECTIVES enforces for the
 * bracketed directives.
 */
const MATERIAL_ICON_NAME = String.raw`[\w-]+`;
export const MATERIAL_ICON_TOKEN = `:material/${MATERIAL_ICON_NAME}:`;
export const STREAMLIT_LOGO_TOKEN = ":streamlit:";

// Compiled once at module scope; String.replace resets a global regex's
// lastIndex per call, so sharing them across calls is safe.
const MATERIAL_ICON_REWRITE_RE = new RegExp(
  `:material/(${MATERIAL_ICON_NAME}):`,
  "g",
);
const STREAMLIT_LOGO_REWRITE_RE = new RegExp(STREAMLIT_LOGO_TOKEN, "g");

/**
 * Neutralise the Streamlit icon/logo tokens in the SOURCE before remark parses
 * it, rewriting them to colon-free Private-Use sentinels:
 *   :material/<name>: -> <ICON_OPEN><name><ICON_CLOSE>
 *   :streamlit:       -> <STREAMLIT_MARK>
 * The createRemarkMaterialIcons / createRemarkStreamlitLogo plugins then
 * findAndReplace the sentinels with the icon span / logo image. Because the
 * sentinels carry no ':', remark-directive cannot fragment them, so a token glued
 * to an adjacent word still renders (the previous ':material_<name>:' rewrite
 * broke in that case). Applied to the raw source for both tiers (label + help).
 */
export function materialIconPreprocess(src: string): string {
  return src
    .replace(SENTINELS_RE, "")
    .replace(MATERIAL_ICON_REWRITE_RE, ICON_OPEN + "$1" + ICON_CLOSE)
    .replace(STREAMLIT_LOGO_REWRITE_RE, STREAMLIT_MARK);
}

/** Inline-style string for a Material Symbols Rounded ligature icon span. */
const MATERIAL_ICON_STYLE =
  "display: inline-block;" +
  ' font-family: "Material Symbols Rounded";' +
  ' font-feature-settings: "liga";' +
  " font-weight: normal;" +
  " user-select: none;" +
  " vertical-align: bottom;" +
  " white-space: nowrap;" +
  " word-wrap: normal;";

/**
 * The material-icon sentinel (ICON_OPEN<name>ICON_CLOSE, emitted by
 * materialIconPreprocess) -> <span role="img" …> with the Material Symbols
 * Rounded font; the icon name is emitted as ligature text so the font renders
 * the glyph (and degrades to the literal name when the font is absent). Run
 * AFTER materialIconPreprocess. Ported from Streamlit; font/feature-settings
 * inline because we have no JS theme object. The font itself is loaded by
 * listview.css (area css-notice); this self-contained inline-styled span needs
 * no CSS class.
 */
export function createRemarkMaterialIcons() {
  return () => (tree: Root) => {
    function replace(_fullMatch: string, iconName: string): Text {
      return {
        type: "text",
        value: iconName,
        data: {
          hName: "span",
          hProperties: {
            role: "img",
            ariaLabel: `${iconName} icon`,
            translate: "no",
            style: MATERIAL_ICON_STYLE,
          },
          hChildren: [{ type: "text", value: iconName }],
        },
      } as Text;
    }
    findAndReplace(tree, [[/\uE000([\w-]+)\uE001/g, replace as () => Text]]);
    return tree;
  };
}

/** Inline data-URI of the Streamlit logo glyph (small, theme-neutral mark). */
const STREAMLIT_LOGO_SRC =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 10">' +
      '<path fill="#ff4b4b" d="M8 0 0 4.2l4.7 2.5L8 0zm0 0 8 4.2-4.7 2.5L8 0z"/>' +
      '<path fill="#7d353b" d="M.2 6.9 8 10l3.3-3.3L.2 6.9z"/>' +
      "</svg>",
  );

/** The streamlit sentinel (STREAMLIT_MARK) -> inline streamlit-logo image, baseline-aligned. */
export function createRemarkStreamlitLogo() {
  return () => (tree: Root) => {
    function replaceStreamlit(): Text {
      return {
        type: "text",
        value: "",
        data: {
          hName: "img",
          hProperties: {
            src: STREAMLIT_LOGO_SRC,
            alt: "Streamlit logo",
            style:
              "display: inline-block; user-select: none; height: 0.75em;" +
              " vertical-align: baseline; margin-bottom: -0.05ex;",
          },
        },
      } as Text;
    }
    findAndReplace(tree, [[/\uE002/g, replaceStreamlit as () => Text]]);
    return tree;
  };
}

/**
 * MUST run after the material/logo plugins. findAndReplace replaces sentinels in
 * regular text nodes, but it does NOT descend into `inlineCode` / `code` nodes \u2014
 * so a token written inside backticks or a fenced block keeps its sentinel. This
 * pass restores any leftover sentinel (in ANY node carrying a string `value`) to
 * the readable source the user typed, so a Private-Use control char never leaks
 * to the DOM and the icon syntax shows verbatim inside code.
 */
// Built once from the module sentinel constants and reused across invocations.
// Both are only ever passed to String.prototype.replace, which resets the
// global regex's lastIndex per call, so sharing them is safe.
const RESTORE_MATERIAL_RE = new RegExp(ICON_OPEN + "([\\w-]+)" + ICON_CLOSE, "g");
const RESTORE_STREAMLIT_RE = new RegExp(STREAMLIT_MARK, "g");

export function createRemarkRestoreIconSentinels() {
  return () => (tree: Root) => {
    visit(tree, (node) => {
      const n = node as { value?: string };
      if (
        typeof n.value === "string" &&
        (n.value.includes(ICON_OPEN) || n.value.includes(STREAMLIT_MARK))
      ) {
        n.value = n.value
          .replace(RESTORE_MATERIAL_RE, ":material/$1:")
          .replace(RESTORE_STREAMLIT_RE, ":streamlit:");
      }
    });
    return tree;
  };
}

// The literal source marker per directive form, keyed by mdast node type. The
// lookup doubles as the "is this an unsupported directive node" test: any other
// node type yields undefined.
const DIRECTIVE_MARKERS: Record<string, string | undefined> = {
  textDirective: ":", //   :name[…]
  leafDirective: "::", //  ::name[…]
  containerDirective: ":::", // :::name … :::
};

/**
 * Reconstruct the literal inline form of a text/leaf directive — `:name` /
 * `::name[children]`. The children (the bracketed label content) are KEPT so
 * `:rainbow[Hello]` renders as the literal `:rainbow[Hello]` rather than dropping
 * the visible "Hello" — Streamlit drops them; this is the long-standing divergence
 * that createRemarkColoringAndSmall's childless-directive guard follows.
 * A directive always carries a children array (empty for a bare `:foo`), so no
 * nullish guard is needed.
 */
function literalDirectiveText(
  marker: string,
  node: TextDirective | LeafDirective,
): PhrasingContent[] {
  const prefix: Text = { type: "text", value: `${marker}${node.name}` };
  return node.children.length > 0
    ? [
        prefix,
        { type: "text", value: "[" } as Text,
        ...node.children,
        { type: "text", value: "]" } as Text,
      ]
    : [prefix];
}

/**
 * MUST run LAST. Any directive still lacking an hName (i.e. unclaimed by the
 * coloring/material/logo plugins) is unsupported; replace it with its literal
 * source text so it renders verbatim, as Streamlit does.
 *
 * Streamlit's own cleanup only visits `textDirective`. We ALSO handle the LEAF
 * (`::name[…]`) and CONTAINER (`:::name … :::`) forms — a deliberate improvement
 * over the port, not a widened port: an unclaimed leaf/container node survives
 * into mdast-util-to-hast, whose unknown-node fallback emits a block `<div>`.
 * That both loses the markers the author typed and puts a block element inside
 * the inline-only label `<span>`, which the label tier guarantees cannot happen
 * (see LABEL_DISALLOWED_ELEMENTS).
 */
export function createRemarkUnsupportedDirectivesCleanup() {
  return () => (tree: Root) => {
    visit(tree, (node, index, parent) => {
      const marker = DIRECTIVE_MARKERS[node.type];
      if (!marker || node.data?.hName || !parent || index === undefined) {
        return;
      }
      const directive = node as Directives;
      // A text directive is phrasing content, spliced inline where it stood. The
      // leaf and container forms are BLOCK nodes, so their literal marker needs a
      // paragraph wrapper to stay valid in that position.
      let replacement: Nodes[];
      if (directive.type === "textDirective") {
        replacement = literalDirectiveText(marker, directive);
      } else if (directive.type === "leafDirective") {
        replacement = [
          {
            type: "paragraph",
            children: literalDirectiveText(marker, directive),
          },
        ];
      } else {
        // Container children are BLOCK content and cannot be folded into the
        // literal paragraph, so the marker becomes its own paragraph and the body
        // is lifted after it. The closing `:::` fence is deliberately NOT
        // reconstructed: an unterminated container parses identically to a closed
        // one, so emitting one would invent text nobody typed.
        replacement = [
          {
            type: "paragraph",
            children: [{ type: "text", value: `${marker}${directive.name}` }],
          },
          ...directive.children,
        ];
      }
      // The parent's children type is a narrower union per parent kind; the
      // replacement is valid where the directive stood (see above), which the
      // union cannot express.
      (parent.children as Nodes[]).splice(index, 1, ...replacement);
      // Continue AT the replacement — never a directive itself, so this cannot
      // loop — so that unsupported directives nested in the lifted children
      // (`::foo[:bar[x]]`) are still visited and cleaned up too.
      return index;
    });
    return tree;
  };
}

/**
 * Block-level elements suppressed in the restricted LABEL tier (passed to
 * react-markdown `disallowedElements` together with `unwrapDisallowed`).
 * Ported from Streamlit, plus the two entries flagged below. Single source of
 * truth: Markdown.tsx (area math-emoji) imports this constant from here.
 */
export const LABEL_DISALLOWED_ELEMENTS: string[] = [
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "ul",
  "ol",
  "li",
  "input",
  "hr",
  "blockquote",
  // `pre` wraps fenced / 4-space-indented code blocks; without it a code block
  // renders as a block <pre> inside the inline-only label <span> (invalid
  // nesting). Inline `code` stays allowed (it is not block-level).
  "pre",
  // Defense in depth for the same invariant: nothing in our pipeline emits a
  // <div> on purpose, but mdast-util-to-hast's fallback for an mdast node it does
  // not recognise does (that is how unclaimed leaf/container directives used to
  // leak a block element into the label <span> — now handled at the source in
  // createRemarkUnsupportedDirectivesCleanup). Blocklisting it here means a
  // future unknown node cannot re-break the inline-only guarantee.
  "div",
];

/**
 * Backslash-escape leading block-level Markdown markers so they render
 * literally in the LABEL tier (headings `#`, blockquote `>`, unordered list
 * `+`/`-`/`*`, ordered list `1.`/`1)`), applied to the source BEFORE parsing.
 * Ported verbatim from Streamlit. Single source of truth: Markdown.tsx
 * (area math-emoji) imports this helper from here.
 */
export function escapeLabelSource(src: string): string {
  let processed = src.replace(/^(\s*)((?:[+\-*]|#+)(?=\s|$)|>)/gm, "$1\\$2");
  processed = processed.replace(/^(\s*)(\d+)([.)])(?=\s|$)/gm, "$1$2\\$3");
  return processed;
}
