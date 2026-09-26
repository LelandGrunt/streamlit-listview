"""Assemble captured frames into a looping GIF.

Importable: ``build_gif(frames_dir, out, scale=0.5, colors=256)`` -> output Path.
CLI: ``python make_gif.py <frames_dir> <out.gif> [scale] [colors]``

Builds a global palette from all frames (so selection/filter states keep their
colors), no dithering (flat UI), infinite loop, per-frame durations.
"""

import json
import sys
from pathlib import Path

from PIL import Image


def validate_gif_params(out, scale, colors) -> None:
    """Raise ValueError for an invalid output path / scale / palette size.

    The one spelling of the CLI-visible rules: build_gif enforces them here, and
    generate.py pre-checks its arguments through the same call.
    """
    out = Path(out)
    if out.suffix.lower() != ".gif":
        raise ValueError(f"output path must end in .gif, got {out.name!r}")
    if scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale!r}")
    if not (2 <= colors <= 256):
        raise ValueError(f"colors must be between 2 and 256, got {colors!r}")


def build_gif(frames_dir, out, scale: float = 0.5, colors: int = 256) -> Path:
    """Assemble ``frames_dir`` (frame_NNN.png + frames.json) into a looping GIF."""
    frames_dir = Path(frames_dir)
    out = Path(out)
    validate_gif_params(out, scale, colors)
    manifest = json.loads((frames_dir / "frames.json").read_text())
    if not manifest:
        raise ValueError(
            f"no frames to assemble: {frames_dir / 'frames.json'} is empty"
        )

    imgs: list[Image.Image] = []
    durations: list[int] = []
    target = None
    for name, dur in manifest:
        im = Image.open(frames_dir / name).convert("RGB")
        if target is None:
            w, h = im.size
            target = (round(w * scale), round(h * scale))
        imgs.append(im.resize(target, Image.LANCZOS))
        durations.append(int(dur))

    # Global palette from a montage of every frame, so colors that appear only in
    # later states (selection tint, filtered view) are represented.
    w, h = target
    montage = Image.new("RGB", (w, h * len(imgs)))
    for i, im in enumerate(imgs):
        montage.paste(im, (0, i * h))
    pal = montage.quantize(colors=colors, method=Image.MEDIANCUT)
    del montage  # free the tall palette image before quantizing every frame

    try:
        no_dither = Image.Dither.NONE
    except AttributeError:  # older Pillow
        no_dither = Image.NONE

    frames_p = [im.quantize(palette=pal, dither=no_dither) for im in imgs]

    out.parent.mkdir(parents=True, exist_ok=True)
    frames_p[0].save(
        out,
        save_all=True,
        append_images=frames_p[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    return out


if __name__ == "__main__":
    out_path = build_gif(
        sys.argv[1],
        sys.argv[2],
        float(sys.argv[3]) if len(sys.argv) > 3 else 0.5,
        int(sys.argv[4]) if len(sys.argv) > 4 else 256,
    )
    kb = out_path.stat().st_size // 1024
    print(f"wrote {out_path} | {kb} KB")
