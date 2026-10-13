"""One-command generator for the hero GIF and the recordings of every scenario.

For each chosen scenario it serves the capture page (app.py) once per take,
plays the take in Chromium, and assembles the frames into a looping GIF:

    python scripts/gif/generate.py                       # the hero: assets/listview-demo.gif
    python scripts/gif/generate.py --all --record bench-results/visual/before   # frames, no GIF

Prereqs: the package installed with a built frontend bundle, and Playwright's
Chromium. See scripts/gif/README.md.
"""

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
ASSETS = REPO_ROOT / "assets"
APP = HERE / "app.py"

# capture.py, make_gif.py, stage.py and scenarios/ live alongside this file. The
# repo root goes on the path for the e2e suite's Streamlit runner: launching a
# harness on a free port and waiting for it to be healthy is the same job here
# as there, so it has one implementation.
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))
from capture import CaptureError, capture
from e2e.e2e_utils import StreamlitRunner
from make_gif import build_gif, validate_gif_params
from scenarios import SCENARIOS
from stage import Scenario

# Generous on purpose: this may be the first run after a fresh install, with a
# cold component bundle still to serve.
STARTUP_TIMEOUT_S = 90
# The capture page reads the scenario and the take to render from these.
ENV_SCENARIO = "LISTVIEW_GIF_SCENARIO"
ENV_TAKE = "LISTVIEW_GIF_TAKE"


def _tail(text: str, n: int = 40) -> str:
    """Return the last ``n`` lines of a captured server report, for diagnostics."""
    lines = text.splitlines()
    return "\n".join(lines[-n:]) if lines else "(no output captured)"


def _serve(
    app: Path,
    want_port: int,
    extra_args: Sequence[str] = (),
    extra_env: dict[str, str] | None = None,
) -> StreamlitRunner:
    """Launch Streamlit until healthy; return the running runner.

    For an auto-picked port, retry on a fresh runner (hence a fresh port) if the
    server dies before becoming healthy (covers a lost port race / transient
    failure); a user-supplied ``--port`` is tried once and not reassigned.
    Raises SystemExit with the captured server output if it never comes up.
    """
    attempts = 1 if want_port else 3
    last_output = ""
    for _ in range(attempts):
        runner = StreamlitRunner(
            app,
            server_port=want_port or None,
            extra_args=list(extra_args),
            startup_timeout=STARTUP_TIMEOUT_S,
            extra_env=extra_env,
        )
        try:
            runner.start()
        except RuntimeError as exc:
            # start() has already stopped the subprocess and folded its captured
            # stdout+stderr into the message — the only diagnostic left to show.
            last_output = str(exc)
            continue
        return runner
    # No second header here: start()'s message already frames the server output.
    raise SystemExit(
        f"Streamlit did not become healthy in {attempts} attempt(s).\n"
        + _tail(last_output)
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line; ``scenarios`` holds the chosen Scenario objects."""
    ap = argparse.ArgumentParser(
        description="Regenerate the hero GIF, or record the scenarios' frames."
    )
    ap.add_argument(
        "--scenario",
        action="append",
        choices=list(SCENARIOS),
        metavar="NAME",
        help=f"a scenario to run, repeatable; one of: {', '.join(SCENARIOS)}",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="every scenario, test scenarios included (needs --record)",
    )
    ap.add_argument(
        "--record",
        metavar="DIR",
        help="save the frames to DIR/<scenario>/ for compare.py instead of GIFs",
    )
    ap.add_argument(
        "--overwrite", action="store_true", help="let --record replace DIR's recording"
    )
    ap.add_argument(
        "--out", help="output GIF path for a single scenario (default: assets/)"
    )
    ap.add_argument("--port", type=int, default=0, help="0 = pick a free port")
    # None until _choose fills in the GIF defaults, so --record can tell a given
    # option from a default one.
    ap.add_argument("--scale", type=float, help="GIF downscale factor (> 0; 0.5)")
    ap.add_argument("--colors", type=int, help="GIF palette size (2-256; 256)")
    ap.add_argument(
        "--keep-frames",
        action="store_true",
        help="keep the PNG frames under build/gif-frames/<scenario>/",
    )
    args = ap.parse_args(argv)
    args.scenarios = _choose(ap, args)
    return args


def _choose(ap: argparse.ArgumentParser, args: argparse.Namespace) -> list[Scenario]:
    """The scenarios the options name; a usage error for a combination that fails."""
    # A blank path, such as an unset shell variable, would otherwise read as
    # an absent option: --record "" would build the hero GIF in assets/.
    for option, value in (("--record", args.record), ("--out", args.out)):
        if value is not None and not value.strip():
            ap.error(f"{option} needs a path, got {value!r}")
    if args.all and args.scenario:
        ap.error("choose one of --all and --scenario")
    if args.all:
        if not args.record:
            ap.error("--all needs --record DIR: test scenarios build no GIF")
        chosen = list(SCENARIOS.values())
    elif args.scenario:
        chosen = [SCENARIOS[name] for name in dict.fromkeys(args.scenario)]
    else:
        chosen = [SCENARIOS["hero"]]
    if args.record:
        _check_record(ap, args)
    else:
        _check_gif(ap, args, chosen)
    return chosen


def _check_record(ap: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """A usage error for a GIF option, or for a recording --record would replace."""
    gif_options = {
        "--out": args.out,
        "--scale": args.scale,
        "--colors": args.colors,
        "--keep-frames": args.keep_frames,
    }
    # Identity, not truthiness or equality: `--scale 0` is given, and wrong,
    # as much as `--scale 2`, and 0 == False.
    given = [
        name
        for name, value in gif_options.items()
        if value is not None and value is not False
    ]
    if given:
        ap.error(f"--record builds no GIF, so it takes no {', '.join(given)}")
    if (Path(args.record) / "meta.json").exists() and not args.overwrite:
        ap.error(f"{args.record} holds a recording; pass --overwrite to replace it")


def _check_gif(
    ap: argparse.ArgumentParser, args: argparse.Namespace, chosen: list[Scenario]
) -> None:
    """Fill in the GIF defaults; a usage error for an option a GIF cannot take."""
    if args.overwrite:
        ap.error("--overwrite needs --record DIR: it replaces a recording, not a GIF")
    args.scale = 0.5 if args.scale is None else args.scale
    args.colors = 256 if args.colors is None else args.colors
    test_only = [s.name for s in chosen if not s.gallery]
    if test_only:
        ap.error(
            "test scenarios build no GIF; record them with --record DIR: "
            + ", ".join(test_only)
        )
    if args.out and len(chosen) != 1:
        ap.error("--out names one GIF: use it with a single --scenario")
    # Validate at argument time so a typo fails immediately, not after the
    # capture has run. Same rules build_gif itself enforces.
    try:
        validate_gif_params(args.out or "out.gif", args.scale, args.colors)
    except ValueError as exc:
        ap.error(str(exc))


def run_scenario(
    scenario: Scenario, frames_dir: Path, port: int, *, one_size: bool = True
) -> str:
    """Play every take of ``scenario``, each on its own server.

    Writes frame_NNN.png files and frames.json to ``frames_dir``, replacing an
    earlier run's, and returns the Chromium version. With ``one_size`` (a GIF) a
    gallery scenario's takes must share the first take's frame size; a
    recording lets them differ, because compare.py reports the change.
    """
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("frame_*.png"):
        old.unlink()
    # Drop a stale manifest first, so an aborted run cannot leave a frames.json
    # that names frames this run just deleted.
    (frames_dir / "frames.json").unlink(missing_ok=True)
    frames: list[dict[str, Any]] = []
    clip_size: tuple[float, float] | None = None
    chromium = ""
    for take in scenario.takes:
        env = {ENV_SCENARIO: scenario.name, ENV_TAKE: take.name}
        runner = _serve(APP, port, take.server_args, env)
        print(f"{scenario.name}/{take.name}: serving on {runner.server_url}")
        try:
            result = capture(
                runner.server_url,
                frames_dir,
                scenario,
                take,
                frames,
                clip_size if scenario.gallery and one_size else None,
            )
        except Exception as exc:
            # The server's report often says why a take failed: an exception in
            # page() reaches the browser only as a timeout. runner.stop() in the
            # finally clause runs after this read.
            where = (
                ""
                if isinstance(exc, CaptureError)
                else f"scenario {scenario.name!r}, take {take.name!r}: "
            )
            output = runner._read_output()
            raise SystemExit(
                f"{where}{exc}\n--- server output ---\n{_tail(output)}"
            ) from exc
        finally:
            runner.stop()
        if clip_size is None:
            clip_size = result.clip_size
        chromium = result.chromium
    (frames_dir / "frames.json").write_text(
        json.dumps(frames, indent=1), encoding="utf-8"
    )
    print(f"{scenario.name}: {len(frames)} frames")
    return chromium


def write_meta(root: Path, scenarios: list[str], chromium: str) -> None:
    """Write meta.json, which marks ``root`` as a complete recording."""
    spec = importlib.util.find_spec("streamlit_listview")
    package = (
        Path(spec.origin).parent
        if spec is not None and spec.origin is not None
        else REPO_ROOT / "streamlit_listview"
    )
    bundles = sorted((package / "frontend" / "build").glob("index-*.js"))
    git = subprocess.run(
        ["git", "describe", "--always", "--dirty"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    meta = {
        "git": git,
        "bundle": bundles[0].name if bundles else "",
        "chromium": chromium,
        "playwright": importlib.metadata.version("playwright"),
        "streamlit": importlib.metadata.version("streamlit"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenarios": scenarios,
    }
    (root / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.record:
        root = Path(args.record)
        root.mkdir(parents=True, exist_ok=True)
        # No meta.json until every scenario has finished: compare.py reads a
        # missing meta.json as an aborted recording.
        (root / "meta.json").unlink(missing_ok=True)
        chromium = ""
        for scenario in args.scenarios:
            chromium = run_scenario(
                scenario, root / scenario.name, args.port, one_size=False
            )
        write_meta(root, [s.name for s in args.scenarios], chromium)
        print(f"recorded {len(args.scenarios)} scenario(s) in {root}")
        return 0
    for scenario in args.scenarios:
        out = Path(args.out) if args.out else ASSETS / scenario.gif_file
        if args.keep_frames:
            frames_dir = REPO_ROOT / "build" / "gif-frames" / scenario.name
            run_scenario(scenario, frames_dir, args.port)
            build_gif(frames_dir, out, args.scale, args.colors)
        else:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                run_scenario(scenario, Path(tmp), args.port)
                build_gif(Path(tmp), out, args.scale, args.colors)
        print(f"wrote {out} | {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
