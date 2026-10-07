# Changelog

Notable changes to `streamlit-listview`. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- The demo's **Large** dataset offers up to 100,000 items, up from 10,000.
- The demo turns on Streamlit's websocket compression (`server.enableWebsocketCompression`). At 100,000 options a click or settings change then sends 0.48 MB over the network instead of 6.75 MB, for about 0.1 s more server CPU. An app of your own with a large option list can turn on the same setting.
- The performance benchmarks also measure 100,000 rows. At that size, in Chromium, the list appears after 2.6 s, and a clicked row highlights after 0.29 s and the app settles after 1.3 s. The options take 6.7 MB to send, and Streamlit sends them again on every rerun that changes the listview's parameters or, for a listview with a `key`, its selection. See [BENCHMARKS.md](BENCHMARKS.md).
- The performance benchmarks measure dict options that carry a `disabled` key on every row. At 100,000 rows the key makes the options 28 % larger (8.6 MB instead of 6.7 MB), the `listview()` call 20 % slower and a rerun that leaves the options unchanged 12 % slower. Search, clicks, group toggles and scrolling take as long as without the key. A row without the key is enabled, so pass `disabled` only on the rows you disable.

### Changed

- **An entry the user adds via `accept_new_options` comes back in the type of the other options.** Before, it always came back as the typed string, so code had to test each returned value with `isinstance`. Now:

  | `options` are …           | The user adds | Before    | Now                                 |
  | ------------------------- | ------------- | --------- | ----------------------------------- |
  | all dicts                 | `Mango`       | `"Mango"` | `{"id": "Mango", "label": "Mango"}` |
  | all `int`                 | `42`          | `"42"`    | `42`                                |
  | all `str`, mixed, or none | `Mango`       | `"Mango"` | `"Mango"`                           |

  The same rule covers an unknown `default` and a selected id that a keyed widget keeps after you remove it from `options`. If your code tested a returned value for `str` to find added entries, test for the option's type instead: with dict options an added entry is a dict whose `id` is the typed text.
- **With int options, the add field accepts only whole numbers.** It takes `42` or `-5` and refuses `abc`, `1.5`, `007` and `+5`, with the hint "Enter a whole number" below the field. Text that matches an existing row's id or label still selects that row, but users can no longer add free text to a list of int options.
- **With int options, an unknown `default` must be a whole number.** `default="abc"` raises `ValueError`; `default=42` and `default="42"` both come back as `42`.

### Fixed

- **`listview()` turns an unexpected value in an added entry into text.** The browser returns the selection to Python as JSON, so a modified page can send any value JSON can express as an added entry: a dict such as `{"$ne": None}`, a list, `None`, `True`, a float, or an int with `abs(value) > 2**53 - 1`. `listview()` returns such a value as `str(value)`: as the entry's `id` and `label` with dict options, and as the entry itself otherwise. An app that puts an added entry into a database query, such as a MongoDB filter, thus receives only a `str` or an `int` with `abs(value) <= 2**53 - 1`. Entries that users type into the add field come back as the table above shows.
- **The demo clears the selection when you pick another data source or Large size.** Before, the selection outlived its dataset: with **Accept new options** on, every row selected in the old dataset stayed selected as an added entry. Edits to the **Custom** options keep the selection, so the demo still shows how a keyed listview corrects its selection when `options` change.

## [1.0.1] - 2026-10-04

Faster large lists. The API and behaviour are unchanged, so upgrading needs no edits.

### Performance

- **Reruns skip rows whose options did not change.** Streamlit sends the options again on every rerun of the app, even when only another widget changed. The listview now keeps the option objects whose content is the same, so it does not render their rows again; when one option changes, only its row re-renders. That reuse cuts the listview's own rerun work by 2.5 to 4.5 times at every list size. In a Streamlit app running in Chromium, a rerun with unchanged options at 50,000 rows finishes 20 to 44 % sooner.
- **Clearing the search or expanding a large group now costs time in proportion to the rows.** Rows render in chunks of 100, so bringing thousands of rows back at once no longer slows down with the square of their number. Clearing a search takes 0.84 s instead of 3.8 s at 50,000 ungrouped rows, and 0.18 s instead of 0.32 s at 10,000, in Chromium.
- **Editing one option touches only that option.** A rerun that changes one option in place, for example to disable or relabel it, rebuilds no index over the others.

The first render, scrolling, and the data sent per rerun are unchanged. A rerun of 50,000 options still transfers 2.3 to 3.4 MB; only sending less data, or rendering only the visible rows, could reduce that.

### Added

- Two-tier performance benchmarks at 100 to 50,000 rows: `npm run bench` measures the React side; `pytest e2e/perf/ --perf-out …` measures the whole app in a real browser with Streamlit. See [BENCHMARKS.md](BENCHMARKS.md).

## [1.0.0] - 2026-09-26

First stable release.

[Unreleased]: https://github.com/LelandGrunt/streamlit-listview/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/LelandGrunt/streamlit-listview/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/LelandGrunt/streamlit-listview/releases/tag/v1.0.0
