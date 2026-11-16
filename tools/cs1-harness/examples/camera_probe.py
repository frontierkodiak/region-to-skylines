"""Measure camera framing against native terrain/trees in a session-owned slot.

Run from tools/cs1-harness: uv run examples/camera_probe.py --map MAP --out DIR
Defaults reproduce the three PL-989 Rio woodland views; --point is repeatable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import time

from cs1_harness.cli import slot, staging
from cs1_harness.config import Config
from cs1_harness.mapcheck import collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("--point", action="append", help="name,x,z; repeatable")
    parser.add_argument("--sizes", nargs="+", type=float, default=[350, 700, 1400])
    parser.add_argument("--pitch", type=float, default=50)
    parser.add_argument("--yaw", type=float, default=0)
    parser.add_argument("--wait-minutes", type=float, default=0)
    args = parser.parse_args()
    points = args.point or ["ridge,-4500,-2400", "high-woodland,-1800,-300", "palms,-3000,-4800"]
    points = [(name, float(x), float(z)) for name, x, z in (p.split(",") for p in points)]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cfg = Config.for_host()
    stage = staging(cfg, out)
    root = pathlib.Path(__file__).resolve().parents[3]
    receipt = {
        "revision": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
        "diff": subprocess.check_output(["git", "-C", str(root), "diff", "HEAD"], text=True),
        "map_sha256": hashlib.sha256(args.map.read_bytes()).hexdigest(),
        "build": json.loads((cfg.build_dir / "build-receipt.json").read_text()),
        "measurements": [],
    }
    try:
        with slot(cfg, stage, args.wait_minutes, {"command": "camera-probe", "out": str(out)}) as session:
            session.live = session.record = False
            installed = session.install_map(args.map.resolve())
            session.launch(["--noWorkshop"])
            client = session.client
            entry = next(
                m
                for m in client.call("maps")["maps"]
                if m["path"] and pathlib.Path(m["path"]).exists() and pathlib.Path(m["path"]).samefile(installed)
            )
            client.call("new_game", path=entry["path"])
            client.wait(lambda s: s.get("in_game") and not s.get("loading"), 900, "city", alive=session.alive)
            client.call("run", paused=True, day_night=False)
            client.call("ui", visible=False)
            for name, x, z in points:
                for size in args.sizes:
                    request = {"position": [x, z], "size": size, "yaw": args.yaw, "pitch": args.pitch}
                    reply = client.call("camera", **request)
                    time.sleep(5)
                    observation = client.call(
                        "world_observe",
                        points=[{"name": name, "x": x, "z": z}],
                        tree_radius=400,
                        screen_points=[{"name": "center", "x": cfg.width / 2, "y": cfg.height / 2}],
                    )
                    cx, _, cz = observation["camera"]["render_position"]
                    under_camera = client.call("world_observe", points=[{"name": "under-camera", "x": cx, "z": cz}])
                    shot = stage / "shots" / f"{name}-{size:g}.png"
                    client.call("screenshot", path=str(shot))
                    deadline = time.monotonic() + 30
                    while not (shot.exists() and shot.stat().st_size > 0):
                        if time.monotonic() > deadline:
                            raise RuntimeError(f"screenshot not written: {shot.name}")
                        time.sleep(0.5)
                    time.sleep(0.5)
                    receipt["measurements"].append(
                        {
                            "name": name,
                            "request": request,
                            "reply": reply,
                            "observation": observation,
                            "under_camera": under_camera["points"][0],
                            "screenshot": f"shots/{shot.name}",
                        }
                    )
                    (out / "measurements.json").write_text(json.dumps(receipt, indent=2) + "\n")
                    print(
                        f"{name} size={size:g}: target={reply['camera']}; render={observation['camera']['render_position']}",
                        flush=True,
                    )
            client.call("camera", release=True)
    finally:
        collect(stage, out)


if __name__ == "__main__":
    main()
