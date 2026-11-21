"""Read-only local net-loss accounting; does not attribute physical flux."""

import argparse
import json
from pathlib import Path

from scipy import ndimage

from closed_storage_candidate import sha
from natural_basins import ADJACENCY, lake_components
from natural_storage_candidate import grid
from water_development_result import read_samples


def audit(folder, native):
    construction = json.loads((folder / "natural-plan.json").read_text())
    components, _ = lake_components(json.loads((folder / "geometry.json").read_text()))
    samples = read_samples(native)
    first, second = samples[:2]
    frames = second["water"]["frame"] - first["water"]["frame"]
    start = grid(native / "grids/t000-water.u16")
    end = grid(native / "grids/t005-water.u16")
    bodies = []
    for body in construction["bodies"]:
        if body["status"] != "constructed":
            continue
        mask = components[body["id"]][0]
        rim = ndimage.binary_dilation(mask, ADJACENCY) & ~mask
        losses = start[mask] - end[mask]
        bodies.append(
            {
                "id": body["id"],
                "nodes": int(mask.sum()),
                "initial_depth_range_m": [
                    float(start[mask].min()),
                    float(start[mask].max()),
                ],
                "t005_depth_range_m": [float(end[mask].min()), float(end[mask].max())],
                "node_net_loss_range_m": [float(losses.min()), float(losses.max())],
                "native_node_area_volume_loss_m3": float(losses.sum() * 16**2),
                "mean_node_loss_m_per_water_frame": float(losses.mean() / frames),
                "rim_wet_nodes_start_t005": [
                    int((start[rim] > 0).sum()),
                    int((end[rim] > 0).sum()),
                ],
            }
        )
    inputs = [
        folder / "geometry.json",
        folder / "natural-plan.json",
        native / "timeline.jsonl",
        native / "grids/t000-water.u16",
        native / "grids/t005-water.u16",
        native / "grids/t000-water-ground.u16",
        native / "grids/t005-water-ground.u16",
    ]
    return {
        "schema": "polli.passive-lake-net-loss-audit/1",
        "bodies": bodies,
        "stats_frame_delta": second["stats"]["frame"] - first["stats"]["frame"],
        "water_frame_delta": frames,
        "captured_floor_equal": (native / "grids/t000-water-ground.u16").read_bytes()
        == (native / "grids/t005-water-ground.u16").read_bytes(),
        "inputs_sha256": {str(p): sha(p) for p in inputs},
        "source_sha256": sha(Path(__file__)),
        "volume_convention": "sum node depth times16m squared, same as harness; not integrated physical flux",
        "physical_flux_budget": "unknown",
        "mechanism": "unresolved: no evaporation or cross-boundary flux telemetry",
        "interpretation": "One unsaturated interval in one native run. No exact sink cadence, between-sample no-spill proof, or long-term extrapolation.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("native", type=Path)
    print(json.dumps(audit(**vars(parser.parse_args())), indent=2))
