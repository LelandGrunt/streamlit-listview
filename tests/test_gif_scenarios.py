"""The GIF scenarios (scripts/gif/): clip geometry, catalogue, GIF assembly, options."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "gif"))

import generate
from capture import CaptureResult
from make_gif import build_gif
from scenarios import SCENARIOS
from stage import Scenario, Stage, Take, clip_for

# The catalogue in README order; each scenario task adds its name.
GALLERY = [
    "hero",
    "keyboard",
    "add-options",
    "markdown",
    "layout",
    "themes",
    "large-list",
    "jump-to-default",
]
TEST_ONLY: list[str] = ["dark", "sidebar", "limits"]
SCENARIO_DIR = ROOT / "scripts" / "gif" / "scenarios"

BOX = {"x": 80.0, "y": 300.0, "width": 560.0, "height": 680.0}


def test_clip_pads_the_box_on_every_side():
    assert clip_for(BOX) == {"x": 68.0, "y": 288.0, "width": 584.0, "height": 704.0}


def test_clip_top_adds_room_above_the_box():
    assert clip_for(BOX, top=160) == {
        "x": 68.0,
        "y": 128.0,
        "width": 584.0,
        "height": 864.0,
    }


def test_clip_never_starts_outside_the_page():
    clip = clip_for({**BOX, "x": 5.0, "y": 5.0})
    assert (clip["x"], clip["y"]) == (0, 0)
    assert (clip["width"], clip["height"]) == (584.0, 704.0)


def test_clip_size_keeps_a_later_take_at_the_first_takes_size():
    """A smaller widget (a theme with a smaller base font) keeps the first take's
    frame, anchored at its own corner, so every GIF frame has one size."""
    first = clip_for(BOX)
    smaller = {**BOX, "x": 90.0, "y": 310.0, "height": 660.0}
    clip = clip_for(smaller, size=(first["width"], first["height"]))
    assert clip == {"x": 78.0, "y": 298.0, "width": 584.0, "height": 704.0}


def test_clip_size_refuses_a_larger_widget():
    """A frame of the first take's size would cut a larger widget off."""
    larger = {**BOX, "height": 700.0}
    with pytest.raises(ValueError, match="584x724 CSS px"):
        clip_for(larger, size=(584.0, 704.0))


def _page(take: str) -> None:
    """A page that renders nothing."""


def _play(stage) -> None:
    """Steps that take no frame."""


def test_gif_file_defaults_to_the_scenario_name():
    scenario = Scenario(
        name="add-options", title="Add", gallery=True, page=_page, play=_play
    )
    assert scenario.gif_file == "listview-add-options.gif"
    assert scenario.takes == (Take(),)
    assert scenario.takes[0].name == "main"


def test_gif_name_overrides_the_default():
    scenario = Scenario(
        name="hero",
        title="Hero",
        gallery=True,
        page=_page,
        play=_play,
        gif_name="listview-demo.gif",
    )
    assert scenario.gif_file == "listview-demo.gif"


def test_catalogue_lists_gallery_scenarios_first():
    assert list(SCENARIOS) == GALLERY + TEST_ONLY
    assert [name for name, s in SCENARIOS.items() if s.gallery] == GALLERY


def test_every_scenario_module_is_in_the_catalogue():
    modules = {
        path.stem.replace("_", "-")
        for path in SCENARIO_DIR.glob("*.py")
        if not path.stem.startswith("_")
    }
    assert modules == set(SCENARIOS)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_scenario_is_complete(name):
    scenario = SCENARIOS[name]
    assert scenario.name == name
    assert scenario.title.strip()
    assert callable(scenario.page)
    assert callable(scenario.play)
    takes = [take.name for take in scenario.takes]
    assert takes
    assert len(takes) == len(set(takes))


def test_gallery_gif_files_are_unique():
    files = [s.gif_file for s in SCENARIOS.values() if s.gallery]
    assert len(files) == len(set(files))
    assert SCENARIOS["hero"].gif_file == "listview-demo.gif"


def _write_frames(frames_dir, sizes):
    frames_dir.mkdir()
    manifest = []
    for index, size in enumerate(sizes):
        name = f"frame_{index:03d}.png"
        colour = (200, 30, 30) if index % 2 else (30, 30, 200)
        Image.new("RGB", size, colour).save(frames_dir / name)
        manifest.append(
            {"file": name, "ms": 100 + 10 * index, "take": "main", "step": f"s{index}"}
        )
    (frames_dir / "frames.json").write_text(json.dumps(manifest), encoding="utf-8")
    return frames_dir


def test_build_gif_reads_the_manifest(tmp_path):
    frames = _write_frames(tmp_path / "frames", [(40, 20), (40, 20)])
    out = build_gif(frames, tmp_path / "out.gif", scale=0.5)
    with Image.open(out) as gif:
        assert gif.size == (20, 10)
        durations = [frame.info["duration"] for frame in ImageSequence.Iterator(gif)]
    assert durations == [100, 110]


def test_build_gif_refuses_frames_of_two_sizes(tmp_path):
    frames = _write_frames(tmp_path / "frames", [(40, 20), (40, 22)])
    with pytest.raises(ValueError, match="frame_001.png is 40x22 px"):
        build_gif(frames, tmp_path / "out.gif")


def test_generate_defaults_to_the_hero():
    assert [s.name for s in generate.parse_args([]).scenarios] == ["hero"]


def test_generate_gallery_chooses_every_gallery_scenario():
    assert [s.name for s in generate.parse_args(["--gallery"]).scenarios] == GALLERY


def test_generate_names_the_scenarios_on_a_typo(capsys):
    with pytest.raises(SystemExit) as excinfo:
        generate.parse_args(["--scenario", "nope"])
    assert excinfo.value.code == 2
    assert "hero" in capsys.readouterr().err


def test_generate_out_needs_a_single_scenario():
    with pytest.raises(SystemExit):
        generate.parse_args(["--gallery", "--out", "x.gif"])
    assert generate.parse_args(["--scenario", "hero", "--out", "x.gif"]).out == "x.gif"


def test_generate_rejects_a_bad_scale():
    with pytest.raises(SystemExit):
        generate.parse_args(["--scale", "0"])


def test_generate_imports_outside_a_streamlit_server():
    """generate.py imports the catalogue in a plain process, where declaring the
    component fails, so no scenario may import streamlit_listview at import time.
    conftest.py patches the declaration for this process, hence the subprocess."""
    code = "import sys; sys.path.insert(0, sys.argv[1]); import generate"
    result = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "scripts" / "gif")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_generate_all_needs_record(capsys):
    with pytest.raises(SystemExit):
        generate.parse_args(["--all"])
    assert "--all needs --record DIR" in capsys.readouterr().err


def test_generate_all_records_every_scenario(tmp_path):
    args = generate.parse_args(["--all", "--record", str(tmp_path / "rec")])
    assert [s.name for s in args.scenarios] == list(SCENARIOS)


def test_generate_refuses_to_replace_a_recording(tmp_path):
    (tmp_path / "meta.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        generate.parse_args(["--all", "--record", str(tmp_path)])
    assert generate.parse_args(
        ["--all", "--record", str(tmp_path), "--overwrite"]
    ).overwrite


def test_generate_record_builds_no_gif(tmp_path, capsys):
    with pytest.raises(SystemExit):
        generate.parse_args(
            ["--scenario", "hero", "--record", str(tmp_path), "--out", "x.gif"]
        )
    assert "--record builds no GIF, so it takes no --out" in capsys.readouterr().err


def test_write_meta_marks_a_complete_recording(tmp_path):
    generate.write_meta(tmp_path, ["hero"], chromium="140.0.7339.16")
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["scenarios"] == ["hero"]
    assert meta["chromium"] == "140.0.7339.16"
    assert {
        "git",
        "bundle",
        "playwright",
        "streamlit",
        "python",
        "platform",
        "recorded_at",
    } <= set(meta)


def test_an_aborted_recording_has_no_meta(tmp_path, monkeypatch):
    recording = tmp_path / "rec"
    recording.mkdir()
    (recording / "meta.json").write_text("{}", encoding="utf-8")

    def fail(scenario, frames_dir, port, **kwargs):
        raise SystemExit("a step failed")

    monkeypatch.setattr(generate, "run_scenario", fail)
    with pytest.raises(SystemExit):
        generate.main(["--all", "--record", str(recording), "--overwrite"])
    assert not (recording / "meta.json").exists()


def test_generate_test_scenarios_need_record(capsys):
    with pytest.raises(SystemExit):
        generate.parse_args(["--scenario", "dark"])
    assert "record them with --record DIR: dark" in capsys.readouterr().err


def test_generate_records_a_test_scenario(tmp_path):
    args = generate.parse_args(["--scenario", "dark", "--record", str(tmp_path)])
    assert [s.name for s in args.scenarios] == ["dark"]


class _FakeRunner:
    """Stands in for a StreamlitRunner: no server, a canned server report."""

    server_url = "http://localhost:0"

    def __init__(self, output=""):
        self.output = output

    def stop(self):
        pass

    def _read_output(self):
        return self.output


def test_a_recording_lets_takes_differ_in_size(tmp_path, monkeypatch):
    """compare.py reports a frame of another size, so only a GIF demands that
    every take of a scenario has the first take's frame size."""
    sizes = []

    def fake_capture(url, frames_dir, scenario, take, frames, clip_size=None):
        sizes.append(clip_size)
        return CaptureResult((584.0, 700.0), "140.0")

    monkeypatch.setattr(generate, "_serve", lambda *args, **kwargs: _FakeRunner())
    monkeypatch.setattr(generate, "capture", fake_capture)
    generate.main(["--scenario", "themes", "--record", str(tmp_path / "rec")])
    assert sizes == [None] * len(SCENARIOS["themes"].takes)


def test_a_failed_take_names_the_scenario_and_shows_the_server_output(
    tmp_path, monkeypatch
):
    """An exception in page() reaches the browser only as a timeout; the cause is
    in the server's report, so the error must carry it."""
    report = "Uncaught app execution\nNameError: name 'x' is not defined"

    def fail(*args, **kwargs):
        raise TimeoutError("Timeout 90000ms exceeded")

    monkeypatch.setattr(generate, "_serve", lambda *args, **kwargs: _FakeRunner(report))
    monkeypatch.setattr(generate, "capture", fail)
    with pytest.raises(SystemExit) as excinfo:
        generate.run_scenario(SCENARIOS["hero"], tmp_path / "frames", 0)
    message = str(excinfo.value.code)
    assert "scenario 'hero', take 'main'" in message
    assert "Timeout 90000ms exceeded" in message
    assert "NameError: name 'x' is not defined" in message


def test_large_list_builds_its_options_on_first_render(monkeypatch):
    """Importing the catalogue (generate.py, pytest, every take's server) must not
    build the 100,000-row list; the scenario's page builds it once, when used."""
    from scenarios import large_list

    assert not any(
        isinstance(value, list) and len(value) == 100_000
        for value in vars(large_list).values()
    )
    calls = []

    def fake_dataset(n):
        calls.append(n)
        return []

    monkeypatch.setattr(large_list, "make_large_dataset", fake_dataset)
    large_list.options.cache_clear()
    large_list.options()
    large_list.options()
    large_list.options.cache_clear()
    assert calls == [100_000]


@pytest.mark.parametrize(
    "gif_option",
    [
        ["--scale", "0.4"],
        ["--colors", "128"],
        ["--keep-frames"],
        # 0 is falsy, so a truthiness check would let these through.
        ["--scale", "0"],
        ["--colors", "0"],
    ],
)
def test_generate_record_refuses_gif_options(tmp_path, capsys, gif_option):
    with pytest.raises(SystemExit):
        generate.parse_args(["--all", "--record", str(tmp_path), *gif_option])
    assert (
        f"--record builds no GIF, so it takes no {gif_option[0]}"
        in capsys.readouterr().err
    )


def test_generate_overwrite_needs_record(capsys):
    with pytest.raises(SystemExit):
        generate.parse_args(["--overwrite"])
    assert "--overwrite needs --record" in capsys.readouterr().err


class _FakePage:
    """Answers the two calls Stage.snap makes, without a browser."""

    def evaluate(self, *args):
        return None

    def screenshot(self, **kwargs):
        return None


def test_snap_refuses_a_repeated_step(tmp_path):
    """compare.py pairs frames by step name, so a repeated name in one take would
    let a later frame overwrite an earlier one without notice."""
    clip = {"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}
    stage = Stage(cast(Any, _FakePage()), Take(), tmp_path, [], cast(Any, clip))
    stage.snap("idle", 100)
    with pytest.raises(ValueError, match="step 'idle' appears twice in take 'main'"):
        stage.snap("idle", 100)


def _flag_pairs(args):
    return dict(zip(args[::2], args[1::2]))


def test_themes_takes_use_the_demo_brand_themes():
    """The themes GIF shows light, dark and two theme files the demo ships, with
    every option of each file passed to the take's server."""
    takes = {take.name: take for take in SCENARIOS["themes"].takes}
    assert list(takes) == ["light", "dark", "databricks-brand", "snowflake-brand"]
    databricks = _flag_pairs(takes["databricks-brand"].server_args)
    assert databricks["--theme.light.primaryColor"] == "#BD2B26"
    assert databricks["--theme.showWidgetBorder"] == "true"
    assert databricks["--theme.baseFontSize"] == "14"
    snowflake = _flag_pairs(takes["snowflake-brand"].server_args)
    assert snowflake["--theme.light.primaryColor"] == "#11567F"
    assert snowflake["--theme.buttonRadius"] == "full"
