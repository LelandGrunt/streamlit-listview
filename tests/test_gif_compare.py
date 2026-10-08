"""compare.py: pairing, pixel counts, the report and the exit codes."""

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "gif"))

import compare

WHITE = (255, 255, 255)


def _image(pixels=(), size=(8, 6)):
    """A white image with the given ((x, y), rgb) pixels set."""
    image = Image.new("RGB", size, WHITE)
    for xy, rgb in pixels:
        image.putpixel(xy, rgb)
    return image


def _record(root, scenarios, chromium="140.0", platform_name="test-os"):
    """Write a recording; ``scenarios`` maps a name to [(take, step, image), ...]."""
    root.mkdir(parents=True)
    for name, frames in scenarios.items():
        folder = root / name
        folder.mkdir()
        manifest = []
        for index, (take, step, image) in enumerate(frames):
            file = f"frame_{index:03d}.png"
            image.save(folder / file)
            manifest.append({"file": file, "ms": 100, "take": take, "step": step})
        (folder / "frames.json").write_text(json.dumps(manifest), encoding="utf-8")
    meta = {
        "scenarios": list(scenarios),
        "chromium": chromium,
        "platform": platform_name,
        "git": "abc1234",
        "bundle": "index-abc.js",
    }
    (root / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return root


def _diffs(a, b, threshold=0):
    return compare.compare(
        compare.load_recording(a), compare.load_recording(b), threshold
    )


def test_identical_recordings_are_the_same(tmp_path):
    frames = {"hero": [("main", "idle", _image()), ("main", "select", _image())]}
    a = _record(tmp_path / "a", frames)
    b = _record(tmp_path / "b", frames)
    assert compare.main([str(a), str(b)]) == 0
    assert (b / "report.html").is_file()


def test_one_changed_pixel_is_counted_and_boxed(tmp_path, capsys):
    a = _record(tmp_path / "a", {"hero": [("main", "idle", _image())]})
    b = _record(
        tmp_path / "b", {"hero": [("main", "idle", _image([((3, 2), (0, 0, 0))]))]}
    )
    [diff] = _diffs(a, b)
    assert diff.status == compare.CHANGED
    assert diff.pixels == 1
    assert diff.box == (3, 2, 4, 3)
    assert compare.main([str(a), str(b)]) == 1
    out = capsys.readouterr().out
    assert "changed  1 px in 1x1 at 3,2" in out
    assert "0 same, 1 changed, 0 added, 0 removed" in out


@pytest.mark.parametrize(
    ("delta", "threshold", "status"),
    [(4, 4, compare.SAME), (5, 4, compare.CHANGED), (1, 0, compare.CHANGED)],
)
def test_threshold_ignores_small_channel_differences(
    tmp_path, delta, threshold, status
):
    a = _record(tmp_path / "a", {"s": [("main", "idle", _image())]})
    changed = _image([((0, 0), (255 - delta, 255, 255))])
    b = _record(tmp_path / "b", {"s": [("main", "idle", changed)]})
    [diff] = _diffs(a, b, threshold)
    assert diff.status == status


def test_a_frame_of_another_size_is_changed(tmp_path):
    a = _record(tmp_path / "a", {"s": [("main", "idle", _image())]})
    b = _record(tmp_path / "b", {"s": [("main", "idle", _image(size=(8, 7)))]})
    [diff] = _diffs(a, b)
    assert diff.status == compare.CHANGED
    assert diff.note == "size 8x6 -> 8x7"


def test_an_inserted_step_is_added_and_the_rest_still_pair(tmp_path):
    a = _record(
        tmp_path / "a", {"s": [("main", "one", _image()), ("main", "two", _image())]}
    )
    b = _record(
        tmp_path / "b",
        {
            "s": [
                ("main", "one", _image()),
                ("main", "new", _image()),
                ("main", "two", _image()),
            ]
        },
    )
    assert [(d.key, d.status) for d in _diffs(a, b)] == [
        (("s", "main", "one"), compare.SAME),
        (("s", "main", "two"), compare.SAME),
        (("s", "main", "new"), compare.ADDED),
    ]


def test_a_scenario_on_one_side_is_removed_or_added(tmp_path):
    a = _record(
        tmp_path / "a",
        {"old": [("main", "idle", _image())], "both": [("main", "idle", _image())]},
    )
    b = _record(
        tmp_path / "b",
        {"both": [("main", "idle", _image())], "new": [("main", "idle", _image())]},
    )
    assert [(d.key, d.status) for d in _diffs(a, b)] == [
        (("old", "main", "idle"), compare.REMOVED),
        (("both", "main", "idle"), compare.SAME),
        (("new", "main", "idle"), compare.ADDED),
    ]


@pytest.mark.parametrize(
    ("damage", "named"),
    [
        ("no-meta", "meta.json"),
        ("no-manifest", "frames.json"),
        ("no-frame", "frame_000.png"),
        ("old-manifest", "frames.json"),
        ("bad-json", "meta.json"),
        ("bad-png", "frame_000.png"),
        ("number-step", "frames.json"),
    ],
)
def test_a_damaged_recording_exits_with_2(tmp_path, capsys, damage, named):
    good = _record(tmp_path / "a", {"s": [("main", "idle", _image())]})
    bad = _record(tmp_path / "b", {"s": [("main", "idle", _image())]})
    if damage == "no-meta":
        (bad / "meta.json").unlink()
    elif damage == "no-manifest":
        (bad / "s" / "frames.json").unlink()
    elif damage == "no-frame":
        (bad / "s" / "frame_000.png").unlink()
    elif damage == "old-manifest":
        old = json.dumps([["frame_000.png", 100]])
        (bad / "s" / "frames.json").write_text(old, encoding="utf-8")
    elif damage == "bad-json":
        (bad / "meta.json").write_text("{not json", encoding="utf-8")
    elif damage == "bad-png":
        (bad / "s" / "frame_000.png").write_bytes(b"not a png")
    else:
        entry = {"file": "frame_000.png", "ms": 100, "take": "main", "step": 7}
        (bad / "s" / "frames.json").write_text(json.dumps([entry]), encoding="utf-8")
    assert compare.main([str(good), str(bad)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert named in err
    assert "Traceback" not in err


def test_a_missing_directory_exits_with_2(tmp_path):
    good = _record(tmp_path / "a", {"s": [("main", "idle", _image())]})
    assert compare.main([str(good), str(tmp_path / "nowhere")]) == 2


def test_the_report_embeds_images_only_for_differences(tmp_path):
    a = _record(
        tmp_path / "a",
        {
            "s": [
                ("main", "same", _image()),
                ("main", "changed", _image()),
                ("main", "removed", _image()),
            ]
        },
    )
    b = _record(
        tmp_path / "b",
        {
            "s": [
                ("main", "same", _image()),
                ("main", "changed", _image([((1, 1), (0, 0, 0))])),
                ("main", "added", _image()),
            ]
        },
    )
    report = tmp_path / "out" / "deeper" / "report.html"
    assert compare.main([str(a), str(b), "--report", str(report)]) == 1
    page = report.read_text(encoding="utf-8")
    # Before, after and the diff view for the changed frame; one image each for
    # the removed and the added frame; none for the frame that stayed the same.
    assert page.count("data:image/png;base64,") == 5


def test_different_machines_warn(tmp_path, capsys):
    a = _record(tmp_path / "a", {"s": [("main", "idle", _image())]}, chromium="140.0")
    b = _record(tmp_path / "b", {"s": [("main", "idle", _image())]}, chromium="141.0")
    assert compare.main([str(a), str(b)]) == 0
    assert "WARNING" in capsys.readouterr().out
    assert "chromium" in (b / "report.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("threshold", ["-1", "256"])
def test_threshold_outside_0_to_255_is_a_usage_error(tmp_path, threshold):
    a = _record(tmp_path / "a", {"s": [("main", "idle", _image())]})
    with pytest.raises(SystemExit) as excinfo:
        compare.main([str(a), str(a), "--threshold", threshold])
    assert excinfo.value.code == 2


def test_a_report_path_that_is_a_folder_exits_with_2(tmp_path, capsys):
    a = _record(tmp_path / "a", {"s": [("main", "idle", _image())]})
    folder = tmp_path / "existing-folder"
    folder.mkdir()
    assert compare.main([str(a), str(a), "--report", str(folder)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "existing-folder" in err


def test_a_folder_without_meta_is_not_a_complete_recording(tmp_path, capsys):
    """A frames folder or the parent of all recordings has no meta.json either;
    calling it "aborted" would send the reader looking for a failed run."""
    good = _record(tmp_path / "a", {"s": [("main", "idle", _image())]})
    assert compare.main([str(good), str(tmp_path)]) == 2
    assert "is not a complete recording" in capsys.readouterr().err
