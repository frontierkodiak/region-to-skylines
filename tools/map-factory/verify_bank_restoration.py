"""Compare regenerated bank candidates with the preceding full candidate maps."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from crp import read_package
from template import manager_tag


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_continuous_floor(before, after, water):
    """Conservative CPU guard, not a production carve or acceptance mask.

    A wet vertex alone does not fix the terrain sampled between vertices.
    Keep its adjacent bilinear patches unchanged. Installed SampleWaterData IL
    reads four m_blockHeights vertices, then interpolates with 8-bit fractions.
    This is not a claim about the renderer's separate smooth-height/shader path.
    """
    wet = np.asarray(water).reshape(1081, 1081) > 0
    support = ndimage.maximum_filter(wet, size=3, mode="constant").ravel()
    changed = support & (np.asarray(before).ravel() != np.asarray(after).ravel())
    if changed.any():
        raise ValueError(
            f"Continuous wet-floor guard: {int(changed.sum())} neighboring terrain vertices changed"
        )


def native_water_ground(terrain, positions):
    """CPU replay of SampleWaterData's fixed-point ground interpolation only.

    Installed Assembly-CSharp SHA-256  c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1.
    IL 0000-00A2 selects the four vertices; 02B1-033A interpolates ground.
    This does not reconstruct water surface, velocity or the renderer.
    """
    ground = np.asarray(terrain).reshape(1081, 1081).astype(np.int64)
    result = []
    for x, z in positions:
        ix, iz = np.floor(
            (np.asarray([x, z], dtype=np.float32) + np.float32(8640)) * np.float32(16)
        ).astype(np.int64)
        x0, x1 = np.clip([ix >> 8, (ix >> 8) + 1], 0, 1080)
        z0, z1 = np.clip([iz >> 8, (iz >> 8) + 1], 0, 1080)
        a = ground[z0, x0] + ((ground[z1, x0] - ground[z0, x0]) * (iz & 255) >> 8)
        b = ground[z0, x1] + ((ground[z1, x1] - ground[z0, x1]) * (iz & 255) >> 8)
        result.append(float(a + ((b - a) * (ix & 255) >> 8)) / 64)
    return result


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
        require_continuous_floor(terrain, candidate, water)
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
