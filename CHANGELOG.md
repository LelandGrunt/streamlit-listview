# Changelog

Notable changes to `streamlit-listview`. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Version numbers follow [Semantic Versioning](https://semver.org/); a 1.x release that breaks compatibility says so at the top of its notes.

## [Unreleased]

**This release breaks compatibility within 1.x.** Three changes to `accept_new_options` with int or dict options can break code that relied on the old behavior. The entries marked **Breaking** under *Changed* say what to change.

### Added

- **`ungrouped_label` sets the header of the options without a group** (default `"Other"`). A group of your own with that name shares the header and its block. Set another label, such as `"N/A"`, to translate the header or to keep that group apart.
- **Each option reports its place in the list and the size of the list** (`aria-posinset`, `aria-setsize`), so a screen reader announces "23,456 of 100,000" even for rows the browser has not drawn. The numbers count the whole list, even while a search narrows it.
- The demo's **Large** dataset offers up to 100,000 items, up from 10,000.
- The demo turns on Streamlit's websocket compression (`server.enableWebsocketCompression`). At 100,000 options a click or settings change then sends 0.48 MB over the network instead of 6.75 MB, for about 0.1 s more server CPU. An app of your own with a large option list can turn on the same setting.
- **The README opens with a 50-second tour of the demo app**, recorded with Streamlit's own *Record screen*: multi-select, search, collapsible groups, sorting, a default far down the list, two brand themes, 100,000 options and the sidebar. `scripts/gif/screencast.py` records it again.
- **The README lists the keys the listview answers to**, among them Esc, which clears the search and then the selection. A new section on large lists gives the measured times and the data Streamlit sends per rerun, and shows how websocket compression shrinks it.
- **The performance benchmarks cover 100,000 rows and dict options that carry a `disabled` key.** At 100,000 options the options take 6.7 MB to send. Streamlit sends them whenever the listview's payload changes: when its parameters change, on the first rerun after a listview with a `key` appears, and on each click on such a listview. A `disabled` key on every row makes the options 28 % larger (8.6 MB), the `listview()` call 15 % slower, and a rerun that sends the options or a click on a keyed listview 13 to 15 % slower; search and scrolling take as long as without it. A row without the key is enabled, so pass `disabled` only on the rows you disable. See [BENCHMARKS.md](BENCHMARKS.md).
- **Each release on GitHub shows its notes from this changelog.** Before, the release page showed only a link that compares the release with the one before.
- For maintainers: `scripts/gif/compare.py` compares two recordings of the widget scenarios in `scripts/gif/` frame by frame and writes an HTML report that marks the changed pixels in red. It shows what a change did to the widget's look; see `scripts/gif/README.md`.

### Changed

- **Breaking: an entry the user adds via `accept_new_options` comes back in the type of the other options.** Before, it always came back as the typed string, so code had to test each returned value with `isinstance`. Now:

  | `options` are …           | The user adds | Before    | Now                                 |
  | ------------------------- | ------------- | --------- | ----------------------------------- |
  | all dicts                 | `Mango`       | `"Mango"` | `{"id": "Mango", "label": "Mango"}` |
  | all `int`                 | `42`          | `"42"`    | `42`                                |
  | all `str`, mixed, or none | `Mango`       | `"Mango"` | `"Mango"`                           |

  The same rule covers an unknown `default` and a selected id that a keyed widget keeps after you remove it from `options`. If your code tested a returned value for `str` to find added entries, test for the option's type instead: with dict options an added entry is a dict whose `id` is the typed text.
- **Breaking: with int options, the add field accepts only whole numbers.** It takes `42` or `-5` and refuses `abc`, `1.5`, `007` and `+5`, with the hint "Enter a whole number" below the field. Text that matches an existing row's id or label still selects that row, but users can no longer add free text to a list of int options.
- **Breaking: with int options, an unknown `default` must be a whole number.** `default="abc"` raises `ValueError`; `default=42` and `default="42"` both come back as `42`.
- **The browser lays out and paints only the rows near the visible frame.** Every row stays in the page, but rows outside the frame skip style, layout and paint until the list scrolls to them. Measured in Chromium with 100,000 options in groups of 100 (medians of 3 runs):

  | Measurement                          | Before   | Now      |
  | ------------------------------------ | -------- | -------- |
  | The list appears                     | 2,310 ms | 1,120 ms |
  | The app settles after a click        | 1,254 ms | 475 ms   |
  | A rerun that sends the options again | 780 ms   | 384 ms   |
  | Clearing the search                  | 1,797 ms | 550 ms   |
  | A scroll frame, 95th percentile      | 158 ms   | 18 ms    |

  At 1,000 options the times stay within the spread of the measurement. In Chromium a screen reader sees only the rows near the frame, and the other rows as the list scrolls to them; each row's `aria-posinset` and `aria-setsize` give its place in the whole list. Firefox before 125 and Safari before 18 ignore the setting and draw every row as before.
- **In a grouped list, the options without a group render last, under their own header.** Before, they rendered without a header where the first of them stood in `options`, so an option placed first, such as "All cities", sat above every group. It now renders at the end. `collapsed_groups="all"` collapses this header too, and so does a list that names `ungrouped_label`.
- **The add field of `accept_new_options` sits in a footer below the list** and stays in view while the list scrolls. The widget grows by the height of that footer; `height` still sets the height of the scrolling list. After an add, the list opens the block the entry appears in and scrolls to the entry.
- **Select all adds the rows in the order shown, so a `max_selections` cap takes them from the top of the list.** Before, it took the options in the order you passed them, which grouping can rearrange.

### Fixed

- **A listview whose `key` changes scrolls its `default` into view even when its stylesheet arrives late.** A new `key`, such as one that includes the `default` the way the demo's does, makes Streamlit draw the listview anew, and the browser loads the listview's stylesheet again. On a slow connection the listview scrolled to its default before the stylesheet arrived, so the scroll was lost and the list stayed at its top. With the stylesheet held back 400 ms in Chromium, the 988th of 1,000 options stayed out of view. The listview now waits for its stylesheet, up to about 10 seconds, before it scrolls.
- **The scroll range follows a change of the row height on a rerun.** A listview with a `key`, scrolled away from its top, got `item_height`, `content_font_size` or `show_grid_lines` changed on a rerun, and the rows outside the visible frame kept their old height until the list scrolled back to its top. With 1,000 options and a change to `item_height=50`, the list scrolled over 37,205 px where its rows take 50,354 px, so the scrollbar and the rows below the frame sat at the wrong places. The listview now measures its rows again whenever their height changes, a theme with another font included.
- **Options without a group and entries added via `accept_new_options` show that they belong to no group.** In a grouped list they looked like members of the last group above them, and only the returned value showed otherwise. The add field below the rows looked like part of that group too.
- **The demo clears the selection when you pick another data source or Large size.** Before, the selection outlived its dataset: with **Accept new options** on, every row selected in the old dataset stayed selected as an added entry. Edits to the **Custom** options keep the selection, so the demo still shows how a keyed listview corrects its selection when `options` change.
- **The demo names the Streamlit version it needs: 1.56 or later.** It passes `required` to `st.pills` and `st.segmented_control`, which Streamlit 1.56 added, so Streamlit 1.51 to 1.55 stop it with a `TypeError`. `demo/requirements.txt` now asks for Streamlit 1.56; the package itself still runs on Streamlit 1.51.

### Security

- **`listview()` turns an unexpected value in an added entry into text.** The browser returns the selection to Python as JSON, so a modified page can send any value JSON can express as an added entry: a dict such as `{"$ne": None}`, a list, `None`, `True`, a float, or an int with `abs(value) > 2**53 - 1`. `listview()` returns such a value as `str(value)`: as the entry's `id` and `label` with dict options, and as the entry itself otherwise. An app that puts an added entry into a database query, such as a MongoDB filter, thus receives only a `str` or an `int` with `abs(value) <= 2**53 - 1`. Entries that users type into the add field come back as the table under *Changed* shows.

## [1.0.1] - 2026-10-04

Faster large lists. The API and behavior are unchanged, so upgrading needs no edits.

### Changed

- **Reruns skip rows whose options did not change.** Streamlit sends the options again whenever the listview's payload changes, for example when another parameter changes or a listview with a `key` is clicked. The listview now keeps the option objects whose content is the same, so it does not render their rows again; when one option changes, only its row re-renders. That reuse cuts the listview's own rerun work by 2.5 to 4.5 times at every list size. In a Streamlit app running in Chromium, a rerun that sends unchanged options again at 50,000 rows finishes 20 to 44 % sooner.
- **Clearing the search or expanding a large group now costs time in proportion to the rows.** Rows render in chunks of 100, so bringing thousands of rows back at once no longer slows down with the square of their number. Clearing a search takes 0.84 s instead of 3.8 s at 50,000 ungrouped rows, and 0.18 s instead of 0.32 s at 10,000, in Chromium.
- **Editing one option touches only that option.** A rerun that changes one option in place, for example to disable or relabel it, rebuilds no index over the others.

The first render, scrolling, and the data sent per rerun are unchanged. A rerun that sends the options again still transfers 2.3 to 3.4 MB at 50,000 options.

*Corrected on 2026-10-11:* these notes first said that Streamlit sends the options on every rerun of the app, even when only another widget changed. It sends them only when the listview's payload changes; another rerun sends about 1.5 KB at 10,000 options. The notes also listed the changes under *Performance*, which Keep a Changelog does not define; they now stand under *Changed*.

### Added

- Two-tier performance benchmarks at 100 to 50,000 rows: `npm run bench` measures the React side; `pytest e2e/perf/ --perf-out …` measures the whole app in a real browser with Streamlit. See [BENCHMARKS.md](BENCHMARKS.md).

## [1.0.0] - 2026-09-26

First stable release.

[Unreleased]: https://github.com/LelandGrunt/streamlit-listview/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/LelandGrunt/streamlit-listview/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/LelandGrunt/streamlit-listview/releases/tag/v1.0.0
