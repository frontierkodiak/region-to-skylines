"""Compare regenerated bank candidates with the preceding full candidate maps."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from crp import read_package
from template import manager_tag


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(before, after):
    results = []
    for work in sorted(after.iterdir()):
        old = before / work.name
        a = json.loads((old / "hydrology.json").read_text())
        b = json.loads((work / "hydrology.json").read_text())
        terrain = np.fromfile(old / "terrain.u16", dtype="<u2")
        candidate = np.fromfile(work / "terrain.u16", dtype="<u2")
        water = np.fromfile(old / "water.u16", dtype="<u2")
        np.testing.assert_array_equal(
            water, np.fromfile(work / "water.u16", dtype="<u2")
        )
        assert np.all(candidate >= terrain), work.name
        np.testing.assert_array_equal(candidate[water > 0], terrain[water > 0])
        for name in ["geometry.json", "banks.f32", "source-geometry.json"]:
            assert sha(old / name) == sha(work / name), (work.name, name)
        for name in ["samples", "start_tile", "surface_water_classification"]:
            assert a[name] == b[name], (work.name, name)
        assert len(a["sources"]) == len(b["sources"])
        water_components = []
        for folder, hydro in [(old, a), (work, b)]:
            _, assets = read_package((folder / (hydro["map_id"] + ".crp")).read_bytes())
            payload = next(asset["payload"] for asset in assets if asset["kind"] == 52)
            water_components.append(
                payload[
                    payload.index(manager_tag("WaterSimulation")) : payload.index(
                        manager_tag("NetManager")
                    )
                ]
            )
        assert water_components[0] == water_components[1], (
            work.name,
            "native WaterSimulation component changed",
        )
        for source, target in zip(a["sources"], b["sources"]):
            # Footprint diagnostic distances may change outside the physical
            # radius. All effective source fields must remain identical.
            assert {
                k: v for k, v in source.items() if k != "short_source_footprint"
            } == {k: v for k, v in target.items() if k != "short_source_footprint"}, (
                work.name,
                source,
            )
            col = round(540 + source["position"][0] / 16)
            row = round(540 + source["position"][2] / 16)
            index = row * 1081 + col
            assert candidate[index] == terrain[index], (work.name, source)
            yy, xx = np.mgrid[:1081, :1081]
            rate = max(source["capacity"], source.get("output_capacity", 0))
            radius = 10 + 0.4 * np.sqrt(np.floor(rate * 65535 + 0.5))
            support = (np.hypot(yy - row, xx - col).ravel() * 16 <= radius) & (
                terrain / 64 < source["target"]
            )
            np.testing.assert_array_equal(candidate[support], terrain[support])
        for key, position in a["node_positions"].items():
            assert position[::2] == b["node_positions"][key][::2]
        results.append(
            {
                "slug": work.name,
                "before_crp_sha256": sha(old / (a["map_id"] + ".crp")),
                "after_crp_sha256": sha(work / (b["map_id"] + ".crp")),
                "restoration": b["bank_restoration"],
                "changed_terrain_cells": int((terrain != candidate).sum()),
                "changed_terrain_bytes": sum(
                    x != y for x, y in zip(terrain.tobytes(), candidate.tobytes())
                ),
                "max_raise_m": float((candidate.astype(float) - terrain).max() / 64),
                "lowered_cells": 0,
                "initial_water_byte_identical": True,
                "all_initial_wet_floor_byte_identical": True,
                "effective_controls_identical": True,
                "native_water_component_byte_identical": True,
                "source_centres_and_below_target_footprints_unchanged": True,
                "sample_groups_positions_and_masks_identical": True,
                "network_horizontal_positions_identical": True,
                "changed_network_node_heights": sum(
                    a["node_positions"][k] != b["node_positions"][k]
                    for k in a["node_positions"]
                ),
                "resource_plan_byte_identical": sha(old / "plan.npz")
                == sha(work / "plan.npz"),
            }
        )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.before, args.after), indent=2))
