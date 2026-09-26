"""README must document the real V2 API and carry no stale scaffold text."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

sys.path.insert(0, str(ROOT / "scripts"))

import verify_wheel  # noqa: E402


def _first(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    assert m, f"no match for {pattern!r}"
    return m.group(1)


def test_documents_core_new_api():
    for token in [
        "selection_mode",
        "accept_new_options",
        "pin_search",
        "collapsible_groups",
        "collapsed_groups",
        "Jump to default",  # jump-to-default described (Features section)
        "max_selections",
        "select_all",
        "show_grid_lines",
        "label_visibility",
        "key",
    ]:
        assert token in README, f"README missing {token!r}"


def test_readme_documents_every_public_param():
    """Drift guard: every public listview() parameter must be named in the
    README — in backticks, i.e. as documented API, not as an accidental
    substring (a bare `in README` check is vacuous for parameters that are
    ordinary English words: help, key, width, sort, label all appear in prose
    regardless). Derived from the live signature so a newly-added
    parameter cannot silently go undocumented (the failure mode that left
    select_all and show_grid_lines out of the README)."""
    import inspect

    from streamlit_listview import listview

    for name in inspect.signature(listview).parameters:
        assert f"`{name}`" in README, (
            f"README does not document the listview() parameter {name!r} "
            "(it must appear in backticks)"
        )


def test_readme_python_examples_compile():
    """Syntax guard: every ```python fenced block in the README must compile —
    a typo'd example (stray comma, unclosed paren, v1-era API pseudo-code)
    would otherwise ship as copy-paste-broken documentation."""
    blocks = re.findall(r"```python\n(.*?)```", README, flags=re.DOTALL)
    assert blocks, "no ```python fenced blocks found in the README"
    for i, block in enumerate(blocks, start=1):
        try:
            compile(block, f"README.md python block #{i}", "exec")
        except SyntaxError as err:
            raise AssertionError(
                f"README.md python block #{i} does not compile: {err}\n{block}"
            ) from err


def test_version_matches_pyproject_and_no_stale_scaffold():
    """Drift guard: the README's dist-filename examples must show the version
    currently declared in [project].version, so a release bump that forgets
    the README fails here (release.yml runs this suite before building). The
    version badge is live — shields.io reads it from PyPI — so it cannot fall
    behind a release; only the project it queries can be wrong, and a wrong
    one would show some other package's version."""
    # The shared column-0-anchored parse (see verify_wheel.project_version) —
    # a third private regex for this field is how the copies drifted.
    version = verify_wheel.project_version(PYPROJECT)
    name = _first(r'(?m)^name\s*=\s*"([^"]+)"', PYPROJECT)

    assert re.search(rf"img\.shields\.io/pypi/v/{re.escape(name)}(?=[?)])", README)
    assert f"streamlit_listview-{version}-py3-none-any.whl" in README
    assert f"streamlit_listview-{version}.tar.gz" in README
    assert "0.0.1" not in README          # stale expected-output filename
    assert "num_clicks" not in README     # stale scaffold snippet
    assert 'listview("World")' not in README


def test_badges_match_declared_floors_and_gates():
    """Drift guard: the static README badges must show the floors and gates
    actually declared in pyproject.toml (requires-python, the streamlit pin,
    fail_under, license) and the frontend vitest thresholds, so changing any
    of them without updating the badges fails here."""
    python_floor = _first(r'(?m)^requires-python\s*=\s*">=([^"]+)"', PYPROJECT)
    assert f"img.shields.io/badge/python-%E2%89%A5_{python_floor}-" in README

    streamlit_floor = _first(r'"streamlit\s*>=\s*([\d.]+)"', PYPROJECT)
    assert f"img.shields.io/badge/Streamlit-%E2%89%A5_{streamlit_floor}-" in README

    fail_under = _first(r"(?m)^fail_under\s*=\s*(\d+)", PYPROJECT)
    assert f"img.shields.io/badge/coverage-{fail_under}%25-" in README
    vitest = (ROOT / "streamlit_listview" / "frontend" / "vitest.config.ts").read_text(
        encoding="utf-8"
    )
    thresholds = re.findall(r"(?:statements|branches|functions|lines):\s*(\d+)", vitest)
    assert len(thresholds) == 4, "vitest coverage thresholds not found"
    for threshold in thresholds:
        assert threshold == fail_under, "vitest coverage gate diverges from the README badge"

    license_id = _first(r'(?m)^license\s*=\s*"([^"]+)"', PYPROJECT)
    # shields.io renders "_" as a space, so "Apache-2.0" is written "Apache_2.0"
    assert f"img.shields.io/badge/license-{license_id.replace('-', '_')}-" in README


def test_install_command_matches_distribution_name():
    """Drift guard: the documented install command must name the real
    distribution ([project].name) — `pip install listview` (a different,
    unrelated PyPI package) shipped in the README once already."""
    name = _first(r'(?m)^name\s*=\s*"([^"]+)"', PYPROJECT)
    assert f"uv pip install {name}" in README
    assert not re.search(r"pip install listview\b", README)


def test_notes_markdown_and_theming():
    assert "Markdown" in README
    # LaTeX/KaTeX intentionally unsupported (spec decision)
    assert "LaTeX" in README or "KaTeX" in README
    assert "--st-" in README              # theming via Streamlit CSS variables
