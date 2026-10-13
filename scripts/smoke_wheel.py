"""Install the built wheel into a new environment and render the listview there.

Usage: python scripts/smoke_wheel.py [path-to-wheel]
If no path is given, the newest dist/*.whl is used.

verify_wheel.py checks the files a wheel ships; this script checks that they
work once installed. It creates a virtual environment with uv, installs the
wheel and the newest Streamlit it admits from PyPI, and runs a listview there
through Streamlit's AppTest. AppTest finds the component through the installed
manifest and resolves the bundle's `index-*.js` and `index-*.css` globs as a
Streamlit server does, so a wheel whose manifest or bundle Streamlit cannot
use fails here. An editable install, as the test suites use, finds both in
the source tree instead. Needs uv on PATH and access to PyPI. Standard library
only, like scripts/push_gate.py, which runs it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import verify_wheel

BUILD = "streamlit_listview/frontend/build/"

# Runs in the new environment and prints one JSON line last. It locates the
# package without importing it: outside a Streamlit runtime, the import fails
# to declare the component.
CHECK = """
import importlib.util
import json

from streamlit.testing.v1 import AppTest

spec = importlib.util.find_spec("streamlit_listview")
app = AppTest.from_string(
    "from streamlit_listview import listview\\n"
    "listview('Smoke test', ['a', 'b'], key='smoke')\\n"
).run()
listviews = app.get("bidi_component")
print(json.dumps({
    "module": spec.origin if spec else None,
    "exceptions": [str(exception.value) for exception in app.exception],
    "js": [listview.proto.js_source_path for listview in listviews],
    "css": [listview.proto.css_source_path for listview in listviews],
}))
"""

# Runs a command in a directory and returns its output; raises SmokeError
# when the command fails.
Run = Callable[[list[str], Path], str]


class SmokeError(Exception):
    """The smoke test could not run, or a step of it failed."""


def bundle(wheel: Path) -> tuple[str, str]:
    """The file names of the wheel's index-*.js and index-*.css."""
    try:
        with zipfile.ZipFile(wheel) as zf:
            names = [n[len(BUILD) :] for n in zf.namelist() if n.startswith(BUILD)]
    except (OSError, zipfile.BadZipFile) as exc:
        raise SmokeError(f"cannot open {wheel}: {exc}") from exc
    found = []
    for suffix in (".js", ".css"):
        matches = [n for n in names if n.startswith("index-") and n.endswith(suffix)]
        if len(matches) != 1:
            raise SmokeError(
                f"{wheel.name} must ship exactly one index-*{suffix}, "
                f"found {len(matches)}"
            )
        found.append(matches[0])
    return found[0], found[1]


def problems(report: dict[str, Any], venv: Path, js: str, css: str) -> list[str]:
    """What keeps the check's report from showing a listview of this wheel."""
    found: list[str] = []
    module = report["module"]
    if module is None:
        found.append("Python found no streamlit_listview in the new environment")
    elif not Path(module).resolve().is_relative_to(venv.resolve()):
        found.append(
            f"Python imported streamlit_listview from {module}, outside the new "
            f"environment {venv}"
        )
    found += [f"the app raised: {message}" for message in report["exceptions"]]
    if len(report["js"]) != 1:
        found.append(f"the app rendered {len(report['js'])} listviews, expected 1")
        return found
    for kind, resolved, shipped in (
        ("JS", report["js"][0], js),
        ("CSS", report["css"][0], css),
    ):
        if resolved != shipped:
            found.append(
                f"Streamlit resolved the {kind} to {resolved}; the wheel ships {shipped}"
            )
    return found


def _run(args: list[str], cwd: Path) -> str:
    """Run a command without input; return its output, or raise SmokeError."""
    result = subprocess.run(
        args,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        raise SmokeError(
            f"{' '.join(args[:3])} failed with exit code {result.returncode}:\n{output}"
        )
    return result.stdout


def smoke(wheel: Path, run: Run = _run) -> list[str]:
    """Install `wheel` into a new environment; return what keeps it from working."""
    js, css = bundle(wheel)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        # The commands run in the temporary directory: from the repository,
        # Python would import the package from the source tree.
        cwd = Path(tmp)
        venv = cwd / "venv"
        run(["uv", "venv", str(venv), "--python", sys.executable], cwd)
        # One lookup for both layouts: Scripts\python.exe on Windows,
        # bin/python elsewhere.
        layouts = os.pathsep.join([str(venv / "Scripts"), str(venv / "bin")])
        python = shutil.which("python", path=layouts)
        if python is None:
            raise SmokeError(f"uv created no Python in {venv}")
        run(["uv", "pip", "install", "--python", python, str(wheel)], cwd)
        output = run([python, "-I", "-c", CHECK], cwd)
        lines = output.splitlines()
        try:
            report = json.loads(lines[-1] if lines else "")
        except ValueError as exc:
            raise SmokeError(f"the check printed no report: {output!r}") from exc
        return problems(report, venv, js, css)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    wheel = Path(args[0]) if args else verify_wheel._newest_wheel()
    print(f"Installing {wheel.name} into a new environment")
    try:
        found = smoke(wheel)
    except SmokeError as exc:
        found = [str(exc)]
    for problem in found:
        print(f"FAIL: {problem}")
    if found:
        return 1
    print(f"PASS: the listview renders from {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
