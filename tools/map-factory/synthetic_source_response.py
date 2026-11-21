"""Synthetic branching source-response arms, not geographic water qualification."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from closed_storage_candidate import ROOT, sha
from crp import (
    N,
    decode_u16,
    patch_metadata,
    read_package,
    water_payload,
    write_package,
)
from maintained_water_inventory import compile_inventory, initial_natural_checks
from natural_basins import protection
from natural_storage_candidate import write
from paint import paint
from resources import Knobs
from template import manager_tag
from water_diagnostics import bind_sources, decode_water, encoded_sources
from waterway_pieces import catalog

POLICY = "synthetic-branched-output-response-v1"
OUTPUTS = [0, 32, 128]
RATE = 128
STEPS = [(y, x) for y in (-1, 0, 1) for x in (-1, 0, 1) if (y, x) != (0, 0)]


def geographic(point):
    x, z = point
    a, e2 = 6378137, 0.00669437999014
    return [float(np.rad2deg(x / a)), float(np.rad2deg(z / (a * (1 - e2))))]


def channel(layout):
    node_positions = {
        str(n["id"]): [n["position"][0], 100.0, n["position"][2]]
        for n in layout["nodes"]
    }
    hydro = {
        "sources": [],
        "start_tile": 12,
        "start_area": {"landing": [768, -768]},
        "node_positions": node_positions,
    }
    environment = {
        "sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1},
        "rivers": [],
        "streams": [],
        "lakes": [],
        "riverAreas": [],
        "oceans": [],
    }
    protected = protection(environment, hydro, layout)
    main = [(x, 0) for x in range(-384, 385, 16)]
    branch = [(0, z) for z in range(384, -1, -16)]
    stages = {
        p: int(np.floor((99.5 - (p[0] + 384) / 768 * 0.5) * 64 + 0.5)) for p in main
    }
    for p in branch:
        stage = int(np.floor((99.25 + p[1] / 384 * 0.25) * 64 + 0.5))
        if p in stages and stages[p] != stage:
            raise ValueError("Synthetic junction has incompatible declared stages")
        stages[p] = stage
    attempts = []
    for turn in range(4):

        def rotate(point):
            x, z = point
            for _ in range(turn):
                x, z = -z, x
            return x, z

        for dx in range(-512, 513, 128):
            for dz in range(-512, 513, 128):
                points = {p: (rotate(p)[0] + dx, rotate(p)[1] + dz) for p in stages}
                nodes = {
                    (540 - z // 16, 540 + x // 16): stages[p]
                    for p, (x, z) in points.items()
                }
                own = set(nodes)
                rim = {(r + y, c + x) for r, c in own for y, x in STEPS} - own
                envelope = own | rim
                inside = all(
                    abs(c * 16 - 8640) <= 960 and abs(8640 - r * 16) <= 960
                    for r, c in envelope
                )
                hits = sum(bool(protected[n]) for n in envelope)
                attempts.append(
                    {
                        "turn": turn,
                        "translation_xz": [dx, dz],
                        "full_envelope_in_start_tile": inside,
                        "protected_hits": hits,
                    }
                )
                if not inside or hits:
                    continue
                floor = np.full((1081, 1081), 6400, np.uint16)
                water = np.zeros_like(floor)
                for node, stage in nodes.items():
                    floor[node], water[node] = stage - 96, 96
                ports = [points[main[0]], points[branch[0]], points[main[-1]]]
                port_stages = [stages[main[0]], stages[branch[0]], stages[main[-1]]]
                geometry = {
                    **environment,
                    "sq": {
                        **environment["sq"],
                        "slug": "synthetic-branched-response-v1",
                        "name": "Synthetic branched source response",
                    },
                    "streams": [
                        {
                            "name": "synthetic main",
                            "class": "stream",
                            "intermittent": 0,
                            "pts": [
                                geographic(points[p])
                                for p in (main[0], (0, 0), main[-1])
                            ],
                        },
                        {
                            "name": "synthetic tributary",
                            "class": "stream",
                            "intermittent": 0,
                            "pts": [
                                geographic(points[p]) for p in (branch[0], branch[-1])
                            ],
                        },
                    ],
                    "source": "predeclared synthetic geometry; no geographic/holdout input",
                }
                hydro.update(
                    map_id="PL1191-synthetic-branched-response-v1",
                    map_name="PL1191 synthetic branched response",
                    sea_level_m=35,
                    sources=[
                        {
                            "class": "stream",
                            "role": role,
                            "name": role,
                            "position": [x, 0, z],
                            "target": stage / 64,
                            "capacity": RATE / 65535,
                            "output_capacity": (RATE if i < 2 else 0) / 65535,
                        }
                        for i, ((x, z), stage, role) in enumerate(
                            zip(
                                ports,
                                port_stages,
                                ["main-inlet", "branch-inlet", "common-outlet-intake"],
                            )
                        )
                    ],
                )
                plan = {
                    "policy": POLICY,
                    "placement_attempts": attempts,
                    "nodes": [
                        {"node_rc": list(n), "stage_q": s, "bed_q": s - 96}
                        for n, s in sorted(nodes.items())
                    ],
                    "rim_rc": [list(n) for n in sorted(rim)],
                    "protected_sha256": hashlib.sha256(protected.tobytes()).hexdigest(),
                    "port_xz": [list(p) for p in ports],
                    "maximum_cut_m": float((6400 - floor).max() / 64),
                    "minimum_freeboard_m": float((6400 - max(nodes.values())) / 64),
                    "source_radius_model_m": float(10 + 0.4 * np.sqrt(RATE)),
                    "ports_not_per_node_regulation": True,
                    "outlet": "declared common intake port, not an unmodeled gravity exit or natural hydraulic junction",
                }
                return geometry, hydro, floor, water, plan
    raise ValueError(
        "No synthetic branching placement satisfies the fixed starttile/protection masks"
    )


def validate(floor, water, geometry, hydro, plan, layout):
    before = np.full((1081, 1081), 6400, np.int64)
    own = {tuple(p["node_rc"]) for p in plan["nodes"]}
    rim = {tuple(n) for n in plan["rim_rc"]}
    expected_rim = {(r + y, c + x) for r, c in own for y, x in STEPS} - own
    if rim != expected_rim or any(
        abs(c * 16 - 8640) > 960 or abs(8640 - r * 16) > 960 for r, c in own | rim
    ):
        raise ValueError("Synthetic full rim/starttile declaration changed")
    environment = copy.deepcopy(geometry)
    environment["streams"] = []
    no_sources = copy.deepcopy(hydro)
    no_sources["sources"] = []
    protected = protection(environment, no_sources, layout)
    if hashlib.sha256(protected.tobytes()).hexdigest() != plan[
        "protected_sha256"
    ] or any(protected[n] for n in own | rim):
        raise ValueError(
            "Synthetic protected evidence changed or intersects channel/rim"
        )
    mask = np.zeros(floor.shape, bool)
    for n in own:
        mask[n] = True
    cut = before.astype(np.int64) - floor.astype(np.int64)
    if (
        np.any(cut < 0)
        or np.any(cut > 192)
        or np.any(cut[~mask])
        or np.any(water[~mask])
    ):
        raise ValueError(
            "Synthetic construction violates no-fill/cut/channel-only initialization"
        )
    if any(int(floor[n]) != 6400 for n in rim):
        raise ValueError("Synthetic full eight-neighbour rim changed")
    for p in plan["nodes"]:
        node = tuple(p["node_rc"])
        if (
            int(floor[node]) != p["bed_q"]
            or int(water[node]) != p["stage_q"] - p["bed_q"]
        ):
            raise ValueError("Synthetic final bed/initial water changed")
        if any(
            int(floor[(node[0] + y, node[1] + x)]) - p["stage_q"] < 32
            for y, x in STEPS
            if (node[0] + y, node[1] + x) not in own
        ):
            raise ValueError("Synthetic bank freeboard below0.5m")
    for source in hydro["sources"]:
        x, _, z = source["position"]
        node = (int((8640 - z) / 16), int((x + 8640) / 16))
        if (
            node not in own
            or source["target"] * 64 - floor[node] < 64
            or not 10 + 0.4 * np.sqrt(RATE) < 16
        ):
            raise ValueError("Synthetic port footprint lacks full single-node1m depth")
    expected = {
        tuple(n)
        for r in catalog(geometry)["rows"]
        if r["field"] == "streams"
        for c in r["clips"]
        for n in c["nodes_rc"]
    }
    if expected != own:
        raise ValueError(
            "Synthetic source geometry does not bind every channel node/branch"
        )


def patch_outputs(raw, output):
    package, assets = read_package(raw)
    simulation = next(a for a in assets if a["kind"] == 52)
    data = simulation["payload"]
    decoded = decode_water(data)
    if len(decoded["sources"]) != 3:
        raise ValueError("Synthetic package needs exactly three declared ports")
    sources = encoded_sources(decoded)
    for source in sources[:2]:
        source["output_capacity"] = output / 65535
    chunk = (
        decoded["tag"]
        + water_payload(
            decoded["depth"], sources, decoded["frame"], decoded["sea_level_m"]
        )
        + decoded["tail"]
    )
    simulation["payload"] = data[: decoded["start"]] + chunk + data[decoded["end"] :]
    checksum = hashlib.md5(simulation["payload"]).hexdigest()
    for asset in assets:
        if asset["kind"] == 100:
            old = asset["payload"]
            asset["payload"] = patch_metadata(old, checksum)
            if patch_metadata(asset["payload"], hashlib.md5(data).hexdigest()) != old:
                raise ValueError(
                    "Synthetic metadata changed outside simulation assetRef"
                )
    return write_package(package, assets)


def package_check(folder, package, hydro, plan, geometry, layout):
    simulation = next(
        a["payload"] for a in read_package(package.read_bytes())[1] if a["kind"] == 52
    )
    decoded = decode_water(simulation)
    bind_sources(decoded, hydro)
    tag = manager_tag("TerrainManager")
    floor, offset = decode_u16(simulation, N, simulation.index(tag) + len(tag))
    delta, _ = decode_u16(simulation, int((floor != 0).sum()), offset)
    if (
        delta.any()
        or floor.astype("<u2").tobytes() != (folder / "terrain.u16").read_bytes()
        or decoded["depth"].astype("<u2").tobytes()
        != (folder / "water.u16").read_bytes()
    ):
        raise ValueError(
            "Synthetic final decoded grids differ from authored bounded grids"
        )
    validate(
        np.flipud(floor.reshape(1081, 1081)),
        np.flipud(decoded["depth"].reshape(1081, 1081)),
        geometry,
        hydro,
        plan,
        layout,
    )
    return decoded


def inventory_for(geometry, hydro):
    inventory = compile_inventory(geometry, hydro)
    inventory["schema"] = "polli.synthetic-source-response-inventory/1"
    for entry in inventory["entries"]:
        if entry.get("field") == "streams" and entry.get("contracts"):
            entry.update(
                status="compiled",
                reason="explicit synthetic channel-plan binds every source vertex/sector; dynamic supply unqualified",
            )
    for i, source in enumerate(hydro["sources"]):
        name = f"synthetic-port:{i}"
        inventory["entries"].append(
            {
                "id": name,
                "status": "compiled",
                "contracts": [
                    {
                        "id": name,
                        "kind": "engineered",
                        "points_xz": [source["position"][::2]],
                        "probe_names": [name],
                    }
                ],
            }
        )
        inventory["points"].append(
            {
                "name": name,
                "x": source["position"][0],
                "z": source["position"][2],
                "required": True,
            }
        )
    inventory["coverage_complete"] = not any(
        e["status"] == "unresolved" for e in inventory["entries"]
    )
    return inventory


def probe_spec(inventory, mask_sha):
    return {
        "points": inventory["points"],
        "reference_water": "reference-water.u16",
        "mapped_water": {
            "format": "cs1-water-mask-u8-v1",
            "file": "mapped-water.u8",
            "sha256": mask_sha,
        },
        "retain_opening_until_five": False,
        "study": "synthetic branched source-response, not geographic qualification",
    }


def export(output):
    if output.exists():
        raise ValueError("Use a fresh synthetic diagnostic preparation")
    output.mkdir(parents=True)
    layout = json.loads((ROOT / "templates/native-corridors.json").read_text())
    geometry, hydro, floor, water, plan = channel(layout)
    validate(floor, water, geometry, hydro, plan, layout)
    base = output / "parent"
    base.mkdir()
    for name, grid in [("terrain.u16", floor), ("water.u16", water)]:
        np.flipud(grid).astype("<u2").tofile(base / name)
    for name, data in [
        ("geometry.json", geometry),
        ("hydrology.json", hydro),
        ("channel-plan.json", plan),
        ("layout.json", layout),
    ]:
        write(base / name, data)
    landcover = output / "synthetic-landcover.u8.gz"
    landcover.write_bytes(
        gzip.compress(np.full((1081, 1081), 30, np.uint8).tobytes(), mtime=0)
    )
    # Resource/network packaging follows static admission, never substitutes it.
    paint(
        base,
        landcover,
        base,
        geometry=base / "geometry.json",
        knobs=Knobs(trees=0, seed=1191),
    )
    parent_package = base / (hydro["map_id"] + ".crp")
    decoded = package_check(base, parent_package, hydro, plan, geometry, layout)
    for source, actual in zip(hydro["sources"], decoded["sources"]):
        source["position"] = actual["position"]
    write(base / "hydrology.json", hydro)
    inventory = inventory_for(geometry, hydro)
    write(base / "inventory.json", inventory)
    initial = initial_natural_checks(inventory, np.flipud(water))
    if any(c["status"] != "pass" for c in initial["contracts"]):
        raise ValueError(
            "Synthetic mandatory initialization failed; retain refusal, do not observe unchanged"
        )
    write(base / "authored-initialization.json", initial)
    shutil.copyfile(base / "water.u16", base / "reference-water.u16")
    mask = np.zeros_like(water, np.uint8)
    for p in plan["nodes"]:
        mask[tuple(p["node_rc"])] = 1
    np.flipud(mask).tofile(base / "mapped-water.u8")
    write(base / "probes.json", probe_spec(inventory, sha(base / "mapped-water.u8")))
    arms = []
    for setting in OUTPUTS:
        arm = output / f"output-{setting:03d}"
        arm.mkdir()
        for n in [
            "terrain.u16",
            "water.u16",
            "geometry.json",
            "channel-plan.json",
            "layout.json",
            "inventory.json",
            "authored-initialization.json",
            "probes.json",
            "reference-water.u16",
            "mapped-water.u8",
        ]:
            shutil.copyfile(base / n, arm / n)
        h = copy.deepcopy(hydro)
        for source in h["sources"][:2]:
            source["output_capacity"] = setting / 65535
        write(arm / "hydrology.json", h)
        package = arm / f"PL1191-synthetic-branch-output-{setting:03d}.crp"
        package.write_bytes(patch_outputs(parent_package.read_bytes(), setting))
        package_check(arm, package, h, plan, geometry, layout)
        arms.append(
            {
                "setting": setting,
                "folder": arm.name,
                "package": package.name,
                "package_sha256": sha(package),
                "files_sha256": {p.name: sha(p) for p in arm.iterdir() if p.is_file()},
            }
        )
    generation = {
        "schema": "polli.synthetic-source-response-preparation/1",
        "policy": POLICY,
        "arms": arms,
        "parent_package_sha256": sha(parent_package),
        "geometry_sha256": sha(base / "geometry.json"),
        "channel_plan_sha256": sha(base / "channel-plan.json"),
        "definition_sha256": inventory["definition_sha256"],
        "native_observation": False,
        "geographic_candidate": False,
        "stable_water_promise": "unknown",
    }
    write(output / "generation.json", generation)
    return generation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.output), indent=2))
