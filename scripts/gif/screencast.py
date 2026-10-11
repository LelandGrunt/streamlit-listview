"""Record a tour of the demo app with Streamlit's own "Record screen".

Playwright opens the demo (demo/app.py) in headless Chromium, starts "Record
screen" from the app menu, plays the tour in real time, stops the recording
with Esc and saves the video Streamlit offers for download. ffmpeg then turns
the video into the README's GIF, assets/listview-tour.gif:

    LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel --with imageio-ffmpeg python scripts/gif/screencast.py

See scripts/gif/README.md.
"""

import argparse
import importlib
import math
import shutil
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from playwright.sync_api import Locator, Page, ViewportSize, sync_playwright

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DEMO_APP = REPO_ROOT / "demo" / "app.py"
DEFAULT_OUT = REPO_ROOT / "assets" / "listview-tour.gif"
# The recording stays here (gitignored), next to failure.png when a step fails.
WORK_DIR = REPO_ROOT / "build" / "screencast"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))
from generate import _serve, _tail

FFMPEG_HINT = (
    "ffmpeg not found. Run the script with it added for this run:\n"
    "  LISTVIEW_SKIP_NPM_BUILD=1 uv run --extra devel --with imageio-ffmpeg "
    "python scripts/gif/screencast.py\n"
    "or put an ffmpeg on the PATH."
)

VIEWPORT: ViewportSize = {"width": 1280, "height": 800}
# The local server shows a Deploy button in the toolbar; viewer mode hides it and
# keeps the app menu with "Record screen".
SERVER_ARGS = ("--client.toolbarMode", "viewer")
# Chromium accepts a capture of the requesting tab without its picker. Never add
# --use-fake-ui-for-media-stream: it answers getDisplayMedia with the whole
# monitor, so the video shows the desktop of whoever runs this script.
LAUNCH_ARGS = ("--auto-accept-this-tab-capture",)

# Streamlit calls getDisplayMedia({video: true}). This asks for the current tab
# instead, excludes screens, and stops any stream that is not a browser tab
# before Streamlit's recorder sees it.
TAB_ONLY_JS = """
(() => {
  const original = MediaDevices.prototype.getDisplayMedia;
  window.__tourSurface = null;
  MediaDevices.prototype.getDisplayMedia = async function (constraints) {
    const stream = await original.call(this, {
      ...constraints,
      preferCurrentTab: true,
      selfBrowserSurface: "include",
      surfaceSwitching: "exclude",
      monitorTypeSurfaces: "exclude",
    });
    const surface = stream.getVideoTracks()[0]?.getSettings().displaySurface;
    window.__tourSurface = surface ?? "none";
    if (surface !== "browser") {
      stream.getTracks().forEach((track) => track.stop());
      throw new Error(`capture refused: the source is ${surface}, not this tab`);
    }
    return stream;
  };
})();
"""

# Counts finished script runs: Streamlit sets data-test-script-state on its app
# root, and each change to "notRunning" ends a run.
RUNS_JS = """
(() => {
  window.__tourRuns = 0;
  new MutationObserver((records) => {
    for (const r of records) {
      if (r.target.getAttribute("data-test-script-state") === "notRunning"
          && r.oldValue !== "notRunning") window.__tourRuns++;
    }
  }).observe(document, {
    subtree: true, attributes: true, attributeOldValue: true,
    attributeFilter: ["data-test-script-state"],
  });
})();
"""

# A tab capture shows no mouse pointer, so the page draws one: an arrow that
# follows mousemove and a ring that marks each mousedown.
CURSOR_JS = """
addEventListener("DOMContentLoaded", () => {
  const arrow = document.createElement("div");
  arrow.innerHTML = `<svg width="22" height="30" viewBox="0 0 22 30"
    xmlns="http://www.w3.org/2000/svg"><path d="M2 2 L2 24 L8 18.5 L12.5 28
    L16.5 26.2 L12 16.8 L19.5 16.8 Z" fill="#111" stroke="#fff"
    stroke-width="2" stroke-linejoin="round"/></svg>`;
  Object.assign(arrow.style, {
    position: "fixed", left: "0", top: "0", zIndex: "2147483647",
    pointerEvents: "none", transform: "translate(-60px, -60px)",
  });
  document.documentElement.appendChild(arrow);
  addEventListener("mousemove", (e) => {
    arrow.style.transform = `translate(${e.clientX - 2}px, ${e.clientY - 2}px)`;
  }, true);
  addEventListener("mousedown", (e) => {
    const ring = document.createElement("div");
    Object.assign(ring.style, {
      position: "fixed", left: `${e.clientX - 16}px`, top: `${e.clientY - 16}px`,
      width: "32px", height: "32px", borderRadius: "50%",
      border: "3px solid rgba(255, 75, 75, 0.85)", boxSizing: "border-box",
      zIndex: "2147483646", pointerEvents: "none",
      transition: "transform 400ms ease-out, opacity 400ms ease-out",
    });
    document.documentElement.appendChild(ring);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      ring.style.transform = "scale(1.6)";
      ring.style.opacity = "0";
    }));
    setTimeout(() => ring.remove(), 500);
  }, true);
});
"""

RERUN_TIMEOUT_MS = 60_000
# The pause after each change, so a viewer sees what it did.
BEAT_MS = 900
# Time between two steps of a pointer glide (about one frame at 60 Hz).
GLIDE_STEP_MS = 16


class Tour:
    """The pointer, the keyboard and the waits that the tour steps use."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.x = VIEWPORT["width"] / 2
        self.y = VIEWPORT["height"] / 2

    def runs(self) -> int:
        return cast(int, self.page.evaluate("window.__tourRuns"))

    @contextmanager
    def rerun(self) -> Generator[None]:
        """Wait until a script run ends after the action in the block."""
        before = self.runs()
        yield
        self.page.wait_for_function(
            f"window.__tourRuns > {before}", timeout=RERUN_TIMEOUT_MS
        )

    def beat(self, ms: int = BEAT_MS) -> None:
        self.page.wait_for_timeout(ms)

    def glide(self, x: float, y: float) -> None:
        """Move the pointer to (x, y) in visible steps, easing in and out."""
        distance = math.hypot(x - self.x, y - self.y)
        steps = max(6, min(28, round(distance / 22)))
        x0, y0 = self.x, self.y
        for i in range(1, steps + 1):
            t = i / steps
            eased = t * t * (3 - 2 * t)
            self.page.mouse.move(x0 + (x - x0) * eased, y0 + (y - y0) * eased)
            self.page.wait_for_timeout(GLIDE_STEP_MS)
        self.x, self.y = x, y

    def glide_to(self, target: Locator) -> None:
        """Glide to the centre of ``target``."""
        target.scroll_into_view_if_needed()
        box = target.bounding_box()
        if box is None:
            raise RuntimeError(f"{target} has no box")
        self.glide(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    def click(self, target: Locator) -> None:
        self.glide_to(target)
        self.page.wait_for_timeout(120)
        self.page.mouse.down()
        self.page.mouse.up()

    def type(self, text: str) -> None:
        self.page.keyboard.type(text, delay=140)

    def press(self, key: str) -> None:
        if key == "Escape":
            raise ValueError(
                "Esc stops the recording; record() presses it after the tour"
            )
        self.page.keyboard.press(key)

    # Locators -----------------------------------------------------------------

    def listview(self) -> Locator:
        return self.page.get_by_test_id("stListview").first

    def row(self, option_id: str) -> Locator:
        return self.page.get_by_test_id(f"stListviewOption-{option_id}")

    def segment(self, name: str) -> Locator:
        """An st.pills or st.segmented_control option: a button with role radio."""
        return self.page.get_by_role("radio", name=name, exact=True).first

    section = segment

    def toggle(self, label: str) -> Locator:
        """The switch of the st.toggle with ``label``: the first box in its label."""
        return (
            self.page.get_by_test_id("stCheckbox")
            .filter(has_text=label)
            .locator("label > div")
            .first
        )

    def selectbox(self, label: str) -> Locator:
        return (
            self.page.get_by_test_id("stSelectbox")
            .filter(has=self.page.get_by_text(label, exact=True))
            .get_by_role("combobox")
            .first
        )

    def multiselect(self, label: str) -> Locator:
        return (
            self.page.get_by_test_id("stMultiSelect")
            .filter(has=self.page.get_by_text(label, exact=True))
            .get_by_role("combobox")
            .first
        )

    def option(self, name: str) -> Locator:
        return self.page.get_by_role("option", name=name, exact=True).first


def play_tour(tour: Tour) -> None:
    """The tour: about 50 seconds through the demo's main features."""
    page = tour.page
    tour.beat(600)

    # Selection and search.
    with tour.rerun():
        tour.click(tour.segment("multi"))
    tour.beat()
    for city in ("berlin", "munich", "cologne"):
        with tour.rerun():
            tour.click(tour.row(city))
        tour.beat(300)
    tour.click(tour.listview().get_by_test_id("stListviewSearch"))
    tour.type("an")
    tour.beat(1000)
    tour.click(tour.listview().get_by_test_id("stListviewSearchClear"))
    tour.beat()

    # Groups and sorting.
    with tour.rerun():
        tour.click(tour.section("Groups"))
    tour.beat(400)
    with tour.rerun():
        tour.click(tour.toggle("Collapsible groups"))
    tour.beat(400)
    tour.click(tour.listview().get_by_test_id("stListviewGroup").first)
    tour.beat()
    with tour.rerun():
        tour.click(tour.section("Sorting"))
    tour.beat(400)
    tour.click(tour.selectbox("Sort"))
    tour.beat(400)
    with tour.rerun():
        tour.click(tour.option("both"))
    tour.beat(1200)

    # A default at the end of the list: the list remounts and scrolls to it.
    with tour.rerun():
        tour.click(tour.section("Basic"))
    tour.beat(400)
    tour.click(tour.multiselect("Default"))
    tour.type("seattle")
    tour.beat(300)
    with tour.rerun():
        tour.press("Enter")
    # Tab closes the dropdown. Not Esc: Esc stops Streamlit's recording.
    tour.press("Tab")
    tour.beat(800)

    # Themes. The demo reruns once more inside the run that switches the theme
    # (see demo/themes.py), and the app root reports only the end of both.
    with tour.rerun():
        tour.click(tour.section("Theme"))
    tour.beat(400)
    for theme in ("Databricks Brand", "Snowflake Brand", "Streamlit default"):
        tour.click(tour.selectbox("Theme"))
        tour.beat(400)
        with tour.rerun():
            tour.click(tour.option(theme))
        tour.beat(1000)

    # 100,000 options: scroll, click, and search.
    with tour.rerun():
        tour.click(tour.section("Data"))
    tour.beat(400)
    with tour.rerun():
        tour.click(tour.segment("Large"))
    tour.beat(400)
    slider = page.get_by_test_id("stSlider").first
    tour.glide_to(slider.get_by_role("slider"))
    page.mouse.down()
    box = slider.bounding_box()
    if box is None:
        raise RuntimeError("the Items slider has no box")
    tour.glide(box["x"] + box["width"] + 30, tour.y)
    with tour.rerun():
        page.mouse.up()
    tour.row("item-99999").wait_for(state="attached", timeout=RERUN_TIMEOUT_MS)
    tour.beat(600)
    tour.glide_to(tour.listview().locator(".listview-body"))
    for _ in range(3):
        page.mouse.wheel(0, 600)
        tour.beat(250)
    tour.beat(300)
    with tour.rerun():
        tour.click(tour.listview().locator('[data-testid^="stListviewOption-"]').nth(6))
    tour.beat(500)
    tour.press("/")
    tour.type("99999")
    tour.beat(1200)

    # The sidebar: the list moves and keeps its selection.
    with tour.rerun():
        tour.click(tour.section("Layout"))
    tour.beat(400)
    with tour.rerun():
        tour.click(tour.toggle("Render widget in sidebar"))
    # The sidebar's own row: the main column's old row can still be attached
    # when the run ends.
    page.get_by_test_id("stSidebar").get_by_test_id(
        "stListviewOption-item-99999"
    ).wait_for(state="attached", timeout=RERUN_TIMEOUT_MS)
    tour.beat(1100)


def check_surface(surface: str | None) -> None:
    """Stop unless the capture source is a browser tab.

    TAB_ONLY_JS has already stopped any other stream; this stops the run.
    """
    if surface != "browser":
        raise SystemExit(f"refused to record: the capture source is {surface}")


def record(url: str, webm: Path) -> None:
    """Record the tour against the demo at ``url`` and save the video to ``webm``."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chromium", headless=True, args=list(LAUNCH_ARGS)
        )
        try:
            context = browser.new_context(viewport=VIEWPORT, accept_downloads=True)
            context.add_init_script(TAB_ONLY_JS)
            context.add_init_script(RUNS_JS)
            context.add_init_script(CURSOR_JS)
            page = context.new_page()
            page.goto(url)
            page.get_by_test_id("stListview").first.wait_for(timeout=90_000)
            page.wait_for_function("window.__tourRuns >= 1", timeout=90_000)
            page.get_by_test_id("stMainMenu").click()
            page.get_by_test_id("stMainMenuItem-recordScreencast").click()
            page.get_by_role("button", name="Start recording!").click()
            page.wait_for_function("window.__tourSurface !== null", timeout=15_000)
            check_surface(page.evaluate("window.__tourSurface"))
            # Streamlit counts down from 3 before its recorder starts. The
            # setup dialog leaves with the click, so waiting for the countdown
            # to leave is enough; a countdown that is already gone passes.
            page.get_by_test_id("stCountdown").wait_for(
                state="detached", timeout=15_000
            )
            try:
                play_tour(Tour(page))
            except Exception:
                WORK_DIR.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=WORK_DIR / "failure.png")
                raise
            # Esc stops the recording, unless a focused widget (such as the
            # theme select box) handles the key first.
            page.evaluate("document.activeElement?.blur()")
            page.keyboard.press("Escape")
            save = page.get_by_role("button", name="Save video to disk")
            save.wait_for(timeout=30_000)
            with page.expect_download() as download:
                save.click()
            download.value.save_as(webm)  # creates the parent directories
        finally:
            browser.close()


def find_ffmpeg() -> str:
    """Return an ffmpeg: imageio-ffmpeg's, else the one on the PATH.

    imageio-ffmpeg is no project dependency; ``uv run --with imageio-ffmpeg``
    adds it for one run, hence the import by name.
    """
    try:
        return cast(str, importlib.import_module("imageio_ffmpeg").get_ffmpeg_exe())
    except ModuleNotFoundError:
        pass
    found = shutil.which("ffmpeg")
    if found is None:
        raise SystemExit(FFMPEG_HINT)
    return found


def video_to_gif(ffmpeg: str, webm: Path, out: Path, width: int, fps: int) -> Path:
    """Convert the recording to a looping GIF ``width`` px wide.

    The video's frame rate varies, so ``fps`` samples it first. mpdecimate drops
    frames that barely differ from the one before, and the variable frame rate
    output gives their time to the frame that stays. One palette, computed from
    the changed pixels of every frame, keeps white white and the theme colors
    true; no dithering, so a still area stays still.
    """
    vf = (
        f"fps={fps},scale={width}:-1:flags=lanczos,mpdecimate,split[a][b];"
        "[a]palettegen=max_colors=256:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=none:diff_mode=rectangle"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(webm), "-vf", vf, "-fps_mode", "vfr", "-loop", "0", str(out),
    ]  # fmt: skip
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{_tail(result.stderr)}")
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="the GIF to write")
    ap.add_argument("--port", type=int, default=0, help="0 picks a free port")
    ap.add_argument("--width", type=int, default=960, help="GIF width in px")
    ap.add_argument("--fps", type=int, default=10, help="GIF frames per second")
    args = ap.parse_args(argv)
    if args.out.suffix.lower() != ".gif":
        ap.error(f"--out must end in .gif, got {args.out.name!r}")
    if not 1 <= args.width <= VIEWPORT["width"]:
        ap.error(f"--width must be 1 to {VIEWPORT['width']}, got {args.width}")
    if not 1 <= args.fps <= 30:
        ap.error(f"--fps must be 1 to 30, got {args.fps}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ffmpeg = find_ffmpeg()  # before the minute-long recording, not after it
    webm = WORK_DIR / "tour.webm"
    runner = _serve(DEMO_APP, args.port, SERVER_ARGS)
    try:
        record(runner.server_url, webm)
    except Exception as exc:
        raise SystemExit(f"{exc}\n{_tail(runner._read_output())}") from exc
    finally:
        runner.stop()
    out = video_to_gif(ffmpeg, webm, args.out, args.width, args.fps)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB); the video is {webm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
