"""Unit tests for the in-tree PEP 517 build backend (`_build_backend.py`).

The backend lives at the repo root (referenced by `backend-path` in pyproject),
so add the root to sys.path to import it. Only the Python control flow is tested
here — the skip switch, source/deps detection, npm commands, the npm-missing
error, the staged-copy cleanup, and which hook hands what to setuptools. The
module counts toward the 100 % coverage gate. The real frontend build is
verified by actually building a wheel (CI + verify_wheel), not here. setuptools
is imported lazily by the backend, so this module imports even in a venv
without setuptools.

Each test points `_FRONTEND` at a temp directory whose `src` / `node_modules`
presence drives the branch under test, and stubs `subprocess.run` so npm never
actually runs.
"""

import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _build_backend as bb


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


def test_build_wheel_drops_the_stale_package_copy(monkeypatch, tmp_path):
    # setuptools stages a wheel's files in build/lib and never deletes there, so
    # a bundle or a module from an earlier build would ship beside the current
    # files.
    stale = tmp_path / "build" / "lib" / "streamlit_listview"
    (stale / "frontend" / "build").mkdir(parents=True)
    (stale / "frontend" / "build" / "index-old123.js").write_text("// old", "utf-8")
    (stale / "_removed_module.py").write_text("# deleted since", encoding="utf-8")
    monkeypatch.setattr(bb, "_STALE_PACKAGE", stale)
    monkeypatch.setattr(bb, "_run_npm_build", lambda: None)
    seen = []

    class Backend:
        def build_wheel(self, *args):
            seen.append(stale.exists())
            return "streamlit_listview-1.0.1-py3-none-any.whl"

    monkeypatch.setattr(bb, "_backend", Backend)
    assert bb.build_wheel("dist") == "streamlit_listview-1.0.1-py3-none-any.whl"
    assert seen == [False]


def _stale_copy_with_a_module(monkeypatch, tmp_path):
    """Point build_wheel at a staged copy that holds one module.

    Returns the module and the list of calls that reach setuptools.
    """
    stale = tmp_path / "build" / "lib" / "streamlit_listview"
    stale.mkdir(parents=True)
    module = stale / "_removed_module.py"
    module.write_text("# deleted since", encoding="utf-8")
    monkeypatch.setattr(bb, "_STALE_PACKAGE", stale)
    monkeypatch.setattr(bb, "_run_npm_build", lambda: None)
    calls: list[tuple[object, ...]] = []

    class Backend:
        def build_wheel(self, *args):
            calls.append(args)
            return "streamlit_listview-1.0.1-py3-none-any.whl"

    monkeypatch.setattr(bb, "_backend", Backend)
    return module, calls


def test_build_wheel_stops_when_the_stale_copy_cannot_be_removed(monkeypatch, tmp_path):
    # A file another process holds open cannot be deleted on Windows; the copy
    # left behind would ship in the wheel. This is the error rmtree raises then.
    module, calls = _stale_copy_with_a_module(monkeypatch, tmp_path)

    def locked(path):
        raise PermissionError(
            13,
            "The process cannot access the file because it is being used by "
            "another process",
            str(module),
        )

    monkeypatch.setattr(bb.shutil, "rmtree", locked)
    with pytest.raises(RuntimeError, match=re.escape(str(module))):
        bb.build_wheel("dist")
    assert calls == []


def test_build_wheel_reports_an_error_without_strerror(monkeypatch, tmp_path):
    _module, calls = _stale_copy_with_a_module(monkeypatch, tmp_path)

    def failing(path):
        raise OSError("disk went away")

    monkeypatch.setattr(bb.shutil, "rmtree", failing)
    with pytest.raises(RuntimeError, match="disk went away") as exc:
        bb.build_wheel("dist")
    assert "None" not in str(exc.value)
    assert calls == []


@pytest.mark.skipif(
    sys.platform != "win32", reason="only Windows refuses to delete an open file"
)
def test_build_wheel_stops_on_a_real_file_lock(monkeypatch, tmp_path):
    module, calls = _stale_copy_with_a_module(monkeypatch, tmp_path)
    with (
        module.open(encoding="utf-8"),
        pytest.raises(RuntimeError, match=re.escape(str(module))),
    ):
        bb.build_wheel("dist")
    assert calls == []


def test_the_stale_copy_is_the_whole_staged_package():
    assert bb._STALE_PACKAGE == ROOT / "build" / "lib" / "streamlit_listview"


def test_build_wheel_needs_no_earlier_build(monkeypatch, tmp_path):
    monkeypatch.setattr(bb, "_STALE_PACKAGE", tmp_path / "build" / "lib")
    monkeypatch.setattr(bb, "_run_npm_build", lambda: None)

    class Backend:
        def build_wheel(self, *args):
            return "streamlit_listview-1.0.1-py3-none-any.whl"

    monkeypatch.setattr(bb, "_backend", Backend)
    assert bb.build_wheel("dist") == "streamlit_listview-1.0.1-py3-none-any.whl"


class _Recorder:
    """A stand-in for setuptools' build_meta that records each hook it gets."""

    def __init__(self, calls: list[tuple[str, tuple[object, ...]]]):
        self.calls = calls

    def __getattr__(self, hook: str):
        def call(*args: object) -> str:
            self.calls.append((hook, args))
            return hook

        return call


@pytest.mark.parametrize(
    ("hook", "args", "builds_the_bundle"),
    [
        ("get_requires_for_build_wheel", ({"k": "v"},), False),
        ("get_requires_for_build_sdist", ({"k": "v"},), False),
        ("get_requires_for_build_editable", ({"k": "v"},), False),
        ("prepare_metadata_for_build_wheel", ("meta", {"k": "v"}), False),
        ("prepare_metadata_for_build_editable", ("meta", {"k": "v"}), False),
        ("build_sdist", ("dist", {"k": "v"}), True),
        ("build_editable", ("dist", {"k": "v"}, "meta"), True),
    ],
)
def test_each_hook_hands_its_arguments_to_setuptools(
    monkeypatch, hook, args, builds_the_bundle
):
    # A hook that produces a distribution builds the bundle first; a hook that
    # only asks setuptools a question leaves npm alone.
    calls: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr(bb, "_backend", lambda: _Recorder(calls))
    monkeypatch.setattr(bb, "_run_npm_build", lambda: calls.append(("npm", ())))
    assert getattr(bb, hook)(*args) == hook
    npm = [("npm", ())] if builds_the_bundle else []
    assert calls == [*npm, (hook, args)]


def test_the_backend_is_setuptools_build_meta(monkeypatch):
    # setuptools is imported only when a hook runs, so a stand-in module shows
    # which backend the hooks delegate to.
    build_meta = object()
    setuptools = types.ModuleType("setuptools")
    setuptools.build_meta = build_meta  # ty: ignore[unresolved-attribute]
    monkeypatch.setitem(sys.modules, "setuptools", setuptools)
    assert bb._backend() is build_meta
