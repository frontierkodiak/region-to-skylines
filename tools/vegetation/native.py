"""Foreground blade-only native catalog, A/B/A render timing and specimen sheet.

Run from tools/cs1-harness's locked environment. Only already-cached packages
are copied into this session's local Assets directory; --noWorkshop and the
read-only offline guard are mandatory. Session teardown removes those copies.
No saves, subscriptions, credentials, purchases or account settings are changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

from assemble import check_frame, classify
from framing import pair_framing

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cs1-harness"))
from cs1_harness.cli import slot, staging
from cs1_harness.config import Config


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def job(session, op, **params):
    session.client.call(op, **params)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        session.alive()
        result = session.client.call("job")
        if result["state"] == "failed":
            raise RuntimeError(result["error"])
        if result["state"] == "done":
            return result["result"]
        time.sleep(0.25)
    raise TimeoutError(op)


def capture(session, out, name):
    target = session.stage / "shots" / f"{name}.png"
    session.client.call("screenshot", path=str(target))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if target.exists() and target.stat().st_size > 0:
            time.sleep(0.3)
            shutil.copyfile(target, out / target.name)
            return target.name
        time.sleep(0.2)
    raise TimeoutError(str(target))


def capture_sheet(session, out, catalog, selected, base):
    specimens = []
    # One quiet patch, identical weather/lighting, common frame for each pair.
    x, z = catalog["forest_patch"]
    for i, candidate in enumerate(selected):
        h = candidate["main"]["size_m"][1]
        traits = classify(candidate["name"])
        similar = [t for t in base if traits["genus"] and classify(t["name"])["genus"] == traits["genus"]]
        if not similar:
            similar = [t for t in base if classify(t["name"])["form"] == traits["form"]] or base
        neighbour = min(similar, key=lambda t: abs(t["main"]["size_m"][1] - h))
        framing = pair_framing(candidate, neighbour)
        gap, height = framing["gap"], framing["height"]
        pair = job(
            session, "vegetation_pair", left=candidate["name"], right=neighbour["name"], x=x, z=z, gap=gap
        )
        if not all(t["created"] for t in pair["specimens"]):
            raise ValueError("Native specimen placement failed")
        ground = sum(t["position"][1] for t in pair["specimens"]) / 2
        views, cameras = {}, {}
        for view, size in [("close", framing["size"]), ("gameplay", 700)]:
            session.client.call(
                "camera",
                position=[x, ground + height * 0.4, z],
                size=size,
                pitch=25 if view == "close" else 50,
                yaw=0,
            )
            time.sleep(4)
            cameras[view] = session.client.call("camera_state")
            views[view] = capture(session, out, f"pair-{i + 1:02d}-{view}")
        specimens.append(
            {
                "candidate": candidate["name"],
                "base_neighbour": neighbour["name"],
                "pair": pair,
                "views": views,
                "cameras": cameras,
            }
        )
        write(out / "specimens.json", specimens)
        print("specimen", i + 1, candidate["name"], flush=True)


def run(installed, out, wait_minutes, sheet_only=False):
    if socket.gethostname().split(".")[0] != "blade":
        raise SystemExit("Native runs are restricted to blade")
    out.mkdir(parents=True, exist_ok=False)
    cfg = Config.for_host()
    inventory = json.loads(installed.read_text())
    packages = [
        p
        for p in inventory["workshop_packages"]
        if "TreeInfo" in p["components"] and not p["contains_assembly"]
    ]
    workshop = Path("/peach/Games/SteamLibrary/steamapps/workshop/content/255710")
    with slot(
        cfg,
        staging(cfg, out),
        wait_minutes,
        {
            "issue": "PL-1326",
            "label": "Vegetation supply: native inventory and comparisons",
            "eta_minutes": 15,
        },
    ) as session:
        session.require_offline = True
        session.record = False
        session.live = False
        session.label = "PL-1326 vegetation supply"
        for p in packages:
            source = workshop / p["workshop_id"] / p["file"]
            if hashlib.sha256(source.read_bytes()).hexdigest() != p["sha256"]:
                raise ValueError(f"Cached package changed: {p['workshop_id']}/{p['file']}")
            session.install_file(source, cfg.data_dir / "Addons/Assets/PL1326" / p["workshop_id"])
        map_path = cfg.game_dir / "Files/Maps/Grand River.crp"
        session.launch(["--noWorkshop"])
        # Use the path the game lists: Flatpak and /peach's symlink alias can
        # name the same file differently. This is the map-check driver's rule.
        listed = next(
            (
                m
                for m in session.client.call("maps")["maps"]
                if m.get("path") and Path(m["path"]).exists() and Path(m["path"]).samefile(map_path)
            ),
            None,
        )
        if listed is None:
            raise ValueError("The exact stock Grand River package is not listed by the game")
        write(out / "map.json", {**listed, "sha256": hashlib.sha256(map_path.read_bytes()).hexdigest()})
        session.client.call("new_game", path=listed["path"], city="PL1326 disposable vegetation comparison")
        session.client.wait(
            lambda s: s.get("in_game") and not s.get("loading"), 600, "disposable city", alive=session.alive
        )
        session.client.call("run", paused=True, day_night=False)
        session.client.call("time_of_day", hour=12)
        session.client.call("run", paused=True, day_night=False)
        session.client.call("ui", visible=False)
        write(
            out / "environment.json",
            {
                "cpu_cores": os.cpu_count(),
                "uptime": subprocess.check_output(["uptime"], text=True).strip(),
                "native_status": session.client.call("status"),
                "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "inventory_sha256": hashlib.sha256(installed.read_bytes()).hexdigest(),
            },
        )
        catalog = session.client.call("vegetation_catalog")
        write(out / "native-catalog.json", catalog)
        trees = catalog["trees"]
        base = [
            t
            for t in trees
            if "." not in t["name"]
            and t.get("main")
            and not any(
                word in t["name"].lower() for word in ("grass", "bush", "flower", "reed", "fern", "winter")
            )
        ]
        allowed = {p["workshop_id"] for p in packages}
        custom = [
            t
            for t in trees
            if t["name"].split(".")[0] in allowed
            and t.get("main")
            and t["main"]["triangles"] is not None
            and t["main"]["size_m"][1] >= 4
            and not any(
                word in t["name"].lower()
                for word in ("snag", "stump", "fallen", "dead", "flower", "grass", "bush")
            )
        ]
        # This is an installed-candidate sample, not a claim about the global
        # best twenty. Round-robin packs prevents one huge pack filling the sheet.
        groups = {}
        for t in sorted(custom, key=lambda t: t["main"]["triangles"]):
            groups.setdefault(t["name"].split(".")[0], []).append(t)
        selected = []
        while groups and len(selected) < 20:
            for prefix in list(groups):
                selected.append(groups[prefix].pop(0))
                if not groups[prefix]:
                    del groups[prefix]
                if len(selected) == 20:
                    break
        write(out / "selected.json", selected)
        if not selected or not base:
            raise ValueError("No usable native trees loaded")
        baseline = next((t for t in base if t["name"] == "Conifer2"), base[0])
        candidate = max(selected, key=lambda t: t["main"]["triangles"])
        point = catalog["forest_patch"]
        timing = []
        # Same positions, growth, camera and instance count. A/B/A bounds drift;
        # raw wall-frame samples are retained, not mislabelled GPU timings.
        for size in () if sheet_only else (350, 1400):
            session.client.call("camera", position=point, size=size, pitch=50, yaw=0)
            time.sleep(4)
            framing = session.client.call(
                "world_observe", screen_points=[{"name": "center", "x": cfg.width // 2, "y": cfg.height // 2}]
            )
            center = framing["screen_points"][0]
            if not center["hit"] or center["water"]["wet"]:
                raise ValueError("Benchmark camera is not over dry terrain")
            image_name = capture(session, out, f"framing-{size}")
            framing["frame_image"] = check_frame(out / image_name)
            write(out / f"framing-{size}.json", framing)
            for repeat in range(5):
                for arm, info in [("A-before", baseline), ("B", candidate), ("A-after", baseline)]:
                    population = job(session, "vegetation_retarget", name=info["name"])
                    sample = job(session, "vegetation_frames", frames=300)
                    timing.append(
                        {
                            "size": size,
                            "repeat": repeat,
                            "arm": arm,
                            "name": info["name"],
                            "population": population,
                            **sample,
                        }
                    )
                    write(out / "frame-samples.json", timing)
                    print("timed", size, repeat, arm, population["instances"], flush=True)
                    if repeat == 0:
                        capture(session, out, f"bench-{size}-{arm}")
        capture_sheet(session, out, catalog, selected, base)
        write(out / "status.json", session.client.call("status"))
        write(
            out / "build.json",
            json.loads(
                (Path(__file__).resolve().parents[1] / "cs1-harness/.build/build-receipt.json").read_text()
            ),
        )
    write(out / "session-receipt.json", session.receipt)
    write(
        out / "cleanup.json",
        {
            "game_pids": __import__("cs1_harness.session", fromlist=["game_pids"]).game_pids(),
            "state_file_exists": cfg.state_file.exists(),
            "installed_files_remaining": [str(p) for p in session.installed if p.exists()],
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wait-minutes", type=float, default=30)
    parser.add_argument(
        "--sheet-only", action="store_true", help="Capture the native sheet without repeating timing"
    )
    args = parser.parse_args()
    run(args.installed, args.out, args.wait_minutes, args.sheet_only)
