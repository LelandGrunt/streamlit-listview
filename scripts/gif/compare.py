"""Compare two recordings of the GIF scenarios frame by frame.

A recording is the directory ``generate.py --record DIR`` writes: meta.json plus
one folder per scenario with frame_NNN.png files and frames.json. Frames pair by
scenario, take and step name, so an inserted step reports as added instead of
shifting every later frame.

CLI: python compare.py <A> <B> [--threshold N] [--report PATH]
Exit codes: 0 every frame is the same, 1 a frame differs, 2 invalid input.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw

SAME = "same"
CHANGED = "changed"
ADDED = "added"
REMOVED = "removed"
STATUSES = (SAME, CHANGED, ADDED, REMOVED)

WHITE = (255, 255, 255)
RED = (220, 0, 0)

# (scenario, take, step)
Key = tuple[str, str, str]


class RecordingError(Exception):
    """A recording is missing, incomplete or unreadable."""


@dataclass(frozen=True)
class Recording:
    root: Path
    meta: dict[str, Any]
    frames: dict[Key, Path]


@dataclass(frozen=True)
class FrameDiff:
    key: Key
    status: str
    pixels: int = 0
    box: tuple[int, int, int, int] | None = None
    note: str = ""


def load_recording(root: Path) -> Recording:
    """Read a recording's meta.json and every scenario's frames.json."""
    if not root.is_dir():
        raise RecordingError(f"{root} is not a directory")
    meta_path = root / "meta.json"
    if not meta_path.is_file():
        raise RecordingError(
            f"{root} is not a complete recording: {meta_path.name} is missing "
            "(generate.py writes it last, so an aborted run has none)"
        )
    # The file being read, so an error names it rather than the recording.
    reading = meta_path
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        frames: dict[Key, Path] = {}
        for scenario in meta["scenarios"]:
            reading = root / scenario / "frames.json"
            if not reading.is_file():
                raise RecordingError(f"{reading} is missing")
            for entry in json.loads(reading.read_text(encoding="utf-8")):
                key = (scenario, entry["take"], entry["step"])
                if not all(isinstance(part, str) for part in key):
                    raise TypeError(f"scenario, take and step must be text: {key!r}")
                path = root / scenario / entry["file"]
                if not path.is_file():
                    raise RecordingError(f"{path} is missing")
                frames[key] = path
    except (ValueError, KeyError, TypeError) as exc:
        raise RecordingError(f"{reading} is not readable: {exc!r}") from exc
    return Recording(root, meta, frames)


def read_frame(path: Path) -> Image.Image:
    """The frame at ``path`` in RGB; a RecordingError names a file Pillow cannot read."""
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except OSError as exc:
        raise RecordingError(f"{path} is not a readable image: {exc}") from exc


def changed_mask(
    before: Image.Image, after: Image.Image, threshold: int
) -> Image.Image:
    """An L-mode mask: 255 where a channel differs by more than ``threshold``."""
    delta = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
    red, green, blue = delta.split()
    peak = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return peak.point([255 if value > threshold else 0 for value in range(256)])


def compare(a: Recording, b: Recording, threshold: int = 0) -> list[FrameDiff]:
    """Pair the frames of two recordings and classify each pair."""
    diffs: list[FrameDiff] = []
    for key in _ordered_keys(a, b):
        before, after = a.frames.get(key), b.frames.get(key)
        if before is None:
            diffs.append(FrameDiff(key, ADDED))
            continue
        if after is None:
            diffs.append(FrameDiff(key, REMOVED))
            continue
        image_a, image_b = read_frame(before), read_frame(after)
        if image_a.size != image_b.size:
            (wa, ha), (wb, hb) = image_a.size, image_b.size
            note = f"size {wa}x{ha} -> {wb}x{hb}"
            diffs.append(FrameDiff(key, CHANGED, note=note))
            continue
        mask = changed_mask(image_a, image_b, threshold)
        box = mask.getbbox()
        if box is None:
            diffs.append(FrameDiff(key, SAME))
        else:
            pixels = mask.histogram()[255]
            diffs.append(FrameDiff(key, CHANGED, pixels=pixels, box=box))
    return diffs


def _ordered_keys(a: Recording, b: Recording) -> list[Key]:
    """Every key of both recordings: per scenario, A's steps, then B's new ones."""
    names = [key[0] for key in a.frames] + [key[0] for key in b.frames]
    keys: list[Key] = []
    for scenario in dict.fromkeys(names):
        keys += [key for key in a.frames if key[0] == scenario]
        keys += [key for key in b.frames if key[0] == scenario and key not in a.frames]
    return keys


def meta_warnings(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Differences between the two machines that change pixels on their own."""
    warnings = []
    for name in ("chromium", "platform"):
        if a.get(name) != b.get(name):
            warnings.append(
                f"the recordings differ in {name} ({a.get(name)!r} vs "
                f"{b.get(name)!r}); pixels may differ for that reason alone"
            )
    return warnings


def _detail(diff: FrameDiff) -> str:
    if diff.note:
        return diff.note
    if diff.box is None:
        return ""
    left, top, right, bottom = diff.box
    return f"{diff.pixels} px in {right - left}x{bottom - top} at {left},{top}"


def _summary(diffs: list[FrameDiff]) -> str:
    return ", ".join(f"{sum(d.status == s for d in diffs)} {s}" for s in STATUSES)


def format_table(diffs: list[FrameDiff]) -> str:
    """One line per frame that differs, then the count per status."""
    header = ("scenario", "take", "step", "status", "detail")
    rows = [header] + [
        (*d.key, d.status, _detail(d)) for d in diffs if d.status != SAME
    ]
    lines = []
    if len(rows) > 1:
        widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
        lines = [
            "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()
            for row in rows
        ]
    lines.append(_summary(diffs))
    return "\n".join(lines)


def diff_view(before: Image.Image, after: Image.Image, threshold: int) -> Image.Image:
    """``after`` dimmed, with the changed pixels in red and their box outlined."""
    mask = changed_mask(before, after, threshold)
    gray = after.convert("L").convert("RGB")
    dimmed = Image.blend(Image.new("RGB", gray.size, WHITE), gray, 0.35)
    view = Image.composite(Image.new("RGB", gray.size, RED), dimmed, mask)
    box = mask.getbbox()
    if box is not None:
        left, top, right, bottom = box
        ImageDraw.Draw(view).rectangle(
            (left - 3, top - 3, right + 2, bottom + 2), outline=RED, width=2
        )
    return view


_STYLE = """
body { margin: 24px; font: 14px/1.5 system-ui, sans-serif; color: #1f2328;
  background: #ffffff; }
h1 { font-size: 20px; }
h3 { font-size: 14px; margin: 24px 0 8px; }
table { border-collapse: collapse; }
th, td { padding: 2px 12px 2px 0; text-align: left; border-bottom: 1px solid #d8dee4; }
tr.same td { color: #6e7781; }
tr.changed td, tr.added td, tr.removed td { font-weight: 600; }
.warning { padding: 8px 12px; border: 1px solid #d4a72c; background: #fff8c5; }
figure { display: inline-block; width: 32%; margin: 0 1% 12px 0; vertical-align: top; }
figure img { width: 100%; border: 1px solid #d8dee4; }
"""


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _figure(caption: str, png: bytes) -> str:
    data = base64.b64encode(png).decode("ascii")
    return (
        f"<figure><figcaption>{_e(caption)}</figcaption>"
        f'<img alt="{_e(caption)}" src="data:image/png;base64,{data}"></figure>'
    )


def _describe(meta: dict[str, Any]) -> str:
    return (
        f"{meta.get('git', '?')}, {meta.get('bundle', '?')}, "
        f"Chromium {meta.get('chromium', '?')}"
    )


def write_report(
    path: Path,
    a: Recording,
    b: Recording,
    diffs: list[FrameDiff],
    warnings: list[str],
    threshold: int,
) -> None:
    """Write the self-contained HTML report: every frame, images for differences."""
    rows = []
    sections = []
    for diff in diffs:
        scenario, take, step = diff.key
        detail = _detail(diff)
        rows.append(
            f'<tr class="{diff.status}"><td>{_e(scenario)}</td><td>{_e(take)}</td>'
            f"<td>{_e(step)}</td><td>{diff.status}</td><td>{_e(detail)}</td></tr>"
        )
        if diff.status == SAME:
            continue
        figures = []
        if diff.status != ADDED:
            figures.append(_figure("before", a.frames[diff.key].read_bytes()))
        if diff.status != REMOVED:
            figures.append(_figure("after", b.frames[diff.key].read_bytes()))
        if diff.status == CHANGED and not diff.note:
            before = read_frame(a.frames[diff.key])
            after = read_frame(b.frames[diff.key])
            buffer = io.BytesIO()
            diff_view(before, after, threshold).save(buffer, format="PNG")
            figures.append(_figure("changed pixels", buffer.getvalue()))
        sections.append(
            f"<section><h3>{_e(scenario)} / {_e(take)} / {_e(step)}: "
            f"{diff.status} {_e(detail)}</h3>{''.join(figures)}</section>"
        )
    page = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en"><head><meta charset="utf-8">',
            "<title>GIF scenario comparison</title>",
            f"<style>{_STYLE}</style></head><body>",
            "<h1>GIF scenario comparison</h1>",
            (
                f"<p>Before: <code>{_e(str(a.root))}</code> ({_e(_describe(a.meta))})<br>"
                f"After: <code>{_e(str(b.root))}</code> ({_e(_describe(b.meta))})<br>"
                f"Threshold: {threshold}. {_summary(diffs)}.</p>"
            ),
            *(f'<p class="warning">WARNING: {_e(w)}</p>' for w in warnings),
            (
                "<table><tr><th>scenario</th><th>take</th><th>step</th>"
                "<th>status</th><th>detail</th></tr>"
            ),
            *rows,
            "</table>",
            *sections,
            "</body></html>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare two GIF scenario recordings.")
    ap.add_argument("before", type=Path, help="the earlier recording (A)")
    ap.add_argument("after", type=Path, help="the later recording (B)")
    ap.add_argument(
        "--threshold",
        type=int,
        default=0,
        help="ignore channel differences up to N (0-255, default 0)",
    )
    ap.add_argument(
        "--report", type=Path, help="the HTML report (default: <after>/report.html)"
    )
    args = ap.parse_args(argv)
    if not 0 <= args.threshold <= 255:
        ap.error(f"--threshold must be between 0 and 255, got {args.threshold}")
    # A Windows console may not encode what a path or a step name holds. Some
    # stdout replacements (pytest's capture) can reconfigure without being a
    # TextIOWrapper, so ask for the method, not the type.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
    try:
        a, b = load_recording(args.before), load_recording(args.after)
        diffs = compare(a, b, args.threshold)
    except RecordingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    warnings = meta_warnings(a.meta, b.meta)
    for warning in warnings:
        print(f"WARNING: {warning}")
    print(format_table(diffs))
    report = args.report or b.root / "report.html"
    try:
        write_report(report, a, b, diffs, warnings, args.threshold)
    except OSError as exc:
        # A folder or a path below a file: the table above still stands.
        print(f"error: cannot write the report to {report}: {exc}", file=sys.stderr)
        return 2
    print(f"report: {report}")
    return 0 if all(d.status == SAME for d in diffs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
