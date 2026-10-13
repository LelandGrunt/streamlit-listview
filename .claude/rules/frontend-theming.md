---
paths:
  - "streamlit_listview/frontend/src/**/*.css"
  - "streamlit_listview/frontend/src/index.tsx"
  - "streamlit_listview/frontend/src/hooks/useColorScheme.ts"
  - "streamlit_listview/frontend/src/utils/container.ts"
  - "streamlit_listview/frontend/src/__tests__/listview-css.test.ts"
  - "e2e/app_sidebar_theme.py"
  - "e2e/app_native_parity.py"
  - "e2e/test_sidebar_theme.py"
  - "e2e/test_native_parity*.py"
---

# Theming and painted states (`streamlit_listview/frontend/`)

These rules extend `streamlit_listview/frontend/CLAUDE.md`. Claude Code loads this file when it reads, writes or edits a file that the `paths` above name: the stylesheet, the code that sets its theme attributes, and the tests that pin it. Read it before any change to how the widget looks, also one that starts in a component.

## Theming

- **All CSS (`listview.css`) reads Streamlit's `--st-*` properties, with fallbacks.** It uses no Bootstrap and no fixed palette.
- **Never use `prefers-color-scheme` or `light-dark()`:** the production bundler (lightningcss) rewrites them so that they miss the shadow tree. For light and dark styling, read the root's `data-color-scheme`, which `useColorScheme` sets from the active Streamlit theme. The attribute reads `light` until an effect after the first paint reads the theme, so never key a surface that is visible at mount on it.
- **Never put a `:has()` selector in a selector list.** lightningcss wraps such a list in `:is()`, and WebKit does not re-evaluate a `:has()` inside `:is()` after a focus change. Write one selector and gather the targets in a trailing `:is()`, as the frame rule does; `single-file-build.test.ts` checks the built sheet.
- **`src/__tests__/listview-css.test.ts` pins what the stylesheet says; `e2e/test_sidebar_theme.py` and `e2e/test_native_parity.py` pin what a browser resolves it to.** They compare the widget with a real `st.selectbox`, `st.pills` or `st.text_input` on the same page, never with a fixed hex value. `test_native_parity_dark.py` repeats the parity tests under `--theme.base dark`, the only run that exercises the dark highlight formula.

## The sidebar swaps two tokens

- **Streamlit gives the sidebar its own theme, and a V2 instance's `--st-*` block comes from the theme at its own mount point.** With Streamlit's default sidebar theme, only `--st-background-color` and `--st-secondary-background-color` trade values, and the heading sizes shrink; every other color is identical. A `[theme.sidebar]` section in the app's config can also set the sidebar's own primary, text and background colors; no test boots one. Only a running app shows the swap: Streamlit builds the names at runtime (`` `--st-${kebab(key)}` ``), so a search of its source finds none.
- **Paint every surface through the `--listview-*` tokens on the container root, never through the raw tokens.** Read raw, the swap inverts the widget in the sidebar. `--listview-surface` (frame, rows, pinned header, add-option footer) and its inset `--listview-inset-surface` (search and add-option fields) are the two raw tokens, swapped together in the single `[data-in-sidebar="true"]` block. `--listview-group-surface` is `--listview-bg-mix`, Streamlit's 50/50 mix of the two, which the swap cannot move. A new surface that references a token behaves correctly in the sidebar without an override of its own.
- **The swap matches Streamlit:** `st.selectbox`, `st.multiselect` and `st.text_input` fill their controls from `--st-secondary-background-color` in both containers, and the open selectbox menu paints the app background in both.
- **`data-in-sidebar` comes from `isInSidebar`, which `index.tsx` calls before the first render;** `Listview` writes the attribute on its root, `div.listview`. The renderer's `parentElement` is the open `ShadowRoot`, so the answer exists at mount; an effect would set it a frame late and flash the main-body colors on every mount. The probe steps to `ShadowRoot.host` first, because `closest()` does not cross a shadow boundary; without that step the widget silently keeps the main-body colors. It needs no observer, because a container move remounts the frontend. `[data-testid="stSidebar"]` is Streamlit-internal; an upstream rename degrades to the main-body colors.

## A surface and its insets are declared as a pair

- **A surface and anything painted on it must resolve to different `--st-*` tokens in every scheme,** so the two are declared together in one block, never at their use sites. A use site cannot see which ground its container resolved to.
- **The help tooltip is the worked example:** `--listview-popover-surface` and `--listview-popover-inset-surface`, both on `.listview-help-popover`, both declared again by the dark override. Each half is literally the other one of the two tokens, never a fixed color and never a `color-mix` off the ground. The sidebar swap then inverts both halves together, so the halves differ in all four combinations of container and scheme without a `[data-in-sidebar]` override, as long as the theme's two background colors differ. Like the label's inline-code chip, it reads the raw tokens, because it follows Streamlit's tooltip, not the list surface; if that has to change, it joins the `--listview-surface` family.
- **Do not paint the code surfaces with `--st-code-background-color`.** Streamlit derives it as a 50 % mix of the two surfaces, so in a light theme it lands close to `--st-background-color`, and an inline-code chip all but disappears.
- **The popover's inline-code rule is scoped to the popover,** because the base chip rule also serves the inline label tier. That tier renders only in `WidgetLabel`, which paints no background, so `--st-secondary-background-color` contrasts there in both containers.
- **A `th` is an inset and also a container:** a chip inside a table header reads the ground half, or it takes the color of its cell. That rule depends on its source order.
- **`listview-css.test.ts` pins the pairs:** the halves differ in each scheme, the dark block swaps them, every inset reads its token, and the `th` source order holds. The list's own pair (`--listview-surface` / `--listview-inset-surface`) is pinned the same way, with the sidebar block as the swap. The test also refuses a `prefers-color-scheme` media query; `light-dark()` and `--st-code-background-color` have no test.

## Every painted state copies the native widget that plays its part

The list is an always-open `st.selectbox` menu, so each state copies a measured Streamlit reference (Streamlit 1.60, both themes):

| State | Reference |
|---|---|
| list surface | the open selectbox menu |
| row hover | the menu's option highlight `darkenedBgMix15`: the bg mix with its HSL lightness −30 in a light theme and +60 in a dark one, at 15 % alpha |
| selected row | an active `st.pills`: primary at 10 %, primary text |
| group band | the `st.dataframe` header (the bg mix) |
| search field | `st.text_input`: filled, a 1px border in its own fill, 1px primary on focus, no ring |
| frame | primary on focus only |

- **The frame changes on focus only.** No native input changes its frame on hover or wheel scroll, so add no hover border.
- **`.listview-item::before` paints the highlight as a pill** with the menu's geometry: a 5px side inset (`sizes.tagMarginInsideBorder`) and a `0.375rem` radius (`radii.md2`, fixed in Streamlit, not derived from `--st-base-radius`). It sits at `z-index: -1` and stays inside the row only because the row is `position: relative; isolation: isolate`; without the isolation every highlight disappears behind the list surface. The row box itself is never tinted.
- **The highlight formula needs relative color syntax** (`hsl(from var(--listview-bg-mix) h s calc(l - 30))`), the only way to take an HSL step off a `var()`. lightningcss passes it, the `@supports not (…)` fallback and `:not(a, b)` through unchanged; check `build/index-*.css` again when the toolchain moves. An engine without the syntax, or with the pre-2024 percentage form (Safari < 18), invalidates the whole custom property, which no `var()` fallback catches; the `@supports not` block substitutes a faint text-color mix.
- **The row focus ring** (Streamlit's `focusRing`, primary at 50 %) appears only under `.listview-listbox:focus-visible`. A mouse click moves the active descendant too (`onItemClick` → `setFocusToId`), and no native menu rings a clicked row. The listbox's own outline is suppressed: the frame turns primary on focus-within and the focused row carries the ring, so the outline would add a second indicator in an unthemed color. A keyboard-focused group header draws the 2px inset primary ring under the same `:focus-visible` (`.listview-group-header--focused`).
- **`.listview-header::after` and `.listview-footer::before` paint the seams of the pinned header and the add-option footer** as backgrounds (`pin_search` or `select_all` pins the header, `accept_new_options` adds the footer). The body drops its top border under a header and its bottom border above a footer. Focus recolors the borders of header, body and footer, so a seam drawn as a border either lights up or notches the outline. Keep the seams non-borders.
