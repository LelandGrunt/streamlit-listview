"""Packaging invariants for the streamlit-listview wheel (spec §9).

The second half exercises `scripts/verify_wheel.py`, the CI gate that inspects a
built wheel. It is driven against synthetic zips rather than a real `uv build`
so the assertions (including the failure paths) run without a Node toolchain.
"""
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ROOT_PYPROJECT = ROOT / "pyproject.toml"
NESTED_PYPROJECT = ROOT / "streamlit_listview" / "pyproject.toml"
DEMO_REQUIREMENTS = ROOT / "demo" / "requirements.txt"

EXPECTED_VERSION = "1.0.1"

sys.path.insert(0, str(ROOT / "scripts"))

import verify_wheel  # noqa: E402


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _project_version(text: str) -> str:
    # THE version parse lives in verify_wheel.project_version (column-0
    # anchored); parsing the field a second way here is how the copies drifted.
    return verify_wheel.project_version(text)


def test_root_version_is_target():
    assert _project_version(_read(ROOT_PYPROJECT)) == EXPECTED_VERSION


def test_nested_version_is_target():
    assert _project_version(_read(NESTED_PYPROJECT)) == EXPECTED_VERSION


def test_versions_agree():
    assert _project_version(_read(ROOT_PYPROJECT)) == _project_version(
        _read(NESTED_PYPROJECT)
    )


def test_demo_requirements_pin_the_released_version():
    # The Community Cloud deployment installs the published wheel from this pin
    # rather than building the repo, so a pin left behind on a release silently
    # keeps the hosted demo on the previous version. Exactly one `==` pin: a
    # range or a second spelling would let the two drift apart unnoticed.
    pins = re.findall(
        r"(?mi)^\s*streamlit[-_.]listview\s*==\s*([^\s;#]+)", _read(DEMO_REQUIREMENTS)
    )
    assert pins == [_project_version(_read(ROOT_PYPROJECT))]


def test_root_packagedata_bundles_build_and_nested_manifest():
    text = _read(ROOT_PYPROJECT)
    # package-data must ship the built frontend AND the nested pyproject manifest
    assert "frontend/build/**/*" in text
    assert re.search(r'package-data[\s\S]*pyproject\.toml', text), (
        "root package-data must include the nested pyproject.toml"
    )


def test_nested_manifest_declares_component():
    text = _read(NESTED_PYPROJECT)
    assert "[[tool.streamlit.component.components]]" in text
    assert re.search(r'(?m)^\s*asset_dir\s*=\s*"frontend/build"', text)
    # The component segment stays "listview"; the manifest's [project] name is
    # "streamlit_listview" (canonically matches the distribution "streamlit-listview"),
    # so the qualified name is "streamlit_listview.listview" — matching
    # st.components.v2.component(...) in __init__.py.
    names = re.findall(r'(?m)^\s*name\s*=\s*"([^"]+)"', text)
    assert "listview" in names
    assert "streamlit_listview" in names


def test_init_registers_qualified_name():
    init = _read(ROOT / "streamlit_listview" / "__init__.py")
    assert '"streamlit_listview.listview"' in init


# ── scripts/verify_wheel.py ──────────────────────────────────────────────────

_DIST_INFO = f"streamlit_listview-{EXPECTED_VERSION}.dist-info"


def _fake_wheel(tmp_path: Path, entries: list[str]) -> Path:
    """Zip up `entries` under a correctly named wheel filename."""
    wheel = tmp_path / f"streamlit_listview-{EXPECTED_VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        for name in entries:
            zf.writestr(name, "x")
    return wheel


def _good_entries() -> list[str]:
    return [
        "streamlit_listview/frontend/build/index-abc123.js",
        "streamlit_listview/frontend/build/index-abc123.css",
        "streamlit_listview/pyproject.toml",
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
    assert "unexpected files under frontend/build/: " \
           "streamlit_listview/frontend/build/extra.txt" in str(exc.value)


def test_verify_wheel_rejects_a_leaked_build_backend(monkeypatch, tmp_path):
    wheel = _fake_wheel(tmp_path, [*_good_entries(), "streamlit_listview/_build_backend.py"])
    with pytest.raises(SystemExit) as exc:
        _verify(monkeypatch, wheel)
    assert "must not ship _build_backend.py" in str(exc.value)
