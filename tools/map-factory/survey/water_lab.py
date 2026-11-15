"""Build a matched CS1 stream experiment; never alters production fixtures.

Run with the map-factory uv project. Creates two experimental CRPs from the
fingerprint-bound native template, plus exact grids, probes and a manifest.
Native results, not these prepared grids, decide whether a stream persists.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np

FACTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
from crp import read_package, write_map  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out: Path) -> dict:
    template = FACTORY / "templates/native-corridors.crp"
    layout = FACTORY / "templates/native-corridors.json"
    spec = json.loads(layout.read_text())
    coordinates = np.arange(1081) * 16.0 - 8640
    xx, zz = np.meshgrid(coordinates, coordinates)
    bank = 120 - 0.001 * xx
    cases = list(itertools.product([1, 2, 3, 4], [0.5, 1, 2, 4], [0.005, 0.02, 0.08]))
    arms = []
    for arm in ["direct", "reservoir"]:
        target = out / arm
        target.mkdir(parents=True, exist_ok=True)
        height = bank.copy()
        surface = np.full_like(bank, -1.0)
        sources, points, records = [], [], []
        for index, (floor_nodes, incision, capacity) in enumerate(cases):
            column, row = divmod(index, 16)
            x0 = -7680 + column * 5120
            x1 = x0 + 4096
            z0 = -3840 + row * 512 + (8 if floor_nodes % 2 == 0 else 0)
            half_floor = (floor_nodes - 1) * 8.0
            cut = incision * np.clip((half_floor + 16 - np.abs(zz - z0)) / 16, 0, 1)
            in_reach = (xx >= x0) & (xx <= x1)
            cut *= in_reach
            height = np.minimum(height, bank - cut)
            reach_surface = bank - incision * 0.25
            wet = in_reach & (cut > incision * 0.25)
            surface[wet] = np.maximum(surface[wet], reach_surface[wet])
            source_x = x0 + 64
            head_stage = 120 - 0.001 * source_x - incision * 0.25
            if arm == "reservoir":
                radius = np.hypot(xx - source_x, zz - z0)
                pond_cut = (incision + 2.0) * np.clip((80 - radius) / 16, 0, 1)
                height = np.minimum(height, bank - pond_cut)
                pond_wet = (radius < 80) & (height < head_stage)
                surface[pond_wet] = np.maximum(surface[pond_wet], head_stage)
            case_id = f"n{floor_nodes}-d{incision:g}-c{capacity:g}"
            sources.append(
                {
                    "name": case_id,
                    "position": [source_x, 0, z0],
                    "target": head_stage,
                    "capacity": capacity,
                }
            )
            sources.append(
                {
                    "name": case_id + "-outlet",
                    "position": [x1 - 16, 0, z0],
                    "target": 120 - 0.001 * (x1 - 16) - incision,
                    "capacity": 0.08,
                    "output_capacity": 0,
                }
            )
            for along in [256, 1024, 2048, 3072, 3840]:
                for across in [-8, 0, 8] if floor_nodes % 2 == 0 else [0]:
                    points.append(
                        {
                            "name": f"{case_id}-x{along}-z{across}",
                            "x": x0 + along,
                            "z": z0 + across,
                        }
                    )
            records.append(
                {
                    "id": case_id,
                    "floor_nodes": floor_nodes,
                    "flat_floor_width_m": (floor_nodes - 1) * 16,
                    "bank_to_bank_width_m": (floor_nodes + 1) * 16,
                    "nominal_wet_width_m": (floor_nodes - 1) * 16 + 24,
                    "incision_m": incision,
                    "prefill_depth_m": incision * 0.75,
                    "capacity": capacity,
                    "encoded_rate": math.floor(capacity * 65535 + 0.5),
                    "source_footprint_radius_m": math.sqrt(
                        math.floor(capacity * 65535 + 0.5)
                    )
                    * 0.4
                    + 10,
                    "x0": x0,
                    "x1": x1,
                    "z": z0,
                    "source_id": index * 2 + 1,
                    "outlet_id": index * 2 + 2,
                }
            )
        raw = np.rint(height * 64).astype("<u2")
        depth = np.rint(np.maximum(0, surface - height) * 64).astype("<u2")
        raw.tofile(target / "terrain.u16")
        depth.tofile(target / "water.u16")
        hydro = {
            "map_id": f"PL979-{arm}",
            "map_name": f"PL979 stream lab - {arm}",
            "sea_level_m": 0,
            "sources": sources,
            "start_tile": 12,
            "node_positions": {
                str(n["id"]): [
                    n["position"][0],
                    128 - 0.001 * n["position"][0],
                    n["position"][2],
                ]
                for n in spec["nodes"]
            },
        }
        (target / "hydrology.json").write_text(json.dumps(hydro, indent=2) + "\n")
        views = [
            {"name": "matrix", "x": 0, "z": 0, "size": 8500, "yaw": 0, "pitch": 85},
            {
                "name": "headwaters",
                "x": -2496,
                "z": 0,
                "size": 700,
                "yaw": 0,
                "pitch": 65,
            },
            {
                "name": "stream-close",
                "x": -512,
                "z": -256,
                "size": 450,
                "yaw": 0,
                "pitch": 65,
            },
        ]
        probes = {
            "points": points,
            "views": views,
            "retain_opening_until_five": True,
            "startup_views": {
                "opening": {"native_yaw_degrees": 0, "render_heading_degrees": 0},
                "area_zoom": {"native_yaw_degrees": 0, "render_heading_degrees": 0},
                "tolerance_degrees": 1,
                "opening_center": {"x": 0, "z": 0, "tolerance_m": 64},
            },
        }
        (target / "probes.json").write_text(json.dumps(probes, indent=2) + "\n")
        package = target / f"PL979-{arm}.crp"
        write_map(
            template,
            layout,
            target / "terrain.u16",
            target / "water.u16",
            target / "hydrology.json",
            package,
        )
        _, assets = read_package(package.read_bytes())
        simulation = next(a["payload"] for a in assets if a["kind"] == 52)
        arms.append(
            {
                "arm": arm,
                "crp": str(package),
                "sha256": digest(package),
                "simulation_sha256": hashlib.sha256(simulation).hexdigest(),
                "grids": {
                    p.name: digest(p)
                    for p in [target / "terrain.u16", target / "water.u16"]
                },
                "cases": records,
            }
        )
    manifest = {
        "template_sha256": digest(template),
        "slope": 0.001,
        "reach_length_m": 4096,
        "cell_m": 16,
        "reservoir_radius_m": 80,
        "reservoir_extra_incision_m": 2,
        "arms": arms,
        "qualification": "prepared only; no native result",
        "limits": [
            "Ideal straight channels; not a universal terrain-independent minimum.",
            "One reservoir arm changes storage/shape, not source target or rate.",
            "Outlet is an explicit absorbing control in both arms.",
            "Native loaded terrain and initial grid must match before interpreting results.",
            "No-flow scenery, city water demand, evaporation and long-run behavior are not qualified.",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    result = build(args.out.resolve())
    print(
        json.dumps(
            {
                "arms": len(result["arms"]),
                "cases_per_arm": len(result["arms"][0]["cases"]),
                "qualification": result["qualification"],
            }
        )
    )
