"""Packaging invariants for the streamlit-listview wheel (spec §9).

The second half exercises `scripts/verify_wheel.py`, the CI gate that inspects a
built wheel. It is driven against synthetic zips rather than a real `uv build`
so the assertions (including the failure paths) run without a Node toolchain.
"""

import os
import re
import runpy
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ROOT_PYPROJECT = ROOT / "pyproject.toml"
NESTED_PYPROJECT = ROOT / "streamlit_listview" / "pyproject.toml"
DEMO_REQUIREMENTS = ROOT / "demo" / "requirements.txt"

EXPECTED_VERSION = "1.1.0"

sys.path.insert(0, str(ROOT / "scripts"))

import push_gate
import verify_wheel


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _project_version(text: str) -> str:
    # THE version parse lives in verify_wheel.project_version (the [project]
    # table only); parsing the field a second way here is how the copies drifted.
    return verify_wheel.project_version(text)


def test_root_version_is_target():
    assert _project_version(_read(ROOT_PYPROJECT)) == EXPECTED_VERSION


def test_nested_version_is_target():
    assert _project_version(_read(NESTED_PYPROJECT)) == EXPECTED_VERSION


def test_versions_agree():
    assert _project_version(_read(ROOT_PYPROJECT)) == _project_version(
        _read(NESTED_PYPROJECT)
    )


@pytest.mark.parametrize("path", [ROOT_PYPROJECT, NESTED_PYPROJECT])
def test_project_version_agrees_with_a_toml_parser(path):
    # The helper reads a subset of TOML; both shipped pyprojects stay inside it.
    data = verify_wheel._parse_toml(_read(path))
    assert _project_version(_read(path)) == data["project"]["version"]


@pytest.mark.parametrize(
    "text",
    [
        # A version key of another table, before [project] and after it.
        '[tool.example]\nversion = "9.9.9"\n\n[project]\nname = "x"\nversion = "1.2.3"\n',
        '[project]\nname = "x"\nversion = "1.2.3"\n\n[tool.example]\nversion = "9.9.9"\n',
        # A subtable of [project] is another table.
        '[project.urls]\nversion = "9.9.9"\n\n[project]\nversion = "1.2.3"\n',
        # Spacing, comments and a literal string, as TOML allows them.
        "[ project ]  # metadata\n  version='1.2.3'  # bumped on release\n",
        '[project]\r\nversion = "1.2.3"\r\n',
    ],
)
def test_project_version_reads_the_project_table_only(text):
    assert verify_wheel.project_version(text) == "1.2.3"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ('version = "1.2.3"\n', "no [project].version field"),
        ('[project]\nversion = ""\n', "no [project].version field"),
        (
            '[project]\nname = "x"\n\n[tool.example]\nversion = "9.9.9"\n',
            "no [project].version field",
        ),
        (
            '[project]\nversion = "1.2.3"\n\n[project]\nversion = "1.2.4"\n',
            "more than one [project].version field",
        ),
    ],
)
def test_project_version_refuses_a_missing_or_ambiguous_field(text, reason):
    with pytest.raises(ValueError, match=re.escape(reason)):
        verify_wheel.project_version(text)


def test_demo_requirements_pin_the_released_version():
    # The Community Cloud deployment installs the published wheel from this pin
    # rather than building the repo, so a pin left behind on a release silently
    # keeps the hosted demo on the previous version. Exactly one `==` pin: a
    # range or a second spelling would let the two drift apart unnoticed.
    # THE pin parse lives in push_gate.demo_pins, which the pre-push gate uses
    # too, so the gate and this test agree on what counts as a pin.
    pins = push_gate.demo_pins(_read(DEMO_REQUIREMENTS))
    assert pins == [_project_version(_read(ROOT_PYPROJECT))]


def test_root_packagedata_bundles_build_and_nested_manifest():
    text = _read(ROOT_PYPROJECT)
    # package-data must ship the built frontend AND the nested pyproject manifest
    assert "frontend/build/**/*" in text
    assert re.search(r"package-data[\s\S]*pyproject\.toml", text), (
        "root package-data must include the nested pyproject.toml"
    )


def test_nested_manifest_declares_component():
    # The component segment stays "listview"; the manifest's [project] name is
    # "streamlit_listview" (canonically matches the distribution "streamlit-listview"),
    # so the qualified name is "streamlit_listview.listview" — matching
    # st.components.v2.component(...) in __init__.py. Parsed with the parser
    # Streamlit reads the shipped copy with, as verify_wheel does.
    assert (
        verify_wheel.manifest_problems(_read(NESTED_PYPROJECT), EXPECTED_VERSION) == []
    )


def test_init_registers_qualified_name():
    init = _read(ROOT / "streamlit_listview" / "__init__.py")
    assert '"streamlit_listview.listview"' in init


# ── scripts/verify_wheel.py ──────────────────────────────────────────────────

_DIST_INFO = f"streamlit_listview-{EXPECTED_VERSION}.dist-info"


_MANIFEST_ENTRY = verify_wheel.MANIFEST


def _fake_wheel(
    tmp_path: Path, entries: list[str], manifest: str | None = None
) -> Path:
    """Zip up `entries` under a correctly named wheel filename.

    The component manifest holds `manifest`, by default the source's own, since
    verify_wheel parses it; every other entry holds a placeholder.
    """
    wheel = tmp_path / f"streamlit_listview-{EXPECTED_VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        for name in entries:
            if name == _MANIFEST_ENTRY:
                zf.writestr(
                    name, _read(NESTED_PYPROJECT) if manifest is None else manifest
                )
            else:
                zf.writestr(name, "x")
    return wheel


def _good_entries() -> list[str]:
    # The package's modules from the source tree, as verify_wheel requires them.
    modules = sorted((ROOT / "streamlit_listview").glob("*.py"))
    return [
        *(f"streamlit_listview/{module.name}" for module in modules),
        "streamlit_listview/py.typed",
        "streamlit_listview/frontend/build/index-abc123.js",
        "streamlit_listview/frontend/build/index-abc123.css",
        "streamlit_listview/frontend/build/THIRD_PARTY_LICENSES.md",
        _MANIFEST_ENTRY,
        f"{_DIST_INFO}/licenses/LICENSE",
        f"{_DIST_INFO}/licenses/NOTICE",
    ]


def _verify(monkeypatch, wheel: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["verify_wheel.py", str(wheel)])
    verify_wheel.main()


def test_verify_wheel_accepts_a_wellformed_wheel(monkeypatch, tmp_path):
    _verify(monkeypatch, _fake_wheel(tmp_path, _good_entries()))


def test_verify_wheel_rejects_a_second_js_chunk(monkeypatch, tmp_path):
    # The registration contract is EXACTLY one index-*.js: Streamlit's glob
    # resolver raises on several matches, so a wheel carrying a stale extra chunk
    # is unloadable and the gate must say so — and distinguish it from zero.
    wheel = _fake_wheel(
        tmp_path,
        [*_good_entries(), "streamlit_listview/frontend/build/index-stale99.js"],
    )
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, wheel)
    assert "exactly one built index-*.js, found 2" in str(exc.value)


def test_verify_wheel_rejects_a_missing_css_bundle(monkeypatch, tmp_path):
    entries = [e for e in _good_entries() if not e.endswith(".css")]
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, _fake_wheel(tmp_path, entries))
    assert "exactly one built index-*.css, found 0 (none)" in str(exc.value)


def test_verify_wheel_rejects_a_missing_license_file(monkeypatch, tmp_path):
    # The bundle carries the code of the frontend's npm packages, and their
    # licenses require their notices in every copy.
    entries = [e for e in _good_entries() if not e.endswith("THIRD_PARTY_LICENSES.md")]
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, _fake_wheel(tmp_path, entries))
    assert "missing the third-party license file" in str(exc.value)


def test_verify_wheel_rejects_an_extra_file_under_build(monkeypatch, tmp_path):
    # The package-data glob ships EVERYTHING under frontend/build/, and the
    # exactly-one checks only count index-* files — a stray file beside the
    # bundle (added between compile and `uv build`) would otherwise land in the
    # published, attested wheel silently, so the gate must pin the exact set.
    wheel = _fake_wheel(
        tmp_path,
        [*_good_entries(), "streamlit_listview/frontend/build/extra.txt"],
    )
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, wheel)
    assert (
        "unexpected files under frontend/build/: "
        "streamlit_listview/frontend/build/extra.txt" in str(exc.value)
    )


def test_verify_wheel_rejects_a_module_missing_from_the_source(monkeypatch, tmp_path):
    # setuptools ships whatever its staging directory build/lib holds, so a
    # module deleted from the source can ship from an earlier build's copy.
    wheel = _fake_wheel(
        tmp_path, [*_good_entries(), "streamlit_listview/_removed_module.py"]
    )
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, wheel)
    assert (
        "files absent from the source tree: streamlit_listview/_removed_module.py"
        in str(exc.value)
    )


@pytest.mark.parametrize(
    "entry", ["streamlit_listview/_options.py", "streamlit_listview/py.typed"]
)
def test_verify_wheel_rejects_a_wheel_without_a_package_file(
    monkeypatch, tmp_path, entry
):
    # The reverse of the check above: the names alone would pass a wheel
    # that lacks a module or the type marker.
    wheel = _fake_wheel(tmp_path, [e for e in _good_entries() if e != entry])
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, wheel)
    assert f"lacks files of the source tree: {entry}" in str(exc.value)


_SOURCE_MANIFEST = _read(NESTED_PYPROJECT)
_NO_COMPONENT = (
    "no [[tool.streamlit.component.components]] entry with "
    "name 'listview' and asset_dir 'frontend/build'"
)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            "[project]",
            "[project",
            "streamlit_listview/pyproject.toml is not valid TOML",
        ),
        (
            'name = "streamlit_listview"',
            'name = "other_package"',
            (
                "[project].name 'other_package' is not the distribution "
                "'streamlit-listview'"
            ),
        ),
        (
            f'version = "{EXPECTED_VERSION}"',
            'version = "9.9.9"',
            f"[project].version '9.9.9' is not '{EXPECTED_VERSION}'",
        ),
        ('asset_dir = "frontend/build"', 'asset_dir = "build"', _NO_COMPONENT),
        ('name = "listview"', 'name = "list_view"', _NO_COMPONENT),
        # Not a table, not a list, not a dict entry: Streamlit registers nothing.
        ("[project]", "project = 1\n[other]", "[project].name '' is not"),
        (
            "[[tool.streamlit.component.components]]",
            "components = 1\n[x]",
            _NO_COMPONENT,
        ),
        (
            "[[tool.streamlit.component.components]]",
            '[tool.streamlit.component]\ncomponents = ["listview"]\n[x]',
            _NO_COMPONENT,
        ),
    ],
)
def test_verify_wheel_rejects_a_manifest_streamlit_cannot_use(
    monkeypatch, tmp_path, old, new, message
):
    # Streamlit reads the shipped manifest when the server starts: it matches
    # [project].name to the distribution and finds the bundle by the
    # component's asset_dir. A wheel whose manifest fails either registers no
    # component, so the gate parses it, not just its file name.
    assert old in _SOURCE_MANIFEST
    manifest = _SOURCE_MANIFEST.replace(old, new, 1)
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, _fake_wheel(tmp_path, _good_entries(), manifest))
    assert message in str(exc.value)


def test_verify_wheel_parses_the_manifest_without_toml(monkeypatch):
    # scripts/push_gate.py imports verify_wheel on the standard library alone,
    # so the manifest parse must work without Streamlit's `toml` package.
    monkeypatch.setitem(sys.modules, "toml", None)
    assert verify_wheel.manifest_problems(_SOURCE_MANIFEST, EXPECTED_VERSION) == []
    problems = verify_wheel.manifest_problems("[project", EXPECTED_VERSION)
    assert len(problems) == 1
    assert problems[0].startswith(f"{verify_wheel.MANIFEST} is not valid TOML")


def test_verify_wheel_rejects_a_leaked_build_backend(monkeypatch, tmp_path):
    wheel = _fake_wheel(
        tmp_path, [*_good_entries(), "streamlit_listview/_build_backend.py"]
    )
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, wheel)
    assert "must not ship _build_backend.py" in str(exc.value)


def test_verify_wheel_rejects_a_wheel_of_another_version(monkeypatch, tmp_path):
    # The version must end at a hyphen: 1.0.10 is not 1.0.1.
    wheel = _fake_wheel(tmp_path, _good_entries())
    other = wheel.with_name(f"streamlit_listview-{EXPECTED_VERSION}0-py3-none-any.whl")
    wheel.rename(other)
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, other)
    assert f"is not version {EXPECTED_VERSION}" in str(exc.value)


def test_verify_wheel_picks_the_newest_wheel_by_time(monkeypatch, tmp_path):
    # Lexically 0.10.0 sorts before 0.9.0; the newer file must win.
    dist = tmp_path / "dist"
    dist.mkdir()
    older = dist / "streamlit_listview-0.9.0-py3-none-any.whl"
    newer = dist / "streamlit_listview-0.10.0-py3-none-any.whl"
    for age, wheel in ((100, older), (0, newer)):
        wheel.write_bytes(b"")
        os.utime(wheel, (1_000_000 - age, 1_000_000 - age))
    monkeypatch.setattr(verify_wheel, "ROOT", tmp_path)
    assert verify_wheel._newest_wheel() == newer


def test_verify_wheel_without_a_wheel_says_how_to_build_one(monkeypatch, tmp_path):
    monkeypatch.setattr(verify_wheel, "ROOT", tmp_path)
    with pytest.raises(SystemExit) as exc:
        verify_wheel._newest_wheel()
    assert "run `uv build` first" in str(exc.value)


def test_verify_wheel_without_a_project_version_stops(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.setattr(verify_wheel, "ROOT", tmp_path)
    with pytest.raises(SystemExit) as exc:
        verify_wheel._expected_version()
    assert "could not read [project].version" in str(exc.value)


def test_verify_wheel_runs_main_as_a_script(monkeypatch, tmp_path, capsys):
    wheel = _fake_wheel(tmp_path, _good_entries())
    monkeypatch.setattr(sys, "argv", ["verify_wheel.py", str(wheel)])
    runpy.run_path(str(ROOT / "scripts" / "verify_wheel.py"), run_name="__main__")
    assert "PASS: wheel contents verified" in capsys.readouterr().out
