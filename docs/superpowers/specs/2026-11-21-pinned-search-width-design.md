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
- Goal, added after the review: the field keeps 3rem of room for text from the sidebar's minimum width up (see *Follow-up: the toggle wraps*).
- Non-goal at first: a new layout for very narrow frames, such as the toggle wrapping below the field. The user made it a goal after the review.

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

## Follow-up: the toggle wraps

The review found a floor that `min-width: 0` cannot lower: the input's padding keeps 56 px for the glyph and the clear button, and its border 2 px. Beside the toggle (69 px as "Select all", 83 px as "Deselect all"), a field in a frame below about 170 px kept no room for text, and the input ran under the toggle. Streamlit's sidebar is 200 px wide at least, which leaves a listview about 140 px; its default of 300 px leaves 240 px.

Approaches:

1. **A container query on the header (chosen).** The header becomes the size container `listview-header`, wraps its flex line, and below 13.5rem of content width (a frame of about 234 px) the field takes `flex-basis: 100%`, so the toggle drops to a line of its own. The width alone decides.
2. `flex-wrap: wrap` with a flex basis on the field. The label would decide the line break: in a band of frame widths as wide as the two labels differ (14 px), a click on "Select all" would bring the wider "Deselect all", move the toggle to a second line and shift the list under the pointer.

13.5rem keeps 3rem of text room beside "Deselect all" just above the threshold. Below it the field takes the whole line, which at the sidebar's minimum also leaves 3rem. Streamlit's default sidebar keeps one line. The wrapped toggle sits at the left, as it does in a header without a pinned search field.
