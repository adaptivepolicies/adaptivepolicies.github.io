"""Render the demo episode video (videos/demo.mp4 and videos/demo-poster.jpg).

The episode is a real evaluation trial: Gemma 4 12B, explicit checkpoints,
temperature 0, reasoning off, unseen task "put salmon in the fridge". Its run
directory on the cluster is
    outputs/experiments/cluster_ap_explicit_gemma4_12b_001/test_unseen/
    ap-explicit-gemma4-12b-t0-m8192-roff-test_unseen-r1
and the frames are task_images/put_salmon_in_the_fridge/step_*.png, one per
successful action. The policy and recovery code below are the model's output,
copied from tasks/put_salmon_in_the_fridge/execution.json.

Usage: uv run --with pillow --with imageio --with imageio-ffmpeg \
           python scripts/make_demo_video.py <frames dir>
"""
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FRAMES = Path(sys.argv[1] if len(sys.argv) > 1 else "frames")
SITE = Path(__file__).resolve().parent.parent
W, H, FPS = 1280, 720, 30
FONTS = Path("C:/Windows/Fonts")

POLICY = '''def policy():
    salmon = parse_objects("visible salmon")[0]
    acquire_object(salmon)
    checkpoint("holding the salmon", lambda: is_holding(salmon))
    find("fridge")
    checkpoint("a fridge is visible", lambda: any(obj.name == "fridge" for obj in get_visible_objects()))
    fridge = parse_objects("visible fridges")[0]
    putin(salmon, fridge)
    checkpoint("the salmon is inside the fridge", lambda: salmon in (get_objects_in(fridge) or []))
    close(fridge)
    checkpoint("the fridge is closed", lambda: "CLOSED" in (get_object_states(fridge) or ()))'''
# The model's recover(), without its explanatory comments.
RECOVER = '''def recover():
    if "OPEN" not in (get_object_states(fridge) or ()):
        open(fridge)
    putin(salmon, fridge)'''

BG, PANEL, BORDER = (23, 24, 26), (15, 16, 18), (51, 54, 59)
TEXT, MUTED = (232, 230, 227), (169, 173, 179)
BLUE, GREEN, ORANGE = (90, 155, 234), (76, 195, 138), (240, 132, 79)


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


SANS, SANS_B, MONO = font("segoeui.ttf", 22), font("segoeuib.ttf", 24), font("consola.ttf", 15)
SMALL = font("segoeui.ttf", 18)
MARK = font("seguisym.ttf", 18)

# Each beat: frame, highlighted policy line (1-based) and its colour, recovery
# line, events shown so far, caption, seconds.
OK, FAIL, CALL = "ok", "fail", "call"
BEATS = [
    dict(frame=None, line=None, caption="The model writes policy() once, with checkpoints on the states later steps rely on.",
         events=[(CALL, "model: policy()")], seconds=4.0),
    dict(frame=3, line=3, caption="acquire_object is not defined, so the model writes it on demand; it walks to the salmon.",
         events=[(CALL, "model: helper acquire_object"), (OK, "walk(salmon)")], seconds=3.5),
    dict(frame=4, line=4, caption="The salmon is grabbed and the checkpoint passes. A passing checkpoint needs no model call.",
         events=[(OK, "grab(salmon)"), (OK, "checkpoint: holding the salmon")], seconds=3.5),
    dict(frame=5, line=6, caption="The agent finds the fridge.",
         events=[(OK, 'find("fridge")'), (OK, "checkpoint: a fridge is visible")], seconds=3.0),
    dict(frame=5, line=8, colour=ORANGE, caption="The policy never opened the fridge, so putin fails.",
         events=[(FAIL, "putin(salmon, fridge): fridge is not open")], seconds=3.5),
    dict(frame=5, line=9, colour=ORANGE, recover=True,
         caption="The checkpoint fails. The model sees the code, the failure and the progress, and writes recover().",
         events=[(FAIL, "checkpoint: the salmon is inside the fridge"), (CALL, "model: recover()")], seconds=5.0),
    dict(frame=6, line=9, colour=ORANGE, recover=True, rline=3, caption="The recovery opens the fridge...",
         events=[(OK, "open(fridge)")], seconds=3.0),
    dict(frame=7, line=9, recover=True, rline=4,
         caption="...and puts the salmon in. The checkpoint is evaluated again and now passes.",
         events=[(OK, "putin(salmon, fridge)"), (OK, "checkpoint: the salmon is inside the fridge")], seconds=4.0),
    dict(frame=8, line=11, caption="The policy continues after the checkpoint and closes the fridge.",
         events=[(OK, "close(fridge)"), (OK, "checkpoint: the fridge is closed")], seconds=3.5),
    dict(frame=8, line=None, caption="Task complete. Five model calls: the policy, one helper, two object queries and one recovery.",
         events=[], seconds=4.5, done=True),
]


def wrap(line, width):
    """Soft-wrap a code line with a hanging indent."""
    if len(line) <= width:
        return [line]
    indent = len(line) - len(line.lstrip()) + 8
    cut = line.rfind(" ", 0, width)
    cut = cut if cut > indent else width
    rest = " " * indent + line[cut:].lstrip()
    return [line[:cut]] + wrap(rest, width)


def draw_code(d, x, y, w, source, title, active=None, colour=BLUE):
    rows = []
    for number, line in enumerate(source.splitlines(), start=1):
        rows += [(number, part) for part in wrap(line, 80)]
    lh = 21
    h = 40 + lh * len(rows) + 12
    d.rounded_rectangle((x, y, x + w, y + h), 8, fill=PANEL, outline=BORDER)
    d.text((x + 14, y + 10), title, font=SMALL, fill=MUTED)
    for i, (number, part) in enumerate(rows):
        ty = y + 40 + i * lh
        if number == active:
            d.rectangle((x + 1, ty - 2, x + w - 1, ty + lh - 3), fill=tuple(int(c * 0.28) for c in colour))
            d.rectangle((x + 1, ty - 2, x + 4, ty + lh - 3), fill=colour)
        d.text((x + 16, ty), part, font=MONO, fill=TEXT)
    return y + h


def sim_frame(index, dim=False):
    size = 460
    if index is None:
        img = Image.new("RGB", (size, size), PANEL)
    else:
        img = Image.open(FRAMES / f"step_{index}.png").convert("RGB").resize((size, size), Image.LANCZOS)
    if dim:
        img = Image.blend(img, Image.new("RGB", img.size, BG), 0.35)
    return img


def render(beat, history):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 22), "Adaptive Policies", font=SANS_B, fill=TEXT)
    d.text((262, 24), "put salmon in the fridge  ·  unseen task, Gemma 4 12B", font=SANS, fill=MUTED)
    frame = sim_frame(beat["frame"], dim=beat.get("done", False))
    img.paste(frame, (40, 70))
    d.rectangle((40, 70, 40 + 460, 70 + 460), outline=BORDER)
    if beat["frame"] is None:
        d.text((270, 300), "VirtualHome", font=SANS_B, fill=MUTED, anchor="mm")
    if beat.get("done"):
        d.rounded_rectangle((130, 260, 410, 340), 10, fill=(20, 60, 40), outline=GREEN, width=2)
        d.text((270, 300), "Goal reached", font=font("segoeuib.ttf", 30), fill=GREEN, anchor="mm")
    # Event log under the frame: the latest events, newest last.
    ly = 546
    for kind, text in history[-3:]:
        mark, col = {OK: ("✓", GREEN), FAIL: ("✗", ORANGE), CALL: ("●", BLUE)}[kind]
        d.text((44, ly), mark, font=MARK, fill=col)
        d.text((68, ly), text, font=SMALL, fill=TEXT if kind != FAIL else ORANGE)
        ly += 26
    # Code: the policy, and the recovery while it runs.
    x, w = 530, 710
    bottom = draw_code(d, x, 70, w, POLICY, "policy()  written once", beat.get("line"), beat.get("colour", BLUE))
    if beat.get("recover"):
        draw_code(d, x, bottom + 12, w, RECOVER, "recover()  written at the failed checkpoint",
                  beat.get("rline"), BLUE)
    # Caption.
    d.text((W // 2, 660), beat["caption"], font=SANS, fill=TEXT, anchor="mm")
    return img


def main():
    history, stills = [], []
    for beat in BEATS:
        history += beat["events"]
        stills.append((render(beat, history), beat["seconds"]))
    out = SITE / "videos" / "demo.mp4"
    writer = imageio.get_writer(out, fps=FPS, codec="libx264", pixelformat="yuv420p", quality=8,
                                macro_block_size=16, ffmpeg_params=["-movflags", "+faststart"])
    fade = int(0.3 * FPS)
    for i, (still, seconds) in enumerate(stills):
        a = np.asarray(still, dtype=np.float32)
        if i:
            prev = np.asarray(stills[i - 1][0], dtype=np.float32)
            for k in range(1, fade + 1):
                writer.append_data((prev + (a - prev) * k / fade).astype(np.uint8))
        for _ in range(int(seconds * FPS) - (fade if i else 0)):
            writer.append_data(a.astype(np.uint8))
    writer.close()
    stills[5][0].save(SITE / "videos" / "demo-poster.jpg", quality=88)
    print(f"{out} ({sum(s for _, s in stills):.1f} s)")


if __name__ == "__main__":
    main()
