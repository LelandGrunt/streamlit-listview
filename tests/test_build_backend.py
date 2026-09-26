"""Unit tests for the in-tree PEP 517 build backend (`_build_backend.py`).

The backend lives at the repo root (referenced by `backend-path` in pyproject),
so add the root to sys.path to import it. Only the Python control flow is tested
here — the skip switch, source/deps detection, npm commands, and the npm-missing
error. The real frontend build is verified by actually building a wheel (CI +
verify_wheel), not here. setuptools is imported lazily by the backend, so this
module imports even in a venv without setuptools.

Each test points `_FRONTEND` at a temp directory whose `src` / `node_modules`
presence drives the branch under test, and stubs `subprocess.run` so npm never
actually runs.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _build_backend as bb  # noqa: E402


def _frontend(tmp_path, *, src=True, node_modules=True, build=True):
    fe = tmp_path / "frontend"
    fe.mkdir()
    if src:
        (fe / "src").mkdir()
    if node_modules:
        (fe / "node_modules").mkdir()
    if build:
        bd = fe / "build"
        bd.mkdir()
        (bd / "index-abc123.js").write_text("// bundle", encoding="utf-8")
        (bd / "index-abc123.css").write_text("/* bundle */", encoding="utf-8")
    return fe


def test_exposes_pep517_hooks():
    for name in (
        "get_requires_for_build_wheel",
        "get_requires_for_build_sdist",
        "get_requires_for_build_editable",
        "prepare_metadata_for_build_wheel",
        "prepare_metadata_for_build_editable",
        "build_wheel",
        "build_sdist",
        "build_editable",
    ):
        assert callable(getattr(bb, name)), name


def test_skip_env_short_circuits_npm(monkeypatch, tmp_path):
    monkeypatch.setenv("LISTVIEW_SKIP_NPM_BUILD", "1")
    monkeypatch.setattr(bb, "_FRONTEND", _frontend(tmp_path))
    calls = []
    monkeypatch.setattr(bb.subprocess, "run", lambda *a, **k: calls.append(a))
    bb._run_npm_build()
    assert calls == [], "npm must not run when LISTVIEW_SKIP_NPM_BUILD=1"


def test_skip_env_without_bundle_raises(monkeypatch, tmp_path):
    # Skipping the npm build is only safe when build/ already ships the bundle.
    # If it does not, packaging would produce a wheel with no index-*.js/.css and
    # the component would fail to register at runtime, so the skip must fail loudly
    # rather than silently emit an asset-less wheel.
    monkeypatch.setenv("LISTVIEW_SKIP_NPM_BUILD", "1")
    monkeypatch.setattr(bb, "_FRONTEND", _frontend(tmp_path, build=False))
    called = []
    monkeypatch.setattr(bb.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(RuntimeError, match="bundle"):
        bb._run_npm_build()
    assert called == [], "npm must not run on the skip path"


def test_skip_env_with_duplicate_bundle_raises(monkeypatch, tmp_path):
    # The registration contract is EXACTLY one index-*.js / index-*.css: Streamlit's
    # glob resolver rejects several matches just as hard as none. A second (stale)
    # chunk next to the fresh one must therefore fail packaging, not sail through.
    monkeypatch.setenv("LISTVIEW_SKIP_NPM_BUILD", "1")
    fe = _frontend(tmp_path)
    (fe / "build" / "index-stale99.js").write_text("// leftover", encoding="utf-8")
    monkeypatch.setattr(bb, "_FRONTEND", fe)
    called = []
    monkeypatch.setattr(bb.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(RuntimeError, match=r"exactly one index-\*\.js — found 2"):
        bb._run_npm_build()
    assert called == [], "npm must not run on the skip path"


def test_no_src_without_bundle_raises(monkeypatch, tmp_path):
    # sdist->wheel with neither source nor a prebuilt bundle: fail loudly rather
    # than package an asset-less wheel.
    monkeypatch.delenv("LISTVIEW_SKIP_NPM_BUILD", raising=False)
    monkeypatch.setattr(bb, "_FRONTEND", _frontend(tmp_path, src=False, build=False))
    with pytest.raises(RuntimeError, match="bundle"):
        bb._run_npm_build()


def test_runs_only_build_when_node_modules_present(monkeypatch, tmp_path):
    monkeypatch.delenv("LISTVIEW_SKIP_NPM_BUILD", raising=False)
    monkeypatch.setattr(bb, "_FRONTEND", _frontend(tmp_path, node_modules=True))
    monkeypatch.setattr(bb.shutil, "which", lambda _: "/usr/bin/npm")
    calls = []
    monkeypatch.setattr(bb.subprocess, "run", lambda cmd, **k: calls.append((cmd, k)))
    bb._run_npm_build()
    # npm is invoked via an argument VECTOR (resolved through shutil.which),
    # never a shell string, so no shell metacharacter can be interpreted —
    # injection-proof regardless of future edits.
    assert [c for c, _ in calls] == [["/usr/bin/npm", "run", "build"]]
    assert all(k.get("shell") is not True for _, k in calls)


def test_installs_deps_when_node_modules_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("LISTVIEW_SKIP_NPM_BUILD", raising=False)
    monkeypatch.setattr(bb, "_FRONTEND", _frontend(tmp_path, node_modules=False))
    monkeypatch.setattr(bb.shutil, "which", lambda _: "/usr/bin/npm")
    calls = []
    monkeypatch.setattr(bb.subprocess, "run", lambda cmd, **k: calls.append((cmd, k)))
    bb._run_npm_build()
    assert [c for c, _ in calls] == [
        ["/usr/bin/npm", "ci"],
        ["/usr/bin/npm", "run", "build"],
    ]
    assert all(k.get("shell") is not True for _, k in calls)


def test_skips_when_no_frontend_src(monkeypatch, tmp_path):
    # sdist scenario: no frontend/src, the prebuilt bundle is used as-is.
    monkeypatch.delenv("LISTVIEW_SKIP_NPM_BUILD", raising=False)
    monkeypatch.setattr(bb, "_FRONTEND", _frontend(tmp_path, src=False))
    calls = []
    monkeypatch.setattr(bb.subprocess, "run", lambda *a, **k: calls.append(a))
    bb._run_npm_build()
    assert calls == [], "npm must not run when frontend/src is absent"


def test_npm_missing_raises_runtimeerror(monkeypatch, tmp_path):
    # npm not on PATH -> friendly RuntimeError, and npm is never invoked.
    # (shutil.which is the real detection path; a missing npm under shell=True
    # would otherwise surface only as an opaque CalledProcessError.)
    monkeypatch.delenv("LISTVIEW_SKIP_NPM_BUILD", raising=False)
    monkeypatch.setattr(bb, "_FRONTEND", _frontend(tmp_path))
    monkeypatch.setattr(bb.shutil, "which", lambda _: None)
    called = []
    monkeypatch.setattr(bb.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(RuntimeError, match="Node.js"):
        bb._run_npm_build()
    assert called == [], "npm must not be invoked when it is not on PATH"
