"""One-command generator for the README demo GIF.

Spawns the capture Streamlit page on a free port, waits until it is healthy,
captures the interaction frames, assembles the looping GIF, and stops the
server — all in a single run:

    python scripts/gif/generate.py                      # -> assets/listview-demo.gif
    python scripts/gif/generate.py --out out.gif --keep-frames

Prereqs: the package installed with a built frontend bundle, plus the capture
deps (Playwright + Chromium, Pillow) and ``requests`` — pulled in by the e2e
suite's Streamlit runner, which this script reuses. See scripts/gif/README.md.
"""

import argparse
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# capture.py / make_gif.py live alongside this file; import them as the modules
# this orchestrator drives. The repo root goes on the path for the e2e suite's
# Streamlit runner: launching a harness on a free port and waiting for it to be
# healthy is the same job here as there, so it has one implementation.
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))
from capture import capture  # noqa: E402
from e2e.e2e_utils import StreamlitRunner  # noqa: E402
from make_gif import build_gif, validate_gif_params  # noqa: E402

# Generous on purpose: this may be the first run after a fresh install, with a
# cold component bundle still to serve.
STARTUP_TIMEOUT_S = 90


def _tail(text: str, n: int = 40) -> str:
    """Return the last ``n`` lines of a captured server report, for diagnostics."""
    lines = text.splitlines()
    return "\n".join(lines[-n:]) if lines else "(no output captured)"


def _serve(app: Path, want_port: int) -> StreamlitRunner:
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
            app, server_port=want_port or None, startup_timeout=STARTUP_TIMEOUT_S
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate the README demo GIF.")
    ap.add_argument(
        "--out",
        default=str(REPO_ROOT / "assets" / "listview-demo.gif"),
        help="output GIF path (default: assets/listview-demo.gif)",
    )
    ap.add_argument("--port", type=int, default=0, help="0 = pick a free port")
    ap.add_argument("--scale", type=float, default=0.5, help="downscale factor (> 0)")
    ap.add_argument("--colors", type=int, default=256, help="GIF palette size (2-256)")
    ap.add_argument(
        "--keep-frames",
        action="store_true",
        help="keep the captured PNG frames under build/gif-frames/",
    )
    args = ap.parse_args()

    # Validate at argument time so a typo fails immediately, not after the
    # ~15s capture+encode pipeline has already run. Same rules build_gif itself
    # enforces — one implementation, surfaced as an argparse usage error.
    try:
        validate_gif_params(args.out, args.scale, args.colors)
    except ValueError as exc:
        ap.error(str(exc))

    app = HERE / "app.py"

    runner = None
    tmp = None
    try:
        runner = _serve(app, args.port)
        print(f"serving {app.name} on {runner.server_url}")

        if args.keep_frames:
            frames_dir = REPO_ROOT / "build" / "gif-frames"  # build/ is gitignored
            frames_dir.mkdir(parents=True, exist_ok=True)
        else:
            tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
            frames_dir = Path(tmp.name)

        n = capture(runner.server_url, frames_dir)
        print(f"captured {n} frames")

        # The server is no longer needed once the frames are on disk; stop it
        # before the CPU-bound encode so it can't linger if build_gif raises.
        runner.stop()

        out = build_gif(frames_dir, args.out, args.scale, args.colors)
        print(f"wrote {out} | {out.stat().st_size // 1024} KB")
    finally:
        if runner is not None:
            runner.stop()  # idempotent: a no-op after the early stop above
        if tmp is not None:
            tmp.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
