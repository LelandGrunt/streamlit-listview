"""The README tour (scripts/gif/screencast.py): capture guard, ffmpeg, options."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "gif"))

import screencast


def test_chromium_accepts_only_a_capture_of_its_own_tab():
    """--use-fake-ui-for-media-stream answers getDisplayMedia with the whole
    monitor, so a recording would show the desktop of whoever runs the script."""
    assert "--auto-accept-this-tab-capture" in screencast.LAUNCH_ARGS
    assert not [arg for arg in screencast.LAUNCH_ARGS if "fake" in arg]


@pytest.mark.parametrize("surface", ["monitor", "window", "none", None])
def test_check_surface_refuses_anything_but_a_browser_tab(surface):
    with pytest.raises(SystemExit, match="refused to record"):
        screencast.check_surface(surface)


def test_check_surface_accepts_a_browser_tab():
    screencast.check_surface("browser")


class _FakeKeyboard:
    def __init__(self) -> None:
        self.pressed: list[str] = []

    def press(self, key: str) -> None:
        self.pressed.append(key)


def test_the_tour_cannot_press_escape():
    """Esc stops Streamlit's recording; record() presses it after the tour."""
    keyboard = _FakeKeyboard()
    tour = screencast.Tour(cast(Any, SimpleNamespace(keyboard=keyboard)))
    tour.press("Tab")
    with pytest.raises(ValueError, match="stops the recording"):
        tour.press("Escape")
    assert keyboard.pressed == ["Tab"]


def test_find_ffmpeg_prefers_imageio_ffmpeg(monkeypatch):
    fake = SimpleNamespace(get_ffmpeg_exe=lambda: "C:/imageio/ffmpeg.exe")
    monkeypatch.setattr(screencast.importlib, "import_module", lambda name: fake)
    monkeypatch.setattr(screencast.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert screencast.find_ffmpeg() == "C:/imageio/ffmpeg.exe"


def _no_module(name: str) -> Any:
    raise ModuleNotFoundError(name)


def test_find_ffmpeg_falls_back_to_the_path(monkeypatch):
    monkeypatch.setattr(screencast.importlib, "import_module", _no_module)
    monkeypatch.setattr(screencast.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert screencast.find_ffmpeg() == "/usr/bin/ffmpeg"


def test_find_ffmpeg_names_the_fix_when_none_is_found(monkeypatch):
    monkeypatch.setattr(screencast.importlib, "import_module", _no_module)
    monkeypatch.setattr(screencast.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="--with imageio-ffmpeg"):
        screencast.find_ffmpeg()


def test_options_default_to_a_960_px_gif_in_assets():
    args = screencast.parse_args([])
    assert args.out == ROOT / "assets" / "listview-tour.gif"
    assert (args.width, args.fps, args.port) == (960, 10, 0)


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--out", "tour.webp"], "must end in .gif"),
        (["--width", "0"], "--width must be 1 to 1280"),
        (["--width", "1281"], "--width must be 1 to 1280"),
        (["--fps", "0"], "--fps must be 1 to 30"),
        (["--fps", "31"], "--fps must be 1 to 30"),
    ],
)
def test_options_refuse_values_outside_their_range(argv, message, capsys):
    with pytest.raises(SystemExit):
        screencast.parse_args(argv)
    assert message in capsys.readouterr().err


def test_video_to_gif_scales_drops_still_frames_and_keeps_the_timing(
    monkeypatch, tmp_path
):
    calls: list[list[str]] = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(screencast.subprocess, "run", run)
    out = tmp_path / "assets" / "tour.gif"
    assert screencast.video_to_gif("ffmpeg", tmp_path / "t.webm", out, 960, 10) == out
    [cmd] = calls
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-i") + 1] == str(tmp_path / "t.webm")
    assert cmd[-1] == str(out)
    assert out.parent.is_dir()
    vf = cmd[cmd.index("-vf") + 1]
    assert vf.startswith("fps=10,scale=960:-1:")
    assert "mpdecimate" in vf
    assert "palettegen" in vf and "paletteuse" in vf
    # A dropped frame lengthens the one before it instead of shortening the GIF.
    assert cmd[cmd.index("-fps_mode") + 1] == "vfr"


def test_video_to_gif_reports_what_ffmpeg_said(monkeypatch, tmp_path):
    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "line\nInvalid data found")

    monkeypatch.setattr(screencast.subprocess, "run", run)
    with pytest.raises(SystemExit, match="Invalid data found"):
        screencast.video_to_gif(
            "ffmpeg", tmp_path / "t.webm", tmp_path / "t.gif", 960, 10
        )


def test_main_looks_for_ffmpeg_before_it_records(monkeypatch):
    """A missing ffmpeg stops the run before the minute-long recording."""

    def no_ffmpeg() -> str:
        raise SystemExit("no ffmpeg")

    def must_not_run(*args, **kwargs):
        raise AssertionError("recorded without ffmpeg")

    monkeypatch.setattr(screencast, "find_ffmpeg", no_ffmpeg)
    monkeypatch.setattr(screencast, "_serve", must_not_run)
    monkeypatch.setattr(screencast, "record", must_not_run)
    with pytest.raises(SystemExit, match="no ffmpeg"):
        screencast.main([])
