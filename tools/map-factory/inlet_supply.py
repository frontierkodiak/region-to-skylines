"""Source-bound inlet hypotheses on existing inputs; not forward hydraulics."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
from scipy import ndimage


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rate(capacity):
    return math.floor(capacity * 65535 + 0.5)


def plans(repo, inputs, native):
    sys.path.insert(0, str(repo / "tools/map-factory"))
    from region import raster
    from surface_water import surface_geometry

    result = {}
    for directory in sorted(inputs.iterdir()):
        if not (directory / "hydrology.json").exists():
            continue
        name = directory.name
        hydro = json.loads((directory / "hydrology.json").read_text())
        geometry, _ = surface_geometry(
            json.loads((directory / "geometry.json").read_text())
        )
        gridroot = native / name / "grids"
        floor_path = gridroot / "t000-water-ground.u16"
        floor = np.fromfile(floor_path, "<u2").reshape(1081, 1081).astype(np.int64)
        depth = np.fromfile(gridroot / "t000-water.u16", "<u2").reshape(1081, 1081)
        mapped = raster(
            geometry["sq"], geometry.get("rivers", []) + geometry.get("streams", [])
        )
        channel = ndimage.binary_dilation(mapped, iterations=4)[::-1] | (depth > 6.4)
        for field in ["lakes", "riverAreas"]:
            channel |= raster(geometry["sq"], geometry.get(field, []), polygons=True)[
                ::-1
            ]
        sources = hydro["sources"]
        rows, chain = [], []
        for index, source in enumerate(sources):
            role = source.get("role")
            if role == "upstream":
                chain = []
            if role not in [
                "upstream",
                "interior",
                "crest",
                "trough",
                "bed_crest",
                "downstream",
            ]:
                chain = []
                continue
            chain.append(index)
            if role != "downstream":
                continue
            if source.get("underground_portal") == "surface_inlet_to_tunnel":
                current = rate(source["capacity"])
                row = {
                    "native_id": index + 1,
                    "old_rate": current,
                    "position": source["position"],
                    "name": source["name"],
                    "proposal": current,
                    "chain": chain.copy(),
                }
                eligible = bool(source.get("bank_limited"))
                coherent = (
                    len(chain) >= 2
                    and sources[chain[0]].get("role") == "upstream"
                    and all(
                        (sources[i]["name"], sources[i]["class"])
                        == (source["name"], source["class"])
                        for i in chain
                    )
                )
                row["scope"] = "bank-limited surface/tunnel input-only boundary"
                if not eligible or not coherent:
                    row["status"] = (
                        "outside_local_stage_class"
                        if not eligible
                        else "unresolved_chain"
                    )
                elif rate(source.get("output_capacity", source["capacity"])):
                    raise ValueError("Portal is not input-only")
                else:
                    supply = sum(
                        rate(sources[i].get("output_capacity", sources[i]["capacity"]))
                        for i in chain[:-1]
                    )
                    x, _, z = source["position"]
                    col, row_index = round((x + 8640) / 16), round((z + 8640) / 16)
                    extent = math.ceil((10 + 0.4 * math.sqrt(current)) / 16) + 1
                    r0, r1 = (
                        max(0, row_index - extent),
                        min(1081, row_index + extent + 1),
                    )
                    c0, c1 = max(0, col - extent), min(1081, col + extent + 1)
                    yy, xx = np.mgrid[r0:r1, c0:c1]
                    distance = np.hypot(xx * 16 - 8640 - x, yy * 16 - 8640 - z)
                    target = math.floor(source["target"] * 64 + 0.5)
                    # Reuse the existing writer's 0.125m local-stage intake margin.
                    unsafe = channel[r0:r1, c0:c1] & (floor[r0:r1, c0:c1] >= target - 8)
                    clearance = float(distance[unsafe].min()) if unsafe.any() else None
                    profile = (
                        current
                        if clearance is None
                        else min(
                            current,
                            math.floor((max(0, clearance - 0.01 - 10) / 0.4) ** 2),
                        )
                    )
                    proposed = min(current, supply, profile)
                    row.update(
                        supply_bound=supply,
                        profile_bound=profile,
                        nearest_upper_channel_m=clearance,
                        proposal=proposed,
                        old_radius_m=10 + 0.4 * math.sqrt(current),
                        proposal_radius_m=10 + 0.4 * math.sqrt(proposed),
                        status="ready_for_falsification"
                        if proposed > 0
                        else "blocked_zero_rate",
                    )
                rows.append(row)
            chain = []
        package = next(directory.glob("*.crp"))
        result[name] = {
            "inputs": {
                str(p): sha(p)
                for p in [
                    package,
                    directory / "hydrology.json",
                    directory / "geometry.json",
                    directory / "terrain.u16",
                    directory / "water.u16",
                    floor_path,
                    gridroot / "t005-water-ground.u16",
                ]
            },
            "sources": len(sources),
            "portals": rows,
            "changed": sum(r["proposal"] != r["old_rate"] for r in rows),
            "blocking": [
                r["native_id"] for r in rows if r["status"] == "blocked_zero_rate"
            ],
        }
    return result


def build_packages(repo, inputs, native, cases, destination):
    """Patch only UInt24 input rates, never regenerate other simulation fields."""
    sys.path.insert(0, str(repo / "tools/map-factory"))
    from crp import read_package, write_package
    from survey.craft_anatomy import Cursor, parse_water, section
    from survey.measure_maps import data_version

    builds = {}
    for name, plan in cases.items():
        if plan["blocking"]:
            raise ValueError(f"{name}: proposal would disable an inlet")
        source = inputs / name
        original = next(source.glob("*.crp"))
        receipt = json.loads((native / name / "session-receipt.json").read_text())
        if receipt["map"]["sha256"] != sha(original):
            raise ValueError(f"{name}: native floor belongs to another package")
        if receipt["cleanup"] != {
            "game": [],
            "steam_instances": [],
            "units_active": [],
        }:
            raise ValueError(f"{name}: incomplete original cleanup")
        for path, expected in plan["inputs"].items():
            if sha(Path(path)) != expected:
                raise ValueError(f"{name}: input changed after planning")
        hydro = json.loads((source / "hydrology.json").read_text())
        package, assets = read_package(original.read_bytes())
        simulation = next(a for a in assets if a["kind"] == 52)
        old = simulation["payload"]
        version = data_version(old)
        if version < 184:
            raise ValueError("Experimental patch requires the current source record")
        water = parse_water(old, version)
        c = Cursor(old, section(old, "WaterSimulation"))
        wet = c.arr(1081 * 1081, 2).reshape(1081, 1081) != 0
        c.arr(wet.sum(), 2)
        vx, vz = wet.copy(), wet.copy()
        vx[:, :-1] |= wet[:, 1:]
        vz[:-1, :] |= wet[1:, :]
        c.arr(vx.sum(), 2, signed=True)
        c.arr(vz.sum(), 2, signed=True)
        count = c.be("H")
        if count != len(hydro["sources"]) or count != plan["sources"]:
            raise ValueError("Source table count mismatch")
        changed = bytearray(old)
        allowed = set()
        edits = []
        for i, (metadata, control) in enumerate(
            zip(hydro["sources"], water["sources"])
        ):
            if (
                control["type"] != 1
                or control["input"] != control["output"]
                or control["input"][::2] != metadata["position"][::2]
                or control["target_raw"] != math.floor(metadata["target"] * 64 + 0.5)
            ):
                raise ValueError(
                    "Encoded source geometry/target does not match provenance"
                )
            if control["input_rate"] != rate(metadata["capacity"]) or control[
                "output_rate"
            ] != rate(metadata.get("output_capacity", metadata["capacity"])):
                raise ValueError("Encoded source rate does not match provenance")
            record_start = c.o + i * 43
            if old[record_start + 34 : record_start + 37] != control[
                "input_rate"
            ].to_bytes(3, "big"):
                raise ValueError("Input field offset mismatch")
        for row in plan["portals"]:
            if row["proposal"] == row["old_rate"]:
                continue
            index = row["native_id"] - 1
            offset = c.o + index * 43 + 34
            changed[offset : offset + 3] = row["proposal"].to_bytes(3, "big")
            allowed.update(range(offset, offset + 3))
            hydro["sources"][index]["capacity"] = row["proposal"] / 65535
            hydro["sources"][index]["inlet_supply_experiment"] = row
            edits.append(
                {
                    "native_id": index + 1,
                    "offset": offset,
                    "before": row["old_rate"],
                    "after": row["proposal"],
                }
            )
        if any(
            a != b and i not in allowed for i, (a, b) in enumerate(zip(old, changed))
        ):
            raise ValueError("Non-input-rate simulation change")
        after = parse_water(bytes(changed), version)
        for i, (a, b) in enumerate(zip(water["sources"], after["sources"])):
            if {k: v for k, v in a.items() if k != "input_rate"} != {
                k: v for k, v in b.items() if k != "input_rate"
            }:
                raise ValueError("Another encoded control field changed")
        old_md5 = hashlib.md5(old).hexdigest().encode()
        new_md5 = hashlib.md5(changed).hexdigest().encode()
        simulation["payload"] = bytes(changed)
        for a in assets:
            if a["kind"] == 100:
                if a["payload"].count(old_md5) != 1:
                    raise ValueError("Ambiguous map asset reference")
                a["payload"] = a["payload"].replace(old_md5, new_md5)
        target = destination / name
        target.mkdir(parents=True, exist_ok=False)
        for filename in [
            "terrain.u16",
            "water.u16",
            "geometry.json",
            "plan.npz",
            "resources.json",
            "resources.png",
        ]:
            if (source / filename).exists():
                shutil.copyfile(source / filename, target / filename)
        binary = write_package(package, assets)
        read_package(binary)
        (target / original.name).write_bytes(binary)
        (target / "hydrology.json").write_text(json.dumps(hydro, indent=2) + "\n")
        result = {
            "qualification": "experimental_unqualified",
            "package": {"sha256": sha(target / original.name)},
            "parent_package_sha256": sha(original),
            "planner_sha256": sha(Path(__file__)),
            "edits": edits,
            "simulation_byte_changes": sum(a != b for a, b in zip(old, changed)),
            "only_encoded_input_rates_and_asset_reference_changed": True,
            "forward_hydraulics": "not tested",
            "heads_grids_output_rates_preserved": True,
        }
        (target / "generation.json").write_text(json.dumps(result, indent=2) + "\n")
        builds[name] = result
    return builds


def trace_replay(repo, trace, case):
    sys.path.insert(0, str(repo / "tools/cs1-harness"))
    from cs1_harness.watertrace import footprint, intake

    header, *records = map(json.loads, trace.read_text().splitlines())
    nodes = np.asarray(header["nodes"], np.int64)
    proposals = {r["native_id"]: r for r in case["portals"]}
    result = []
    for native_id in header["targets"]:
        source0 = next(s for s in records[0]["sources"] if s["id"] == native_id)
        control = source0["before"]
        if not control["input_rate"] or control["output_rate"]:
            continue
        rows = []
        rates = {"one_node_224": 224}
        if native_id in proposals:
            p = proposals[native_id]
            rates.update(
                supply_only=min(p["old_rate"], p.get("supply_bound", p["old_rate"])),
                supply_and_profile=p["proposal"],
            )
        old_mask = footprint(nodes, control["input"], control["input_rate"])
        old_rows = []
        for record in records:
            s = next(s for s in record["sources"] if s["id"] == native_id)
            pre = np.asarray(s["pre_cells"], np.int64)[: len(nodes) * 4].reshape(-1, 4)
            old = intake(
                pre[old_mask, 1],
                pre[old_mask, 0],
                control["target"],
                control["input_rate"],
            )
            assert old[0] == s["availability"] and old[1] == s["nominal"]
            assert int(old[2].sum()) == s["input"]["water"]
            old_rows.append({"nominal": old[1], "removed": int(old[2].sum())})
            for label, candidate in rates.items():
                mask = footprint(nodes, control["input"], candidate)
                available, nominal, removed = intake(
                    pre[mask, 1], pre[mask, 0], control["target"], candidate
                )
                rows.append(
                    {
                        "step": record["step"],
                        "variant": label,
                        "rate": candidate,
                        "nodes": int(mask.sum()),
                        "availability": available,
                        "unclamped_positive_request": max(0, available >> 1),
                        "nominal": nominal,
                        "removed": int(removed.sum()),
                        "old_removed": int(old[2].sum()),
                    }
                )
        summaries = {}
        for label in rates:
            r = [v for v in rows if v["variant"] == label]
            summaries[label] = {
                "rate": rates[label],
                "nodes": r[0]["nodes"],
                "peak_unclamped_positive_request": max(
                    v["unclamped_positive_request"] for v in r
                ),
                "cap_clipped_updates": sum(
                    v["unclamped_positive_request"] > rates[label] for v in r
                ),
                "positive_updates": sum(v["removed"] > 0 for v in r),
                "newly_positive_updates": sum(
                    v["removed"] > 0 and v["old_removed"] == 0 for v in r
                ),
                "removed_sum": sum(v["removed"] for v in r),
                "changed_updates": sum(v["removed"] != v["old_removed"] for v in r),
            }
        result.append(
            {
                "native_id": native_id,
                "old_nodes": int(old_mask.sum()),
                "old_peak_nominal": max(v["nominal"] for v in old_rows),
                "old_total_removed": sum(v["removed"] for v in old_rows),
                "variants": summaries,
                "steps": rows,
            }
        )
    return {
        "trace_sha256": sha(trace),
        "completed_updates": len(records),
        "sources": result,
        "limit": "Every variant reuses ACTUAL OLD pre-input arrays independently. It is not a changed-run trajectory, capacity guarantee or map gate pass.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--native", type=Path, required=True)
    p.add_argument("--trace", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--build",
        type=Path,
        help="new experimental output directory; never production fixtures",
    )
    p.add_argument(
        "--trace-case",
        required=True,
        help="case name only for fixed-preimage diagnostic replay",
    )
    args = p.parse_args()
    all_cases = plans(args.repo, args.inputs, args.native)
    result = {
        "policy": "input-only bank-limited portal: min(old input, sum of that source-chain's encoded output rates, existing upper-channel footprint limit); no heads, grids, output rates or selectors by probe/camera/region",
        "source_sha256": sha(Path(__file__)),
        "cases": all_cases,
        "actual_preimage_replay": trace_replay(
            args.repo, args.trace, all_cases[args.trace_case]
        ),
        "candidate_produced": False,
        "fresh_native": False,
    }
    if args.build:
        result["builds"] = build_packages(
            args.repo, args.inputs, args.native, all_cases, args.build
        )
        result["candidate_produced"] = True
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: {
                    "portals": len(v["portals"]),
                    "changed": v["changed"],
                    "blocking": v["blocking"],
                }
                for k, v in all_cases.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
