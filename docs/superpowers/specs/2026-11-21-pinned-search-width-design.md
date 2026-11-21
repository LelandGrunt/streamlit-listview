# Pinned search field in a narrow frame: design

## Intent

A listview with `pin_search=True` in a narrow sidebar shows its search field wider than the frame: the field runs out past the right border. The field must shrink with the frame, as the in-flow search field already does.

## Cause

`.listview-header` is a flex container, and `.listview-header > .listview-search` takes `flex: 1` only. A flex item keeps `min-width: auto`, so it never shrinks below its content's minimum width. The search input's intrinsic width is about 20 characters, which makes the search field about 232 px wide at least in Streamlit's default theme. Below a frame width of about 240 px the field overflows the header; with `select_all`, the toggle leaves the frame below about 320 px.

Measured with the shipped stylesheet on a bare page in Chromium and Firefox, with the browser's default font (a field of 252 px), at a frame width of 170 px:

| Layout | Overflow now | Overflow with `min-width: 0` |
| --- | --- | --- |
| in-flow search | none | none |
| pinned search | 75 px | none |
| pinned search and Select all | 75 px | none |

## Goals and non-goals

- Goal: the pinned search field and the Select all toggle stay inside the frame at every width the sidebar allows.
- Non-goal: a new layout for very narrow frames, such as the toggle wrapping below the field.

## Approaches

1. **`min-width: 0` on `.listview-header > .listview-search` (chosen).** It lets the flex item shrink below its content; the input already carries `min-width: 0` inside it. It touches one rule and only the pinned layout.
2. `overflow: hidden` on the header. It clips the field instead of shrinking it, so the right end and the clear button disappear.
3. A `size="1"` attribute on the input. It lowers the intrinsic width, but changes the markup for a fault that lies in the stylesheet alone, and it also changes the in-flow field.

## Design

- `listview.css`: add `min-width: 0` to `.listview-header > .listview-search`, with a comment that gives the reason.
- `listview-css.test.ts`: pin the declaration.
- An e2e test: in a narrow frame, the pinned search field, with and without Select all, stays inside the header's border box.
- `CHANGELOG.md`: a *Fixed* entry under a new *Unreleased* section.
- Run the visual comparison and regenerate the hero GIF, as the root `CLAUDE.md` requires for a change to `listview.css`; commit the GIF only if its frames change.

## Left to the builder

- The harness and the width for the e2e test.
