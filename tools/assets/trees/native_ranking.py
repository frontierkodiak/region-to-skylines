"""One foreground slot: native single-tree ranking inputs, then complete teardown."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--harness", type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.harness))
    from cs1_harness.assets import Driver
    from cs1_harness.cli import slot
    from cs1_harness.config import Config
    from cs1_harness.session import game_pids

    plan = json.loads(a.plan.read_text())
    cfg = Config.for_host("blade")
    a.out.mkdir(parents=True, exist_ok=False)
    write(a.out / "plan.json", plan)
    packages = {}
    for t in plan["trees"]:
        for package in t["packages"]:
            source = Path(package["local_path"])
            if hashlib.sha256(source.read_bytes()).hexdigest() != package["sha256"]:
                raise ValueError("Changed accepted source package")
            packages[str(source)] = package
    stage = cfg.harness_home / "runs" / "PL1328-native-ranking-v1"
    started = time.monotonic()
    rows = []
    try:
        with slot(
            cfg,
            stage,
            5,
            {
                "issue": "PL-1328",
                "label": "single-tree ranking captures",
                "eta_minutes": 10,
            },
        ) as s:
            s.require_offline = True
            s.record = False
            s.live = False
            for source in packages:
                path = Path(source)
                s.install_file(
                    path,
                    cfg.data_dir / "Addons/Assets/PL1328-ranking" / path.parent.name,
                )
            write(
                a.out / "build.json",
                json.loads((cfg.build_dir / "build-receipt.json").read_text()),
            )
            s.launch(["--noWorkshop"])
            c = s.client
            entry = next(
                m for m in c.call("maps")["maps"] if m["name"] == "Grand River"
            )
            c.call("new_game", path=entry["path"], city="PL1328 disposable ranking")
            d = Driver(s, a.out, log=lambda t: print(t, flush=True))
            d.wait_level("in_game", 600, "ranking city")
            c.call("run", paused=True, day_night=False)
            c.call("time_of_day", hour=12)
            c.call("ui", visible=False)
            catalog = c.call("vegetation_catalog")
            write(a.out / "catalog.json", catalog)
            available = {t["name"] for t in catalog["trees"]}
            if not all(t["name"] in available for t in plan["trees"]):
                raise ValueError("A frozen ranking prefab did not load")
            for ordinal, t in enumerate(plan["trees"]):
                name = t["name"]
                # Pair supplies the exact terrain Y at x=0,z=300. It is never photographed.
                pair = d.job(
                    c.call(
                        "vegetation_pair", left=name, right=name, x=12.5, z=300, gap=25
                    ),
                    60,
                    "terrain fixture",
                )
                y = pair["specimens"][0]["position"][1]
                single = d.job(
                    c.call("vegetation_palette", names=[name], x=120, z=300),
                    60,
                    "single tree",
                )
                if (
                    len(single["specimens"]) != 1
                    or not single["specimens"][0]["created"]
                ):
                    raise ValueError("Single-tree placement failed")
                # Palette releases old instances; retarget flushes stale paused render groups.
                d.job(
                    c.call("vegetation_retarget", name=name), 60, "flush render groups"
                )
                if c.call("vegetation_catalog")["instances"] != 1:
                    raise ValueError("Competing trees remain")
                for view, distance in plan["views"].items():
                    if view == "billboard" and name not in plan["anchors"]:
                        continue
                    pitch = 20 if view == "close" else 40
                    position = [0, y + 8, 300]
                    c.call(
                        "camera", position=position, size=distance, pitch=pitch, yaw=0
                    )
                    deadline = time.monotonic() + 20
                    while True:
                        state = c.call("camera_state")
                        if (
                            abs(state["size"] - distance) < 0.1
                            and abs(state["pitch"] - pitch) < 0.1
                            and max(
                                abs(x - z) for x, z in zip(state["position"], position)
                            )
                            < 0.1
                        ):
                            break
                        if time.monotonic() > deadline:
                            raise TimeoutError("Camera did not settle")
                        time.sleep(0.1)
                    stem = f"{ordinal:02d}-{view}"
                    d.shot(stem, settle=0.5)
                    image = a.out / (stem + ".png")
                    shutil.copyfile(stage / "shots" / image.name, image)
                    row = {
                        "name": name,
                        "genus": t["genus"],
                        "anchor": name in plan["anchors"],
                        "view": view,
                        "file": image.name,
                        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                        "camera": state,
                        "instances": 1,
                    }
                    rows.append(row)
                    write(a.out / "frames.json", rows)
                print("captured", ordinal + 1, name, flush=True)
            c.call("camera", release=True)
    finally:
        if stage.exists():
            shutil.copytree(stage, a.out / "session", dirs_exist_ok=True)
        write(
            a.out / "cleanup.json",
            {
                "wall_seconds": time.monotonic() - started,
                "game_pids": game_pids(),
                "frames": len(rows),
            },
        )


if __name__ == "__main__":
    main()
