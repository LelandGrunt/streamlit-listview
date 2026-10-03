# Changelog

Notable changes to `streamlit-listview`. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.1] - Unreleased

Faster large lists. No API or behaviour changes: upgrading needs no code change.

### Performance

- **Reruns no longer re-render an unchanged list.** Streamlit sends the options again on every rerun of the app, even when only another widget changed. The listview now keeps the option objects whose content did not change, so their rows are not rendered again; when one option changes, only its row re-renders. This cuts the listview's own rerun work by 2.5 to 4.5 times at every list size. In a Streamlit app in Chromium, a rerun with unchanged options at 50,000 rows settles 20 to 44 % sooner.
- **Clearing the search, or expanding a large group, is no longer quadratic.** Rows render in keyed chunks of 100, so bringing thousands of rows back at once no longer slows down with the square of their number. Clearing a search over 50,000 ungrouped rows takes 0.84 s instead of 3.8 s in Chromium, and 0.18 s instead of 0.32 s at 10,000 rows.
- **Editing a single option is cheaper.** A rerun that changes one option in place, for example to disable or relabel it, no longer rebuilds an index over every option.

Mounting the list, scrolling, and the data sent per rerun are unchanged. A rerun of 50,000 options still transfers 2.3 to 3.4 MB, which only a smaller payload or a virtualized list could reduce.

### Development

- Two-tier performance benchmarks at 100 to 50,000 rows: `npm run bench` for the React side, `pytest e2e/perf/ --perf-out …` in a real browser with Streamlit. See [BENCHMARKS.md](BENCHMARKS.md).

## [1.0.0] - 2026-09-26

First stable release.

[1.0.1]: https://github.com/LelandGrunt/streamlit-listview/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/LelandGrunt/streamlit-listview/releases/tag/v1.0.0
