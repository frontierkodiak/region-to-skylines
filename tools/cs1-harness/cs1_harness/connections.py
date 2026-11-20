"""Package-bound outside-path observations, not a service or geography verdict."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import time

from .cli import slot, staging
from .config import Config

MODES = {"road": "Car", "rail": "Train", "ship": "Ship", "air": "Plane"}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def outside_pair(networks, vehicle):
    """Farthest two outside endpoints in one undirected native component.

    This is only probe selection. Native pathfinding, not this graph, decides
    directionality and lane validity. Select no pair for disconnected entries.
    """
    segments = [s for s in networks["segments"] if any(vehicle in lane["vehicle"].split(", ") for lane in s["lanes"])]
    links = {}
    ends = {}
    for s in segments:
        links.setdefault(s["start"], set()).add(s["end"])
        links.setdefault(s["end"], set()).add(s["start"])
        lane = next(item["index"] for item in s["lanes"] if vehicle in item["vehicle"].split(", "))
        for key, pos, offset in [("start", "a", 0), ("end", "b", 255)]:
            if "Outside" in s[key + "_flags"].split(", "):
                ends[s[key]] = {"position": [s["id"], lane, offset], "xyz": s[pos]}
    candidates = []
    remaining = set(links)
    while remaining:
        pending = [min(remaining)]
        component = set()
        while pending:
            n = pending.pop()
            if n in component:
                continue
            component.add(n)
            pending.extend(links[n] - component)
        remaining -= component
        for a, b in itertools.combinations(sorted(component & ends.keys()), 2):
            distance = sum((x - y) ** 2 for x, y in zip(ends[a]["xyz"], ends[b]["xyz"]))
            candidates.append((distance, a, b))
    if not candidates:
        return None
    _, a, b = max(candidates)
    return [ends[a]["position"], ends[b]["position"]]


def outside_requests(networks, capability, vehicle):
    """Matched boundary/midpoint requests; change only endpoint lane offsets."""
    pair = outside_pair(networks, vehicle)
    if pair is None:
        return []
    by_id = {segment["id"]: segment for segment in networks["segments"]}
    requests = []
    for direction, (a, b) in enumerate([pair, pair[::-1]]):
        a_lanes = [lane["index"] for lane in by_id[a[0]]["lanes"] if vehicle in lane["vehicle"].split(", ")]
        b_lanes = [lane["index"] for lane in by_id[b[0]]["lanes"] if vehicle in lane["vehicle"].split(", ")]
        for a_lane, b_lane in itertools.product(a_lanes, b_lanes):
            for position_kind, a_offset, b_offset in [("boundary", a[2], b[2]), ("midpoint", 128, 128)]:
                requests.append(
                    {
                        "capability": capability,
                        "name": "outside-to-outside",
                        "direction": direction,
                        "position_kind": position_kind,
                        "from": [a[0], a_lane, a_offset],
                        "to": [b[0], b_lane, b_offset],
                    }
                )
    return requests


def collect(package, probes, out, wait_minutes=60):
    """Acquire/release the fair slot for ONE map; retain errors and cleanup."""
    out.mkdir(parents=True, exist_ok=False)
    cfg = Config.for_host()
    stage = staging(cfg, out)
    result = {
        "schema": 1,
        "observed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "artifact_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        "package": str(package),
        "limits": "New Game panel and native lane paths only; no port/airport service or editor-tool placement test.",
    }
    s = None
    try:
        with slot(cfg, stage, wait_minutes, {"command": "connections", "issue": "PL-1121", "label": package.name}) as s:
            result["observed_at"] = datetime.datetime.now(datetime.UTC).isoformat()
            result["collector_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            result["build_receipt"] = json.loads((cfg.build_dir / "build-receipt.json").read_text())
            s.require_offline = True
            s.record = False
            s.live = False
            installed = s.install_map(package)
            s.launch(["--noWorkshop"])
            c = s.client
            entries = c.call("maps")["maps"]
            entry = next(m for m in entries if m.get("path") and Path(m["path"]).samefile(installed))
            result["listed"] = entry
            deadline = time.monotonic() + 30
            while True:
                panel = c.call("new_game_panel", path=entry["path"], select=True)
                if not panel.get("pending"):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("native New Game panel did not become available")
                s.alive()
                time.sleep(0.1)
            dump(out / "panel.json", panel)
            c.call("new_game_panel", close=True)
            c.call("new_game", path=entry["path"])
            result["loaded"] = c.wait(
                lambda st: st.get("in_game") and not st.get("loading"), 600, "New Game", alive=s.alive
            )
            c.call("run", paused=True)
            networks = c.call("networks")
            dump(out / "networks.json", networks)
            route_points = []
            for segment in networks["segments"]:
                if any("Ship" in lane["vehicle"].split(", ") for lane in segment["lanes"]):
                    a, b = segment["a"], segment["b"]
                    route_points.extend([[a[0], a[2]], [(a[0] + b[0]) / 2, (a[2] + b[2]) / 2]])
            if route_points:
                dump(out / "ship-water-at-opening.json", c.call("water", points=route_points))
            requests = []
            # The frozen geographic probes also cover entry-to-start access.
            for p in probes.get("paths", []):
                requests.append({"capability": "rail" if p.get("rail") else "road", "name": p["name"], **p})
            for capability, vehicle in MODES.items():
                requests.extend(outside_requests(networks, capability, vehicle))
            result["paths"] = []
            c.call("run", paused=False, speed=1)
            for request in requests:
                s.check_offline()
                mode = {"road": "car", "rail": "train", "ship": "ship", "air": "plane"}[request["capability"]]
                row = {"request": request, "mode": mode}
                try:
                    started = c.call("path_start", **{"from": request["from"], "to": request["to"], "mode": mode})
                    deadline = time.monotonic() + 30
                    while True:
                        s.alive()
                        reply = c.call("path_result", id=started["id"])
                        if reply["complete"] or time.monotonic() >= deadline:
                            break
                        time.sleep(0.1)
                    row["result"] = reply
                    if not reply["complete"]:
                        raise RuntimeError("path did not complete; abort this session so no pending path is reused")
                except Exception as error:
                    row["error"] = str(error)
                    result["paths"].append(row)
                    dump(out / "observation.json", result)
                    raise
                result["paths"].append(row)
                dump(out / "observation.json", result)
            result["completed"] = True
    except Exception as error:
        result["error"] = str(error)
    finally:
        result["finished_at"] = datetime.datetime.now(datetime.UTC).isoformat()
        if s is not None:
            result["session"] = s.receipt
        dump(out / "observation.json", result)
        for name in ["game.log", "gpu.csv"]:
            if (stage / name).exists():
                shutil.copyfile(stage / name, out / name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--wait-minutes", type=float, default=60)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    for case in manifest["cases"]:
        if args.only and case["slug"] not in args.only:
            continue
        package = Path(case["package"])
        if hashlib.sha256(package.read_bytes()).hexdigest() != case["artifact_sha256"]:
            raise ValueError("package changed after selection")
        probes = json.loads(Path(case["probes"]).read_text())
        result = collect(package, probes, args.out / case["slug"], args.wait_minutes)
        print(case["slug"], "completed" if result.get("completed") else result.get("error"), flush=True)


if __name__ == "__main__":
    main()
