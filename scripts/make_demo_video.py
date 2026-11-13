"""Encode the simulator recording of the demo episode as videos/demo.mp4.

Input is the output directory of scripts/render_episode.py (run in WSL with the
VirtualHome player): frames recorded by the simulator for each executed action,
and stills from the same camera taken between actions. Every frame in the video
comes from the simulator; nothing is drawn onto it. Where the agent waited in the
trial (the failed grab, the rejected recoveries and the re-plan), the video holds
the simulator's still for that moment. Step captions go in videos/demo.vtt.

Usage: uv run --with imageio --with imageio-ffmpeg --with numpy --with pillow \
           python scripts/make_demo_video.py <render output>/frames
"""
import json
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "frames")
SITE = Path(__file__).resolve().parent.parent
replay = json.loads((SRC / "replay.json").read_text())
fps = replay["fps"]


def frames(step):
    return [SRC / f for f in replay["steps"][step]["frames"]]


def load(path):
    return np.asarray(Image.open(path).convert("RGB"))


# (frames, caption). Held stills are repeated for the given number of seconds.
segments = [
    (frames(0), "policy(): find(toaster). The agent walks to the toaster."),
    ([SRC / "after_find_toaster.png"] * int(3.5 * fps),
     "grab(bread) fails: the agent is not close to the bread."),
    ([SRC / "after_find_toaster.png"] * int(3.5 * fps),
     "Two local recoveries are written; both are rejected by the code checks."),
    ([SRC / "after_find_bread.png"] * int(3.5 * fps),
     "The model re-plans from the current state. New policy: find(bread)."),
    (frames(2), "grab(bread)"),
    (frames(3), "putback(bread, toaster)"),
    (frames(4) + [frames(4)[-1]] * int(2.5 * fps), "switchon(toaster). Task complete: 8 model calls."),
]

out = SITE / "videos" / "demo.mp4"
writer = imageio.get_writer(out, fps=fps, codec="libx264", pixelformat="yuv420p", quality=8,
                            macro_block_size=16, ffmpeg_params=["-movflags", "+faststart"])
cues, t = [], 0.0
for paths, caption in segments:
    for p in paths:
        writer.append_data(load(p))
    start, t = t, t + len(paths) / fps
    cues.append((start, t, caption))
writer.close()


def stamp(seconds):
    m, s = divmod(seconds, 60)
    return f"00:{int(m):02d}:{s:06.3f}"


vtt = "WEBVTT\n\n" + "\n".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n" for i, (a, b, text) in enumerate(cues, 1))
(SITE / "videos" / "demo.vtt").write_text(vtt, encoding="utf-8")
Image.open(frames(3)[len(frames(3)) // 2]).convert("RGB").save(SITE / "videos" / "demo-poster.jpg", quality=88)
print(f"{out}: {t:.1f} s, {sum(len(p) for p, _ in segments)} frames at {fps} fps")
