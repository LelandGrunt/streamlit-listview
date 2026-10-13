"""scripts/smoke_wheel.py: the listview renders from an installed wheel.

The real run installs Streamlit from PyPI, so these tests drive it through a
recording runner. The check that runs in the new environment runs here for
real, against the editable install and the built bundle.
"""

import json
import runpy
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import smoke_wheel

BUILD = "streamlit_listview/frontend/build"
JS, CSS = "index-abc.js", "index-def.css"
GOOD = [f"{BUILD}/{JS}", f"{BUILD}/{CSS}", "streamlit_listview/__init__.py"]


def _wheel(tmp_path: Path, entries: list[str]) -> Path:
    wheel = tmp_path / "streamlit_listview-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        for name in entries:
            zf.writestr(name, "x")
    return wheel


def _report(venv: Path, **changes):
    """What the check prints for a listview rendered from `venv`."""
    module = venv / "Lib" / "site-packages" / "streamlit_listview" / "__init__.py"
    report = {"module": str(module), "exceptions": [], "js": [JS], "css": [CSS]}
    return {**report, **changes}


def test_bundle_names_the_wheels_js_and_css(tmp_path):
    assert smoke_wheel.bundle(_wheel(tmp_path, GOOD)) == (JS, CSS)


@pytest.mark.parametrize(
    "entries", [GOOD[1:], [*GOOD, f"{BUILD}/index-xyz.js"]], ids=["no-js", "two-js"]
)
def test_bundle_needs_exactly_one_js_and_one_css(tmp_path, entries):
    with pytest.raises(smoke_wheel.SmokeError, match=r"exactly one index-\*\.js"):
        smoke_wheel.bundle(_wheel(tmp_path, entries))


def test_bundle_names_a_wheel_it_cannot_open(tmp_path):
    with pytest.raises(smoke_wheel.SmokeError, match="cannot open"):
        smoke_wheel.bundle(tmp_path / "none.whl")


def test_a_listview_from_the_new_environment_passes(tmp_path):
    assert smoke_wheel.problems(_report(tmp_path), tmp_path, JS, CSS) == []


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        (
            {"module": str(ROOT / "streamlit_listview" / "__init__.py")},
            (
                "Python imported streamlit_listview from "
                f"{ROOT / 'streamlit_listview' / '__init__.py'}, outside the new "
                "environment"
            ),
        ),
        ({"module": None}, "Python found no streamlit_listview in the new environment"),
        ({"exceptions": ["boom"]}, "the app raised: boom"),
        ({"js": [], "css": []}, "the app rendered 0 listviews, expected 1"),
        (
            {"js": ["index-old.js"]},
            "Streamlit resolved the JS to index-old.js; the wheel ships index-abc.js",
        ),
        (
            {"css": ["index-old.css"]},
            (
                "Streamlit resolved the CSS to index-old.css; the wheel ships "
                "index-def.css"
            ),
        ),
    ],
)
def test_a_problem_is_named(tmp_path, changes, expected):
    found = smoke_wheel.problems(_report(tmp_path, **changes), tmp_path, JS, CSS)
    # One problem each; a message may go on to name the environment.
    assert len(found) == 1
    assert found[0].startswith(expected)


class Runner:
    """Records each command; makes the new environment's interpreter and
    answers the check with a canned report."""

    def __init__(self, report=None):
        self.report = report
        self.calls: list[tuple[list[str], Path]] = []
        self.venv: Path | None = None

    def __call__(self, args: list[str], cwd: Path) -> str:
        self.calls.append((args, cwd))
        if args[:2] == ["uv", "venv"]:
            self.venv = Path(args[2])
            # Both layouts, so the test passes on Windows and on POSIX.
            for python in (
                self.venv / "Scripts" / "python.exe",
                self.venv / "bin" / "python",
            ):
                python.parent.mkdir(parents=True)
                python.write_text("", encoding="utf-8")
                python.chmod(0o755)
            return ""
        if "-I" in args:
            assert self.venv is not None, "the check ran before uv venv"
            report = self.report or _report(self.venv)
            return "a warning\n" + json.dumps(report) + "\n"
        return ""


def test_smoke_installs_the_wheel_in_a_new_environment(tmp_path):
    wheel = _wheel(tmp_path, GOOD)
    runner = Runner()
    assert smoke_wheel.smoke(wheel, runner) == []
    (venv_args, cwd), (install_args, _), (check_args, check_cwd) = runner.calls
    assert venv_args[:2] == ["uv", "venv"]
    assert venv_args[3:] == ["--python", sys.executable]
    assert install_args[:4] == ["uv", "pip", "install", "--python"]
    assert install_args[4] == check_args[0]
    assert install_args[5] == str(wheel)
    # Not the repository, or Python would import the package from the source.
    assert check_cwd == cwd != ROOT
    assert check_args[1:] == ["-I", "-c", smoke_wheel.CHECK]


def test_smoke_reports_what_the_check_found(tmp_path):
    runner = Runner(report={"module": None, "exceptions": [], "js": [JS], "css": [CSS]})
    found = smoke_wheel.smoke(_wheel(tmp_path, GOOD), runner)
    assert found == ["Python found no streamlit_listview in the new environment"]


@pytest.mark.parametrize("output", ["", "a warning\n"])
def test_smoke_names_a_check_that_printed_no_report(tmp_path, output):
    runner = Runner()

    def run(args, cwd):
        # uv's steps as usual; the check prints `output` instead of a report.
        return output if "-I" in args else runner(args, cwd)

    with pytest.raises(smoke_wheel.SmokeError, match="printed no report"):
        smoke_wheel.smoke(_wheel(tmp_path, GOOD), run)


def test_smoke_names_an_environment_without_python(tmp_path):
    def run(args, cwd):
        return ""  # creates nothing, not even the environment

    with pytest.raises(smoke_wheel.SmokeError, match="uv created no Python"):
        smoke_wheel.smoke(_wheel(tmp_path, GOOD), run)


def test_the_check_reports_what_streamlit_resolved(tmp_path):
    """CHECK itself, against the editable install and the built bundle."""
    out = smoke_wheel._run([sys.executable, "-I", "-c", smoke_wheel.CHECK], tmp_path)
    report = json.loads(out.splitlines()[-1])
    build = ROOT / BUILD
    assert report["exceptions"] == []
    assert report["js"] == [next(build.glob("index-*.js")).name]
    assert report["css"] == [next(build.glob("index-*.css")).name]
    assert Path(report["module"]).is_relative_to(ROOT / "streamlit_listview")


def test_run_returns_the_output_and_names_a_failed_command(tmp_path):
    ok = [sys.executable, "-c", "print('out')"]
    assert smoke_wheel._run(ok, tmp_path).strip() == "out"
    failing = [sys.executable, "-c", "import sys; sys.exit('broken')"]
    with pytest.raises(smoke_wheel.SmokeError, match=r"(?s)exit code 1.*broken"):
        smoke_wheel._run(failing, tmp_path)


def test_run_passes_no_input(tmp_path):
    """A command that waits for input fails instead of hanging."""
    reads = [sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"]
    assert smoke_wheel._run(reads, tmp_path).strip() == "''"


@pytest.mark.parametrize(
    ("outcome", "code", "printed"),
    [
        ([], 0, "PASS: the listview renders from streamlit_listview-1.2.3"),
        (["the app raised: boom"], 1, "FAIL: the app raised: boom"),
        (smoke_wheel.SmokeError("uv failed"), 1, "FAIL: uv failed"),
    ],
)
def test_main_exits_with_the_outcome(
    tmp_path, monkeypatch, capsys, outcome, code, printed
):
    def smoke(wheel):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(smoke_wheel, "smoke", smoke)
    assert smoke_wheel.main([str(_wheel(tmp_path, GOOD))]) == code
    assert printed in capsys.readouterr().out


def test_main_defaults_to_the_newest_wheel(tmp_path, monkeypatch, capsys):
    wheel = _wheel(tmp_path, GOOD)
    monkeypatch.setattr(smoke_wheel.verify_wheel, "_newest_wheel", lambda: wheel)
    monkeypatch.setattr(smoke_wheel, "smoke", lambda wheel: [])
    assert smoke_wheel.main([]) == 0
    assert wheel.name in capsys.readouterr().out


def test_smoke_wheel_runs_main_as_a_script(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["smoke_wheel.py", str(tmp_path / "none.whl")])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "scripts" / "smoke_wheel.py"), run_name="__main__")
    assert exc.value.code == 1
    assert "FAIL: cannot open" in capsys.readouterr().out
