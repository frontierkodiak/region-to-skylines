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

FOCUSED_V2 = {
    "rio": {"ship", "rail"},
    "charleston": {"ship"},
    "hong-kong": {"ship", "road", "rail"},
    "boston": {"ship"},
    "pittsburgh": {"road"},
}

MODES = {"road": "Car", "rail": "Train", "ship": "Ship", "air": "Plane"}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def outside_endpoints(networks, vehicle):
    ends = []
    for segment in networks["segments"]:
        lanes = [lane for lane in segment["lanes"] if vehicle in lane["vehicle"].split(", ")]
        for key, offset in [("start", 0), ("end", 255)]:
            flags = segment[key + "_flags"].split(", ")
            if lanes and "Outside" in flags:
                ends.append(
                    {
                        "node": segment[key],
                        "segment": segment["id"],
                        "offset": offset,
                        "roles": [role for role in flags if role in {"OneWayIn", "OneWayOut"}],
                        "lanes": lanes,
                    }
                )
    return ends


def outside_pairs(networks, vehicle):
    """Enumerate candidate outside pairs, never infer native reachability from node sharing.

    Road requires opposite OneWay roles. Rail includes every outside lane pair;
    the native pathfinder tests connectivity, with lane directions retained.
    """
    return [
        (a, b)
        for a, b in itertools.combinations(outside_endpoints(networks, vehicle), 2)
        if a["segment"] != b["segment"]
        and a["node"] != b["node"]
        and (vehicle != "Car" or ({*a["roles"], *b["roles"]} == {"OneWayIn", "OneWayOut"} and a["roles"] != b["roles"]))
    ]


def outside_pair(networks, vehicle):
    pairs = outside_pairs(networks, vehicle)
    if not pairs:
        return None
    a, b = pairs[0]
    return [[end["segment"], end["lanes"][0]["index"], end["offset"]] for end in [a, b]]


def outside_requests(networks, capability, vehicle):
    requests = []
    for pair_index, pair in enumerate(outside_pairs(networks, vehicle)):
        for direction, (a, b) in enumerate([pair, pair[::-1]]):
            for a_lane, b_lane in itertools.product(a["lanes"], b["lanes"]):
                for kind, a_offset, b_offset in [("boundary", a["offset"], b["offset"]), ("midpoint", 128, 128)]:
                    requests.append(
                        {
                            "capability": capability,
                            "name": "outside-to-outside",
                            "pair_index": pair_index,
                            "direction": direction,
                            "position_kind": kind,
                            "endpoint_roles": [a["roles"], b["roles"]],
                            "lane_directions": [a_lane.get("direction"), b_lane.get("direction")],
                            "from": [a["segment"], a_lane["index"], a_offset],
                            "to": [b["segment"], b_lane["index"], b_offset],
                        }
                    )
    return requests


def collect(package, probes, out, wait_minutes=60, capabilities=None):
    """Acquire/release the fair slot for ONE map; retain errors and cleanup."""
    capabilities = set(MODES) if capabilities is None else capabilities
    out.mkdir(parents=True, exist_ok=False)
    cfg = Config.for_host()
    stage = staging(cfg, out)
    result = {
        "schema": 2,
        "protocol": "NewGameFromMap/noWorkshop/non-inverted; all candidate outside lane pairs, boundary+midpoint, both directions; no construction",
        "observed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "artifact_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        "package": str(package),
        "requested_capabilities": sorted(capabilities),
        "limits": "New Game panel and native lane paths only; no port/airport service or editor-tool placement test.",
    }
    s = None
    try:
        with slot(cfg, stage, wait_minutes, {"command": "connections", "issue": "PL-1142", "label": package.name}) as s:
            result["observed_at"] = datetime.datetime.now(datetime.UTC).isoformat()
            result["collector_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            result["collector_sources"] = {
                name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ["connections.py", "runtime_identity.py"]
            }
            result["build_receipt"] = json.loads((cfg.build_dir / "build-receipt.json").read_text())
            s.require_offline = True
            s.record = False
            s.live = False
            installed = s.install_map(package)
            if s.receipt["map"]["sha256"] != result["artifact_sha256"]:
                raise ValueError("installed package changed before launch")
            s.launch(["--noWorkshop"])
            c = s.client
            from .runtime_identity import bind_runtime

            result["runtime_identity"] = bind_runtime(s, result["build_receipt"])
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
            result["new_game_protocol"] = c.call("new_game", path=entry["path"])
            if (
                result["new_game_protocol"].get("update_mode") != "NewGameFromMap"
                or result["new_game_protocol"].get("invert_traffic") != "False"
            ):
                raise ValueError("native New Game protocol is not bound")
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
            result["candidate_coverage"] = {
                cap: len(outside_requests(networks, cap, vehicle))
                for cap, vehicle in MODES.items()
                if cap in capabilities
            }
            requests = []
            # The frozen geographic probes also cover entry-to-start access.
            for p in probes.get("paths", []):
                if ("rail" if p.get("rail") else "road") not in capabilities:
                    continue
                requests.append({"capability": "rail" if p.get("rail") else "road", "name": p["name"], **p})
            for capability, vehicle in MODES.items():
                if capability not in capabilities:
                    continue
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
    parser.add_argument(
        "--focused-v2",
        action="store_true",
        help="Fixed four ship-positive cases plus the no-fresh-two-edge diagnostic subset",
    )
    parser.add_argument("--wait-minutes", type=float, default=60)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    for case in manifest["cases"]:
        if args.focused_v2 and case["slug"] not in FOCUSED_V2:
            continue
        if args.only and case["slug"] not in args.only:
            continue
        package = Path(case["package"])
        if hashlib.sha256(package.read_bytes()).hexdigest() != case["artifact_sha256"]:
            raise ValueError("package changed after selection")
        probes = json.loads(Path(case["probes"]).read_text())
        result = collect(
            package,
            probes,
            args.out / case["slug"],
            args.wait_minutes,
            FOCUSED_V2[case["slug"]] if args.focused_v2 else None,
        )
        print(case["slug"], "completed" if result.get("completed") else result.get("error"), flush=True)


if __name__ == "__main__":
    main()
