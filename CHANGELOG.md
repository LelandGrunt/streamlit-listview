# Changelog

Notable changes to `streamlit-listview`. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.1] - Unreleased

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

[1.0.1]: https://github.com/LelandGrunt/streamlit-listview/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/LelandGrunt/streamlit-listview/releases/tag/v1.0.0
