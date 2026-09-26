import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
// The palette is imported from the PRODUCER rather than re-typed here: the
// plugin emits a listview-md-*--<name> class per entry and this sheet is the only
// consumer, so driving the assertions off the same list is what makes adding a
// color to it fail here until the matching CSS rules exist (DB7).
import { MARKDOWN_COLORS } from "../markdown/streamlitPlugins";

// Use import.meta.dirname (Node 20.11+ / Vitest) to build an absolute path
// rather than fileURLToPath(new URL(..., import.meta.url)), which breaks in
// jsdom because the URL constructor resolves relative to the jsdom origin
// (http://localhost:3000) instead of the file-system location.
const css = readFileSync(
  resolve(import.meta.dirname, "../listview.css"),
  "utf8",
);

describe("listview.css base theming", () => {
  it("themes the container surface/border/radius via --st-* with fallbacks", () => {
    expect(css).toContain('[data-testid="stListview"]');
    expect(css).toContain("var(--st-background-color");
    expect(css).toContain("var(--st-border-color");
    expect(css).toContain("var(--st-base-radius");
    expect(css).toContain("var(--st-text-color");
    expect(css).toContain("var(--st-font");
  });

  it("defines each faded shade ONCE as a custom property and reuses it", () => {
    // These shades have no --st-* token, so the sheet mixes them itself: muted
    // placeholder copy and field glyphs (text 60%), group headers and the empty
    // state (text 70%), the disabled label (text 40%), the group item count
    // (text 50%), every hairline separator (border 50%). Spelled out per site, a
    // shade has to be re-tuned at each one — the 60% had already been re-typed
    // six times, and the other three two to three times — so every mix lives in
    // a single inherited custom property on the container root and the use sites
    // reference it. Hence: exactly one occurrence of each mix in the whole sheet.
    //
    // Table-driven so a shade added to the root block is covered by this test
    // rather than needing its own copy of it.
    const shades = [
      { token: "--listview-faded-text-60", source: "--st-text-color", pct: "60%" },
      { token: "--listview-faded-text-70", source: "--st-text-color", pct: "70%" },
      { token: "--listview-faded-text-40", source: "--st-text-color", pct: "40%" },
      { token: "--listview-faded-text-50", source: "--st-text-color", pct: "50%" },
      {
        token: "--listview-faded-border-50",
        source: "--st-border-color",
        pct: "50%",
      },
    ];
    for (const { token, source, pct } of shades) {
      // defined on the container root, from the theme token, at that percentage
      expect(css).toMatch(
        new RegExp(
          `\\[data-testid="stListview"\\][^{]*\\{[^}]*${token}:\\s*color-mix\\(` +
            `\\s*in srgb\\s*,\\s*var\\(${source}[\\s\\S]*?${pct}`,
        ),
      );
      // ...and mixed nowhere else (the one match IS the definition above)
      const inlineMixes =
        css.match(
          new RegExp(
            `color-mix\\(\\s*in srgb\\s*,\\s*var\\(${source}[^;]*?${pct}`,
            "g",
          ),
        ) ?? [];
      expect(inlineMixes).toHaveLength(1);
      expect(css).toContain(`var(${token})`);
    }
  });

  // Streamlit's sidebar theme SWAPS --st-background-color with
  // --st-secondary-background-color, and nothing else about the color palette.
  // Consumed raw, that inverts the widget in the sidebar: rows land on the
  // group-header surface and headers on the row surface. So the two surfaces
  // are named once as tokens and the swap is undone in exactly one block —
  // spelled per rule, the sidebar would need four more overrides that can drift
  // apart, which is the same failure mode the faded shades above guard against.
  it("names every painted surface as a token instead of raw --st-* per rule", () => {
    const surfaces = [
      { token: "--listview-surface", source: "var\\(--st-background-color" },
      {
        token: "--listview-inset-surface",
        source: "var\\(--st-secondary-background-color",
      },
      { token: "--listview-group-surface", source: "var\\(--listview-bg-mix\\)" },
    ];
    for (const { token, source } of surfaces) {
      // defined on the container root, from the main-body token
      expect(css).toMatch(
        new RegExp(
          `\\[data-testid="stListview"\\]\\s*\\{[\\s\\S]*?${token}:\\s*${source}`,
        ),
      );
    }
    // Every surface that paints a background reaches for a token. Listed by
    // rule so a new painted surface has to be added here deliberately.
    const painted = [
      { rule: "\\.listview-body", token: "--listview-surface" },
      { rule: "\\.listview-header", token: "--listview-surface" },
      { rule: "\\.listview-group-header", token: "--listview-group-surface" },
      {
        rule: "\\.listview-search__input,\\s*\\.listview-new-option__input",
        token: "--listview-inset-surface",
      },
    ];
    for (const { rule, token } of painted) {
      expect(css).toMatch(
        new RegExp(`${rule}\\s*\\{[^}]*background:\\s*var\\(${token}\\)`),
      );
    }
  });

  it("swaps the list surface and its inset together in the sidebar", () => {
    // The search and add-option fields are an INSET on the list surface, filled
    // like st.text_input. Inset and ground must resolve to different --st-*
    // tokens in both containers, or the field is painted the colour of the list
    // it sits in and vanishes — which the sidebar swap does to any pair that
    // is not swapped with it. So the sidebar block hands the pair the theme's
    // two surfaces the other way round (the same rule the help popover's
    // ground/inset pair follows), rather than pinning which token each half gets.
    const tokenOf = (block: string, token: string) =>
      block.match(new RegExp(`${token}:\\s*var\\(\\s*(--st-[a-z-]+)`))?.[1];
    const main =
      css.match(/\[data-testid="stListview"\]\s*\{[^}]*\}/)?.[0] ?? "";
    const side =
      css.match(
        /\[data-testid="stListview"\]\[data-in-sidebar="true"\]\s*\{[^}]*\}/,
      )?.[0] ?? "";
    const pairs = {
      main: {
        ground: tokenOf(main, "--listview-surface"),
        inset: tokenOf(main, "--listview-inset-surface"),
      },
      side: {
        ground: tokenOf(side, "--listview-surface"),
        inset: tokenOf(side, "--listview-inset-surface"),
      },
    };
    for (const [where, pair] of Object.entries(pairs)) {
      expect(pair.ground, `${where} ground`).toBeDefined();
      expect(pair.inset, `${where} inset`).toBeDefined();
      expect(pair.inset, `${where} inset must not repaint its ground`).not.toBe(
        pair.ground,
      );
    }
    expect(pairs.side.ground).toBe(pairs.main.inset);
    expect(pairs.side.inset).toBe(pairs.main.ground);
  });

  it("derives the group band from bgMix, which the sidebar swap cannot change", () => {
    // Streamlit's theme mixes its two background tokens 50/50 (bgMix) for the
    // st.dataframe header band and the menu highlight. The mix is symmetric in
    // the two, so the sidebar — which only trades them — resolves it to the same
    // colour: the band needs no sidebar override, exactly like Streamlit's own.
    expect(css).toMatch(
      /\[data-testid="stListview"\]\s*\{[^}]*--listview-bg-mix:\s*color-mix\(\s*in srgb\s*,\s*var\(--st-background-color[^;]*?50%\s*,\s*var\(--st-secondary-background-color/,
    );
    // Regression guard: a sidebar band override brings back a band that differs
    // between the two containers, where the menu it mirrors never does.
    const side =
      css.match(
        /\[data-testid="stListview"\]\[data-in-sidebar="true"\]\s*\{[^}]*\}/,
      )?.[0] ?? "";
    expect(side).not.toBe("");
    expect(side).not.toMatch(/--listview-group-surface/);
  });

  it("paints the row highlight as the selectbox menu's darkenedBgMix15", () => {
    // Streamlit derives the menu's hover/focus pill from bgMix: HSL lightness
    // -30 points in a light theme, +60 in a dark one, at 15% alpha. A primary
    // tint (the previous hover) has no counterpart in any Streamlit menu, and
    // the dark branch is load-bearing: darkening a dark surface by 30 points
    // leaves a pill darker than the list it sits on.
    expect(css).toMatch(
      /\[data-testid="stListview"\]\s*\{[^}]*--listview-hover-base:\s*hsl\(\s*from\s+var\(--listview-bg-mix\)\s+h\s+s\s+calc\(\s*l\s*-\s*30\s*\)\s*\)/,
    );
    expect(css).toMatch(
      /\[data-testid="stListview"\]\[data-color-scheme="dark"\]\s*\{[^}]*--listview-hover-base:\s*hsl\(\s*from\s+var\(--listview-bg-mix\)\s+h\s+s\s+calc\(\s*l\s*\+\s*60\s*\)\s*\)/,
    );
    expect(css).toMatch(
      /--listview-hover-surface:\s*color-mix\(\s*in srgb\s*,\s*var\(--listview-hover-base\)\s*15%\s*,\s*transparent\s*\)/,
    );
    // An engine without relative colour syntax (Safari before 18 parses the old
    // percentage form, so `calc(l - 30)` is invalid there) would otherwise drop
    // the hover highlight altogether: the whole custom property goes invalid at
    // computed-value time, and a var() fallback cannot catch that.
    expect(css).toMatch(
      /@supports\s+not\s+\(\s*color:\s*hsl\(\s*from\s+red\s+h\s+s\s+calc\(\s*l\s*-\s*30\s*\)\s*\)\s*\)\s*\{[\s\S]*?--listview-hover-surface:\s*color-mix\(\s*in srgb\s*,\s*var\(--st-text-color/,
    );
  });

  it("paints hover, selection and focus as an inset pill, never as a full-row tint", () => {
    // The selectbox menu highlights an option with a pill inset from the row
    // edges. The pill is a ::before BEHIND the label: z-index -1 only stays
    // inside the row if the row isolates a stacking context — without it the
    // pill drops behind the list surface and every highlight disappears.
    const row = css.match(/\.listview-item\s*\{[^}]*\}/)?.[0] ?? "";
    expect(row).toMatch(/position:\s*relative/);
    expect(row).toMatch(/isolation:\s*isolate/);
    const pill = css.match(/\.listview-item::before\s*\{[^}]*\}/)?.[0] ?? "";
    expect(pill).toMatch(/content:\s*""/);
    expect(pill).toMatch(/position:\s*absolute/);
    expect(pill).toMatch(/inset:/);
    expect(pill).toMatch(/z-index:\s*-1/);
    expect(pill).toMatch(/border-radius:/);
    // The row box itself is never tinted, so a highlight cannot bleed into the
    // grid line or under a sticky group header.
    expect(css).not.toMatch(
      /\.listview-item(:hover|\[aria-selected="true"\])\s*\{[^}]*background/,
    );
  });

  it("hovers only rows that take a click, like the menu's disabled options", () => {
    expect(css).toMatch(
      /\.listview-item:not\(\[aria-disabled="true"\],\s*\.listview-item--muted\):hover::before\s*\{[^}]*background:\s*var\(--listview-hover-surface\)/,
    );
  });

  it("marks a selected row like an active st.pills: primary at 10% and primary text", () => {
    expect(css).toMatch(
      /\[data-testid="stListview"\]\s*\{[^}]*--listview-selected-surface:\s*color-mix\(\s*in srgb\s*,\s*var\(--st-primary-color(?:,\s*#ff4b4b)?\)\s*10%\s*,\s*transparent\s*\)/,
    );
    expect(css).toMatch(
      /\.listview-item\[aria-selected="true"\]\s*\{[^}]*color:\s*var\(--st-primary-color/,
    );
    expect(css).toMatch(
      /\.listview-item\[aria-selected="true"\]::before\s*\{[^}]*background:\s*var\(--listview-selected-surface\)/,
    );
    // Hovering a selected row must keep it on the selection's hue. The plain
    // hover rule is (0,3,1); this one has to out-rank it by specificity, not by
    // source order, so it names the selection AND the interactive state.
    expect(css).toMatch(
      /\.listview-item\[aria-selected="true"\]:not\(\[aria-disabled="true"\]\):hover::before\s*\{[^}]*background:\s*var\(--listview-selected-hover-surface\)/,
    );
  });

  it("draws the row focus ring for keyboard focus only", () => {
    // Clicking a row moves the active descendant too, and the old ring followed
    // it: every mouse click left a 2px primary frame on the clicked row, which
    // no native menu does. Every rule that paints the focused row is scoped to a
    // keyboard-focused listbox.
    const focusedRules =
      css.match(/[^{}]*\.listview-item--focused[^{}]*\{/g) ?? [];
    expect(focusedRules.length).toBeGreaterThan(0);
    for (const rule of focusedRules) {
      expect(rule).toMatch(/\.listview-listbox:focus-visible\s/);
    }
    // Streamlit's focusRing: the primary color at 50%.
    expect(css).toMatch(
      /--listview-focus-ring:\s*color-mix\(\s*in srgb\s*,\s*var\(--st-primary-color(?:,\s*#ff4b4b)?\)\s*50%\s*,\s*transparent\s*\)/,
    );
    expect(css).toMatch(
      /\.listview-listbox:focus-visible\s+\.listview-item--focused::before\s*\{[^}]*box-shadow:[^;]*var\(--listview-focus-ring\)/,
    );
  });

  it("draws the pinned header's seam as a divider the focus outline cannot reach", () => {
    // Focus turns the BORDER COLOR of the header and the body primary. The seam
    // between them used to be the body's top border, so it lit up too — a
    // primary line through the middle of the one control. Resetting just that
    // border's colour on focus is not enough: where a primary side border meets
    // a differently coloured top border, the corner joins cut a notch into the
    // outline. So the body drops its top border under a header, and the header
    // paints the seam as a background — which no border-color rule touches.
    expect(css).toMatch(/\.listview-header\s*\{[^}]*position:\s*relative/);
    const seam = css.match(/\.listview-header::after\s*\{[^}]*\}/)?.[0] ?? "";
    expect(seam).toMatch(/content:\s*""/);
    expect(seam).toMatch(/position:\s*absolute/);
    expect(seam).toMatch(/bottom:\s*0/);
    expect(seam).toMatch(/height:\s*1px/);
    expect(seam).toMatch(/background:\s*var\(--st-border-color/);
    expect(css).toMatch(
      /\.listview-header\s*\+\s*\.listview-body\s*\{[^}]*border-top-width:\s*0/,
    );
  });

  it("drops the listbox's own UA focus outline", () => {
    // Keyboard focus on the listbox drew the browser's outline (auto 1px) as a
    // dark hairline under the search field and along the right edge. The frame
    // already turns primary on focus-within (see the next test), so the outline
    // only added a second, unthemed indicator.
    expect(css).toMatch(
      /\.listview-listbox:focus-visible\s*\{[^}]*outline:\s*none/,
    );
  });

  it("lights the control border in the primary color while the widget is active", () => {
    // Focus parity with st.selectbox / st.multiselect: focusing the list, the
    // search field, or the add-option input turns the control border primary.
    // :has() cross-links the (optional) pinned header with the body.
    expect(css).toMatch(
      /\.listview:has\([^)]*:focus-within[\s\S]*?border-color:\s*var\(--st-primary-color/,
    );
  });

  it("mutes disabled items via opacity", () => {
    expect(css).toContain('[aria-disabled="true"]');
    expect(css).toMatch(/opacity:\s*0\.\d+/);
  });

  it("fades AND deactivates the pinned header together with the body when the widget is disabled", () => {
    // Regression: the disabled treatment was scoped to .listview-body only, so a
    // pinned header (pin_search / select_all) kept a fully enabled appearance —
    // the search input's explicit color/background/border override the browser's
    // disabled styling — above a faded list.
    expect(css).toMatch(
      /\.listview--disabled\s+\.listview-header\s*,\s*\.listview--disabled\s+\.listview-body\s*\{[^}]*opacity:\s*0\.4[^}]*pointer-events:\s*none/,
    );
  });

  it("does not stack the per-item fade onto the whole-widget fade", () => {
    // Regression: a disabled widget fades .listview-body to 0.4 AND every row
    // carries aria-disabled (the container ORs the widget flag into the row
    // prop), whose own rule fades it to 0.4 again. Opacity multiplies through
    // nesting, so rows rendered at 0.16 — a second, deeper fade below the
    // header. The override must restore full opacity for rows inside a
    // disabled widget, and must not paint anything else.
    const block =
      css.match(
        /\.listview--disabled\s+\.listview-item\[aria-disabled="true"\]\s*\{[^}]*\}/,
      )?.[0] ?? "";
    expect(block).not.toBe("");
    expect(block).toMatch(/opacity:\s*1\s*;/);
    expect(block).not.toMatch(/background/);
  });

  it("mutes at-cap (max_selections) items distinctly from disabled", () => {
    expect(css).toContain(".listview-item--muted");
    expect(css).toMatch(/\.listview-item--muted[^{]*\{[^}]*opacity/);
  });

  it("styles the widget label row and exposes the help tooltip popover", () => {
    expect(css).toContain(".listview-widget-label");
    // small label size derived from base (no dedicated --st-* sm token)
    expect(css).toMatch(
      /\.listview-widget-label\b[^{]*\{[^}]*calc\(var\(--st-base-font-size/,
    );
    // disabled label fades the theme text color (via the shared 40% token)
    expect(css).toMatch(
      /\.listview-widget-label--disabled\s*\{[^}]*var\(--listview-faded-text-40\)/,
    );
    // help icon trigger gets a focus ring from the primary color
    expect(css).toMatch(
      /\.listview-help-trigger:focus-visible\s*\{[^}]*var\(--st-primary-color/,
    );
    // the inline help-text placeholder is retired; the hover/focus popover surface exists
    expect(css).not.toMatch(/\.listview-help-text\s*\{/);
    expect(css).toContain(".listview-help-popover");
  });

  it("clips the screen-reader label copy out of the layout without hiding it", () => {
    // It supplies the listbox's accessible name via aria-labelledby, and a
    // display:none / visibility:hidden node contributes nothing to a computed
    // name — so the sr-only treatment must be the clip idiom, not hiding.
    const block =
      css.match(/\.listview-widget-label__a11y-name\s*\{[^}]*\}/)?.[0] ?? "";
    expect(block).not.toBe("");
    expect(block).toMatch(/position:\s*absolute/);
    expect(block).toMatch(/clip-path:\s*inset\(50%\)/);
    expect(block).not.toMatch(/display:\s*none/);
    expect(block).not.toMatch(/visibility:\s*hidden/);
  });

  it("declares the layout custom properties on the container root and consumes them", () => {
    expect(css).toContain("var(--listview-height");
    expect(css).toContain("var(--listview-item-height");
    expect(css).toContain("var(--listview-width");
    expect(css).toContain("var(--listview-content-font-size");
    // The --listview-* defaults are declared on the same selector the real
    // container root emits (data-testid="stListview"), so the inline vars
    // Listview.tsx sets there resolve, and .listview-body inherits them.
    expect(css).toMatch(
      /\[data-testid="stListview"\][^{]*\{[^}]*--listview-height/,
    );
  });

  it("sizes option items via --listview-content-font-size, falling back to the small (0.875) size", () => {
    expect(css).toMatch(
      /\.listview-item\s*\{[^}]*font-size:\s*var\(\s*--listview-content-font-size\s*,\s*calc\(var\(--st-base-font-size[^}]*\*\s*0\.875/,
    );
  });

  it("drops row dividers when the no-grid modifier is set", () => {
    expect(css).toMatch(
      /\.listview--no-grid\s+\.listview-item\s*\{[^}]*border-bottom:\s*none/,
    );
  });
});

describe("listview.css markdown — inline tier (label + help)", () => {
  it("scopes markdown styling under the .listview-markdown wrapper", () => {
    expect(css).toContain(".listview-markdown");
  });

  it("themes inline code via the secondary background + base radius", () => {
    // Selector must be scoped to :not(pre) > code so block code in <pre> does not
    // inherit the chip styling (inline-code-only fix — see review issue).
    expect(css).toMatch(
      /\.listview-markdown\s+:not\(pre\)\s*>\s*code\b[^{]*\{[^}]*var\(--st-secondary-background-color/,
    );
    expect(css).toMatch(
      /\.listview-markdown\s+:not\(pre\)\s*>\s*code\b[^{]*\{[^}]*var\(--st-base-radius/,
    );
  });

  it("resets block code inside <pre> so it does not inherit the inline-chip styling", () => {
    expect(css).toMatch(
      /\.listview-markdown\s+pre\s+code\b[^{]*\{[^}]*padding:\s*0/,
    );
    expect(css).toMatch(
      /\.listview-markdown\s+pre\s+code\b[^{]*\{[^}]*background:\s*none/,
    );
  });

  it("colors links via --st-link-color and underlines them", () => {
    expect(css).toMatch(
      /\.listview-markdown\s+a\b[^{]*\{[^}]*var\(--st-link-color/,
    );
    expect(css).toMatch(
      /\.listview-markdown\s+a\b[^{]*\{[^}]*text-decoration:\s*underline/,
    );
  });

  it("renders inline images at font height (max-height: 1em)", () => {
    expect(css).toMatch(
      /\.listview-markdown\s+img\b[^{]*\{[^}]*max-height:\s*1em/,
    );
  });

  it("collapses the markdown wrapper's own block margins so the label stays inline", () => {
    expect(css).toMatch(
      /\.listview-markdown\s+p\b[^{]*\{[^}]*margin:\s*0/,
    );
  });
});

describe("listview.css markdown — help tier block elements", () => {
  it("scopes block elements under the help popover markdown wrapper", () => {
    expect(css).toContain(".listview-help-popover .listview-markdown");
  });

  it("borders GFM tables with --st-border-color", () => {
    expect(css).toMatch(
      /\.listview-help-popover\s+\.listview-markdown\s+(table|th|td)\b[^{]*\{[^}]*var\(--st-border-color/,
    );
  });

  it("styles blockquotes with a left border from the theme", () => {
    expect(css).toMatch(
      /\.listview-help-popover\s+\.listview-markdown\s+blockquote\b[^{]*\{[^}]*border-left/,
    );
  });

  it("themes fenced code blocks as a scrollable mono surface", () => {
    expect(css).toMatch(
      /\.listview-help-popover\s+\.listview-markdown\s+pre\b[^{]*\{[^}]*overflow-x:\s*auto/,
    );
    // Surface comes from the popover's inset half, NOT --st-secondary-background-color:
    // that token IS the dark popover's own ground (see the pair test below).
    expect(css).toMatch(
      /\.listview-help-popover\s+\.listview-markdown\s+pre\s*\{[^}]*background:\s*var\(--listview-popover-inset-surface\)/,
    );
  });

  it("renders hr from the theme border color", () => {
    expect(css).toMatch(
      /\.listview-help-popover\s+\.listview-markdown\s+hr\b[^{]*\{[^}]*var\(--st-border-color/,
    );
  });
});

describe("listview.css markdown — Streamlit extras (colors, badge, shimmer, material)", () => {
  it("defines the colored-text / colored-background / badge base classes", () => {
    expect(css).toContain(".listview-md-color");
    expect(css).toContain(".listview-md-bg");
    expect(css).toContain(".listview-md-badge");
  });

  it("emits a per-color modifier class for every color the plugin can emit", () => {
    for (const name of MARKDOWN_COLORS) {
      expect(css).toContain(`.listview-md-color--${name}`);
      expect(css).toContain(`.listview-md-bg--${name}`);
      expect(css).toContain(`.listview-md-badge--${name}`);
    }
  });

  it("binds named foreground colors to --st-<name>-text-color (fallback --st-<name>-color)", () => {
    for (const name of MARKDOWN_COLORS) {
      expect(css).toMatch(
        new RegExp(
          `\\.listview-md-color--${name}\\b[^{]*\\{[^}]*var\\(--st-${name}-text-color`,
        ),
      );
      // fallback chain reaches --st-<name>-color
      expect(css).toContain(`var(--st-${name}-color`);
    }
  });

  it("binds named background colors to --st-<name>-background-color tokens", () => {
    for (const name of MARKDOWN_COLORS) {
      expect(css).toMatch(
        new RegExp(
          `\\.listview-md-bg--${name}\\b[^{]*\\{[^}]*var\\(--st-${name}-background-color`,
        ),
      );
    }
  });

  it("binds the badge to the text token on the background token per color", () => {
    for (const name of MARKDOWN_COLORS) {
      expect(css).toMatch(
        new RegExp(
          `\\.listview-md-badge--${name}\\b[^{]*\\{[^}]*var\\(--st-${name}-background-color`,
        ),
      );
      expect(css).toMatch(
        new RegExp(
          `\\.listview-md-badge--${name}\\b[^{]*\\{[^}]*var\\(--st-${name}-text-color`,
        ),
      );
    }
  });

  it("rounds badges with the base radius and pads them", () => {
    expect(css).toMatch(
      /\.listview-md-badge\b[^{]*\{[^}]*var\(--st-base-radius/,
    );
    expect(css).toMatch(/\.listview-md-badge\b[^{]*\{[^}]*padding/);
  });

  it("lets the colored-text base rule inherit so an arbitrary inline color wins", () => {
    expect(css).toMatch(
      /\.listview-markdown\s+\.listview-md-color\b[^{]*\{[^}]*color:\s*inherit/,
    );
  });

  it("animates the shimmer span with a keyframed mask", () => {
    expect(css).toContain(".listview-md-shimmer");
    expect(css).toMatch(/@keyframes\s+listview-shimmer/);
    expect(css).toMatch(/\.listview-md-shimmer\b[^{]*\{[^}]*animation[^}]*listview-shimmer/);
  });

  it("renders :small[] text smaller via .listview-md-small", () => {
    expect(css).toContain(".listview-md-small");
  });

  it("renders material icons with inline-styled spans — no CSS class needed", () => {
    // createRemarkMaterialIcons emits inline styles (MATERIAL_ICON_STYLE), not a
    // className, so there is no .listview-md-material-icon selector in the sheet.
    // The font family and liga feature-settings live solely in the inline style;
    // asserting their absence from the CSS locks the DB7 producer==consumer contract.
    expect(css).not.toContain(".listview-md-material-icon");
  });
});

describe("listview.css help tooltip popover", () => {
  it("defines the .listview-help-popover surface", () => {
    expect(css).toContain(".listview-help-popover");
  });

  it("uses the theme font at the small size and theme text color", () => {
    expect(css).toMatch(
      /\.listview-help-popover\b[^{]*\{[^}]*var\(--st-font/,
    );
    expect(css).toMatch(
      /\.listview-help-popover\b[^{]*\{[^}]*calc\(var\(--st-base-font-size/,
    );
    expect(css).toMatch(
      /\.listview-help-popover\b[^{]*\{[^}]*color:\s*var\(--st-text-color/,
    );
  });

  it("tracks the Streamlit theme for its surface (light=bg, dark=secondary), not the OS scheme", () => {
    // Light is the default surface (bgColor); the dark override swaps to
    // secondaryBackground keyed on the theme-derived [data-color-scheme]
    // attribute Listview.tsx sets — matching Streamlit's own tooltip in either
    // theme, regardless of the OS prefers-color-scheme.
    const block = css.match(/\.listview-help-popover\s*\{[^}]*\}/)?.[0] ?? "";
    expect(block).not.toBe("");
    // The surface is now reached through the named pair (see the next test), so
    // the light/dark contract is asserted on where each half of the pair points.
    expect(block).toMatch(/background:\s*var\(--listview-popover-surface\)/);
    expect(block).toMatch(
      /--listview-popover-surface:\s*var\(\s*--st-background-color/,
    );
    expect(css).toMatch(
      /\.listview\[data-color-scheme="dark"\]\s+\.listview-help-popover\s*\{[^}]*--listview-popover-surface:\s*var\(\s*--st-secondary-background-color/,
    );
    // the OS-keyed media override must be gone (it mismatched native tooltips
    // whenever the OS scheme disagreed with the Streamlit theme). Match the
    // @media query itself, not the word in the explanatory comment.
    expect(css).not.toMatch(/@media[^{]*prefers-color-scheme/);
  });

  it("never resolves an inset surface to the same --st-* token as the popover ground", () => {
    // The dark theme did exactly that. The popover swapped its ground to
    // --st-secondary-background-color, while the three surfaces painted ON it —
    // the inline-code chip, the GFM table header and the fenced code block —
    // stayed on that same token, so each one rendered in the exact colour of the
    // thing it sat on and vanished. Light escaped only by accident: the popover
    // happens to sit on --st-background-color there. So this was never a sidebar
    // or a container question — it was one token used for both roles.
    //
    // The two grounds are now declared as a PAIR in the popover's own rule
    // blocks, which is what makes the collision unrepeatable: a scheme can only
    // hand them the theme's two surfaces swapped, and an edit to one is written
    // next to the other. Assert that property — the halves point at DIFFERENT
    // --st-* tokens, and the dark block swaps them rather than moving one —
    // instead of pinning which surface each half happens to get.
    const pairIn = (block: string) => {
      expect(block).not.toBe("");
      return {
        ground: block.match(
          /--listview-popover-surface:\s*var\(\s*(--st-[a-z-]+)/,
        )?.[1],
        inset: block.match(
          /--listview-popover-inset-surface:\s*var\(\s*(--st-[a-z-]+)/,
        )?.[1],
      };
    };
    const light = pairIn(
      css.match(/\.listview-help-popover\s*\{[^}]*\}/)?.[0] ?? "",
    );
    const dark = pairIn(
      css.match(
        /\.listview\[data-color-scheme="dark"\]\s+\.listview-help-popover\s*\{[^}]*\}/,
      )?.[0] ?? "",
    );
    for (const [scheme, pair] of [
      ["light", light],
      ["dark", dark],
    ] as const) {
      expect(pair.ground, `${scheme} popover ground`).toBeDefined();
      expect(pair.inset, `${scheme} popover inset`).toBeDefined();
      expect(
        pair.inset,
        `${scheme} inset must not repaint its own ground`,
      ).not.toBe(pair.ground);
    }
    // ...and the dark block is a swap of the same two surfaces, not a third one.
    expect(dark.ground).toBe(light.inset);
    expect(dark.inset).toBe(light.ground);
  });

  it("routes every surface rendered inside the popover through the inset half", () => {
    // The three insets. Each must read the token, because spelling any --st-*
    // surface here directly is how the halves drifted into the same colour: the
    // use site cannot see which ground the popover resolved to in this scheme.
    // The inline-code chip needs its own popover-scoped rule — the base chip
    // (unscoped, for the inline label tier) sits on the LIST surface, which does
    // not swap, so it correctly keeps --st-secondary-background-color.
    const insets = [
      String.raw`:not\(pre\)\s*>\s*code`,
      String.raw`th`,
      String.raw`pre`,
    ];
    for (const selector of insets) {
      expect(css, `inset: ${selector}`).toMatch(
        new RegExp(
          String.raw`\.listview-help-popover\s+\.listview-markdown\s+${selector}\s*\{` +
            String.raw`[^}]*background:\s*var\(--listview-popover-inset-surface\)`,
        ),
      );
    }
  });

  it("keeps a chip inside a table header off the header's own surface", () => {
    // th is the one inset that is also a CONTAINER, so it needs the pair read the
    // other way round: a chip inside a header cell cannot ALSO take the inset
    // half, or it is painted the exact colour of the cell it sits on. A help
    // table whose header names a field in code did exactly that, in both schemes
    // and both containers. It takes the ground half, which the pair guarantees is
    // a different colour. (A chip in a BODY cell is already fine — td is
    // transparent, so that chip sits on the popover ground.)
    //
    // Equal specificity to the popover chip rule above ((0,2,2) both), so this
    // one must come LATER in the sheet — the same source-order tie the base chip
    // rule and the `pre code` reset already rely on.
    const chip = String.raw`\.listview-help-popover\s+\.listview-markdown\s+:not\(pre\)\s*>\s*code\s*\{`;
    const thChip = String.raw`\.listview-help-popover\s+\.listview-markdown\s+th\s+code\s*\{`;
    expect(css).toMatch(
      new RegExp(
        thChip +
          String.raw`[^}]*background:\s*var\(--listview-popover-surface\)`,
      ),
    );
    expect(css.search(new RegExp(thChip))).toBeGreaterThan(
      css.search(new RegExp(chip)),
    );
  });

  it("renders a borderless floating surface: base radius + a soft drop shadow", () => {
    // Streamlit's TooltipIcon surface has NO border; it floats on a soft shadow
    // (BaseWeb lighting.shadow400). The contract is border-vs-shadow — that the
    // popover reads as floating rather than as a bordered box — so the shadow's
    // exact offsets/alpha stay free to be tuned.
    const block = css.match(/\.listview-help-popover\s*\{[^}]*\}/)?.[0] ?? "";
    expect(block).not.toBe("");
    expect(block).not.toMatch(/(^|[^-])border:\s*1px/);
    expect(block).toMatch(/var\(--st-base-radius/);
    expect(block).toMatch(/box-shadow:\s*[^;]*rgba\(/);
  });

  it("is positioned above-right with a max-width and a high z-index", () => {
    expect(css).toMatch(
      /\.listview-help-popover\b[^{]*\{[^}]*position:\s*absolute/,
    );
    expect(css).toMatch(/\.listview-help-popover\b[^{]*\{[^}]*max-width/);
    expect(css).toMatch(/\.listview-help-popover\b[^{]*\{[^}]*z-index/);
  });

  it("anchors the trigger slot as the positioning context", () => {
    expect(css).toMatch(
      /\.listview-widget-label__help-slot\s*\{[^}]*position:\s*relative/,
    );
  });

  it("bridges the gap under the popover so the pointer can reach it", () => {
    // Regression: the popover floats `bottom: calc(100% + 0.25rem)` above the
    // trigger, and that 0.25rem strip belonged to no element — crossing it
    // fired the wrapper's mouseleave and unmounted the popover before the
    // pointer arrived, so a link in `help` could never be clicked. A pseudo-
    // element owned by the popover must cover exactly that gap, and it must
    // stay transparent (no fourth painted surface).
    const offset = css.match(
      /\.listview-help-popover\s*\{[^}]*bottom:\s*calc\(100%\s*\+\s*([\d.]+rem)\)/,
    )?.[1];
    expect(offset).toBeDefined();
    const bridge =
      css.match(/\.listview-help-popover::before\s*\{[^}]*\}/)?.[0] ?? "";
    expect(bridge).not.toBe("");
    expect(bridge).toMatch(/content:\s*""/);
    expect(bridge).toMatch(/position:\s*absolute/);
    expect(bridge).toMatch(/top:\s*100%/);
    expect(bridge).toMatch(new RegExp(`height:\\s*${offset}`));
    expect(bridge).not.toMatch(/background/);
  });
});

describe("Milestone C feature styling", () => {
  it("styles the search field, pinned header, chevron, and new-option row", () => {
    expect(css).toContain(".listview-header");
    expect(css).toContain(".listview-search__icon");
    expect(css).toContain(".listview-search__input");
    expect(css).toContain(".listview-search__clear");
    expect(css).toContain(".listview-group-header--collapsible");
    expect(css).toContain(".listview-group-header__chevron");
    expect(css).toContain(".listview-new-option__icon");
    expect(css).toContain(".listview-new-option__input");
  });

  it("sizes the collapse chevron via --listview-content-font-size, defaulting to 1rem", () => {
    expect(css).toMatch(
      /\.listview-group-header__chevron\s*\{[^}]*width:\s*var\(\s*--listview-content-font-size\s*,\s*1rem/,
    );
    expect(css).toMatch(
      /\.listview-group-header__chevron\s*\{[^}]*height:\s*var\(\s*--listview-content-font-size\s*,\s*1rem/,
    );
  });

  it("styles the group item count as a muted, normal-weight inline span", () => {
    expect(css).toContain(".listview-group-header__count");
    // normal weight so it recedes against the 600-weight name
    expect(css).toMatch(
      /\.listview-group-header__count\b[^{]*\{[^}]*font-weight:\s*400/,
    );
    // more muted than the name: the shared 50% faded-text token (mixed once, in
    // the root token block — see the faded-shade test above)
    expect(css).toMatch(
      /\.listview-group-header__count\b[^{]*\{[^}]*color:\s*var\(--listview-faded-text-50\)/,
    );
    // separated from the name by a NON-ZERO logical-start margin in the static
    // header (the exact gap is cosmetic; the contract is only that there is one,
    // and that it is the logical property so RTL keeps the count after the name)…
    // ([1-9] rather than a negative lookahead for 0: the value only has to
    // contain a non-zero digit, and \s* before a lookahead can backtrack onto the
    // whitespace and satisfy it vacuously.)
    expect(css).toMatch(
      /\.listview-group-header__count\b[^{]*\{[^}]*margin-inline-start:[^;]*[1-9]/,
    );
    // …reset to 0 under the collapsible header so the flex gap is not doubled
    expect(css).toMatch(
      /\.listview-group-header--collapsible\s+\.listview-group-header__count\s*\{[^}]*margin-inline-start:\s*0\b/,
    );
  });

  it("sizes group headers via --listview-content-font-size with the 0.875 fallback", () => {
    expect(css).toMatch(
      /\.listview-group-header\s*\{[^}]*font-size:\s*var\(\s*--listview-content-font-size\s*,\s*calc\(var\(--st-base-font-size[^}]*\*\s*0\.875/,
    );
    expect(css).toMatch(
      /\.listview-group-header--collapsible\s*\{[^}]*font-size:\s*var\(\s*--listview-content-font-size\s*,\s*calc\(var\(--st-base-font-size[^}]*\*\s*0\.875/,
    );
  });

  it("the inner listbox does not re-declare the body border (single scroll frame)", () => {
    // .listview-body keeps height/overflow/border; .listview-listbox must not add its own border
    expect(css).not.toMatch(/\.listview-listbox\s*\{[^}]*border:/);
  });

  it("fills the search field like st.text_input: no visible edge, 1px primary on focus", () => {
    // st.text_input paints its border in its own fill colour, so the field reads
    // as one filled shape, and focus turns that 1px border primary — no extra
    // ring. A --st-border-color outline around a field inside the bordered list
    // frame drew a second, unmatched edge.
    const field =
      css.match(
        /\.listview-search__input\s*,\s*\.listview-new-option__input\s*\{[^}]*\}/,
      )?.[0] ?? "";
    expect(field).toMatch(/background:\s*var\(--listview-inset-surface\)/);
    expect(field).toMatch(
      /border:\s*1px\s+solid\s+var\(--listview-inset-surface\)/,
    );
    const focus =
      css.match(
        /\.listview-search__input:focus-visible\s*,\s*\.listview-new-option__input:focus-visible\s*\{[^}]*\}/,
      )?.[0] ?? "";
    expect(focus).toMatch(/border-color:\s*var\(--st-primary-color/);
    expect(focus).not.toMatch(/box-shadow/);
  });

  it("resets the UA button border on the collapsible group header", () => {
    // With collapsible_groups the header is a <button>. The header rule set only
    // border-bottom, so the browser's own button border (2px outset) framed the
    // top, left and right of every group band. The reset has to come BEFORE the
    // bottom line in the same block, or it would erase it.
    const header = css.match(/\.listview-group-header\s*\{[^}]*\}/)?.[0] ?? "";
    const reset = header.search(/(^|[\s;{])border:\s*0\s*;/);
    const bottom = header.search(/border-bottom:\s*1px/);
    expect(reset).toBeGreaterThan(-1);
    expect(bottom).toBeGreaterThan(reset);
  });

  it("styles the search box and the add-option box from ONE shared recipe", () => {
    // Both are the same control (a bordered field with a left-edge glyph) sitting
    // in the same bordered frame, so any divergence reads as a rendering bug. They
    // were two full copies of these declarations with nothing linking them and had
    // already drifted; grouping the selectors per concern — glyph, field,
    // placeholder, focus ring — is what makes a theming change reach both. Only
    // horizontal padding may be overridden per field.
    expect(css).toMatch(
      /\.listview-search__icon\s*,\s*\.listview-new-option__icon\s*\{/,
    );
    expect(css).toMatch(
      /\.listview-search__input\s*,\s*\.listview-new-option__input\s*\{[^}]*var\(--listview-inset-surface\)/,
    );
    expect(css).toMatch(
      /\.listview-search__input::placeholder\s*,\s*\.listview-new-option__input::placeholder\s*\{/,
    );
    expect(css).toMatch(
      /\.listview-search__input:focus-visible\s*,\s*\.listview-new-option__input:focus-visible\s*\{[^}]*var\(--st-primary-color/,
    );
  });
});
