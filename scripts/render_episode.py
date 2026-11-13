"""Re-render a recorded Adaptive Policies episode in the VirtualHome simulator.

The episode is replayed from the trial's own task log: every script line that the
simulator executed, in order, against the same scene, character and starting room.
Actions that failed in the trial were rejected before reaching Unity, so they
changed nothing and are not replayed; the video pauses where they happened.
Recording uses the simulator's own cameras with animation on (the evaluation ran
with animation skipped and recorded only one still per action).

Default episode: Gemma 4 12B, implicit placement, temperature 0.6, reasoning off,
env2 task "make toast" (cluster run cluster_ap_implicit_gemma4_12b_001/env2/
ap-implicit-gemma4-12b-t06-m8192-roff-env2-r1), which neither baseline completed.

Run inside WSL with a VirtualHome player started on SIM_PORT (see
render_episode.sh) and the AdaptPolicies sources on PYTHONPATH:
    python scripts/render_episode.py --initial-state initial_state.json --output frames/
"""
import argparse
import glob
import json
import math
import os
import shutil

import cv2

from virtualhome.simulation.unity_simulator import UnityCommunication

ENV_ID = 2
INITIAL_ROOM = "kitchen"
# Executed lines from task_logs/make_toast/task_logs.txt, in order. The failed
# "[grab] <breadslice> (167)" between steps 1 and 2 was rejected by the
# precondition check (not close to the bread) and never reached Unity.
STEPS = [
    "<char0> [find] <toaster> (166)",
    "<char0> [find] <breadslice> (167)",
    "<char0> [grab] <breadslice> (167)",
    "<char0> [putback] <breadslice> (167) <toaster> (166)",
    "<char0> [switchon] <toaster> (166)",
]


def classes(graph):
    return {n["id"]: n["class_name"] for n in graph["nodes"]}


def relations(graph):
    ids = classes(graph)
    return {(ids[e["from_id"]], e["relation_type"], ids[e["to_id"]]) for e in graph["edges"]}


def center(graph, cls):
    node = next(n for n in graph["nodes"] if n["class_name"] == cls)
    return node["bounding_box"]["center"]


def add_counter_camera(comm, back=1.9, side=1.1, rise=0.75):
    """A static scene camera in front of and beside the toaster, looking at it."""
    _, graph = comm.environment_graph()
    t, c = center(graph, "toaster"), center(graph, "character")
    dx, dz = c[0] - t[0], c[2] - t[2]  # from the toaster towards the agent (out of the wall)
    norm = math.hypot(dx, dz) or 1.0
    dx, dz = dx / norm, dz / norm
    sx, sz = -dz, dx  # sideways along the counter
    pos = [t[0] + back * dx + side * sx, t[1] + rise, t[2] + back * dz + side * sz]
    vx, vy, vz = t[0] - pos[0], t[1] - pos[1], t[2] - pos[2]
    yaw = math.degrees(math.atan2(vx, vz))
    pitch = math.degrees(math.atan2(-vy, math.hypot(vx, vz)))
    ok, message = comm.add_camera(position=pos, rotation=[pitch, yaw, 0], field_view=50)
    assert ok, message
    # The player reports the new camera's index: "New camera created. Id:95".
    index = int(message.rsplit("Id:", 1)[1])
    print(f"counter camera {index}: position={[round(v, 2) for v in pos]} pitch={pitch:.1f} yaw={yaw:.1f}")
    return index


def still(comm, index, args, path):
    ok, images = comm.camera_image([index], image_width=args.width, image_height=args.height)
    assert ok
    cv2.imwrite(path, images[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--initial-state", required=True, help="the trial's tasks/make_toast/initial_state.json")
    ap.add_argument("--output", required=True)
    ap.add_argument("--port", default=os.getenv("SIM_PORT", "8085"))
    ap.add_argument("--camera", default="PERSON_FROM_BACK")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    out = os.path.abspath(args.output)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    comm = UnityCommunication(port=args.port, timeout_wait=600)
    comm.check_connection()  # waits until the player answers
    comm.reset(ENV_ID)
    assert comm.add_character("Chars/Male2", initial_room=INITIAL_ROOM), "add_character failed"
    _, graph = comm.environment_graph()

    # The replayed scene must be the trial's scene: same ids for the same objects.
    recorded = json.load(open(args.initial_state))
    live, ref = classes(graph), classes(recorded)
    for obj_id in (166, 167):
        assert live.get(obj_id) == ref.get(obj_id), (obj_id, live.get(obj_id), ref.get(obj_id))
    shared = set(live) & set(ref)
    same = sum(live[i] == ref[i] for i in shared)
    print(f"scene check: {same}/{len(ref)} recorded object ids match by class")

    if args.preview:
        # Framing check: run the first action without animation, place the camera
        # and save one still from it.
        ok, message = comm.render_script([STEPS[0]], skip_animation=True, find_solution=False)
        assert ok, message
        still(comm, add_counter_camera(comm), args, f"{out}/preview.png")
        return

    log, camera = [], [args.camera]
    for index, line in enumerate(STEPS):
        prefix = f"step{index}"
        ok, message = comm.render_script(
            [line], recording=True, skip_animation=False, find_solution=False,
            frame_rate=args.fps, camera_mode=camera, image_synthesis=["normal"],
            image_width=args.width, image_height=args.height,
            output_folder=out + "/", file_name_prefix=prefix)
        frames = sorted(glob.glob(f"{out}/{prefix}/**/*normal*.png", recursive=True))
        print(f"{line}: success={ok} frames={len(frames)} camera={camera} {message if not ok else ''}")
        assert ok, message
        log.append({"step": index, "line": line, "camera": camera[0],
                    "frames": [os.path.relpath(f, out) for f in frames]})
        if index == 0:
            # The agent now stands at the counter, where the camera behind it hides
            # the toaster. Watch the rest from a static camera beside the counter.
            camera = [str(add_counter_camera(comm))]
            still(comm, int(camera[0]), args, f"{out}/after_find_toaster.png")
        if index == 1:
            still(comm, int(camera[0]), args, f"{out}/after_find_bread.png")

    _, final = comm.environment_graph()
    rel = relations(final)
    toaster_on = any(n["class_name"] == "toaster" and "ON" in n["states"] for n in final["nodes"])
    print("breadslice ON toaster:", ("breadslice", "ON", "toaster") in rel, "| toaster ON:", toaster_on)
    json.dump({"env_id": ENV_ID, "initial_room": INITIAL_ROOM, "camera": args.camera, "fps": args.fps,
               "steps": log, "bread_on_toaster": ("breadslice", "ON", "toaster") in rel,
               "toaster_on": toaster_on}, open(f"{out}/replay.json", "w"), indent=1)


if __name__ == "__main__":
    main()
