"""Complete fixed-path wet-gradient summaries; no inferred discharge."""

import argparse
from pathlib import Path

import numpy as np

from bank_authority import ROOT, load, sha, write


def path_summary(head_q, depth_q, velocity):
    wet_pair = (depth_q[:-1] > 6.4) & (depth_q[1:] > 6.4)
    delta = np.diff(head_q.astype(np.int32)) / 64
    valid = np.flatnonzero(wet_pair)
    observed = wet_pair & np.isfinite(velocity[:-1])
    largest = int(valid[np.argmax(delta[valid])]) if valid.size else None
    return {
        "nodes": int(head_q.size),
        "wet_nodes": int(np.count_nonzero(depth_q > 6.4)),
        "wet_pairs": int(valid.size),
        "API_velocity_nodes": int(np.isfinite(velocity).sum()),
        "wet_pairs_with_velocity": int(observed.sum()),
        "velocity_positive_toward_edge": int(
            np.count_nonzero(observed & (velocity[:-1] > 0))
        ),
        "velocity_negative_away_from_edge": int(
            np.count_nonzero(observed & (velocity[:-1] < 0))
        ),
        "velocity_times_head_difference_negative": int(
            np.count_nonzero(observed & (velocity[:-1] * delta < 0))
        ),
        "maximum_wet_pair_head_rise_toward_edge_m": float(delta[largest])
        if largest is not None
        else None,
        "maximum_rise_edge_index": largest,
        "source_H_m": int(head_q[0]) / 64,
        "source_depth_m": int(depth_q[0]) / 64,
        "boundary_H_m": int(head_q[-1]) / 64,
    }


def stage(protocol, output):
    if output.exists():
        raise ValueError("Fresh derived witness output required")
    output.mkdir(parents=True)
    source = protocol / "analysis"
    inputs = {p.name: sha(p) for p in source.iterdir() if p.is_file()}
    write(
        output / "profile-freeze.json",
        {
            "schema": "polli.coastal-corridor-profile-freeze/1",
            "known_basis": "Existing PL-1245 review and boundary-corridor-v1 results, not outcome-blind",
            "input_directory": str(source),
            "files_sha256": inputs,
            "source_sha256": sha(ROOT / "diagnostics/coastal_corridor_profiles.py"),
            "method": "All declared paths; only adjacent wet pairs form gradients; separate static/minimax API projections; unknown velocity is NaN, never zero",
        },
    )
    result = load(source / "result.json")
    paths = load(source / "paths.json")
    shape = tuple(result["route_profile_shape"])
    nodes = np.fromfile(source / "route_nodes.bin", "<i4")
    columns = {int(n): i for i, n in enumerate(nodes)}
    head = np.fromfile(source / "head_q.bin", "<i4").reshape(shape)
    depth = np.fromfile(source / "depth_q.bin", "<i4").reshape(shape)
    velocity = {
        kind: np.fromfile(source / f"{kind}_signed_velocity_api.bin", "<f8").reshape(
            shape
        )
        for kind in ("static", "minimax")
    }
    rows = []
    for feature in paths["features"]:
        feature_rows = []
        for path in feature["paths"]:
            cols = np.array([columns[n] for n in path["nodes"]])
            kind = "static" if path["kind"] == "subsea_shortest" else "minimax"
            summaries = [
                path_summary(h[cols], d[cols], v[cols])
                for h, d, v in zip(head, depth, velocity[kind])
            ]
            feature_rows.append(
                {
                    "source_node": path["source_node"],
                    "kind": path["kind"],
                    "minimum_spill_floor_m": path["minimum_spill_floor_m"],
                    "samples": summaries,
                }
            )
        rows.append(
            {
                "id": feature["id"],
                "name": feature["name"],
                "scope": feature["scope"],
                "paths": feature_rows,
            }
        )
    write(
        output / "profiles.json",
        {
            "profile_freeze_sha256": sha(output / "profile-freeze.json"),
            "times": [s["minute"] for s in result["snapshots"]],
            "features": rows,
            "limits": "Graph directions/conditional minimax paths are not accepted hydraulic connectivity or geographic flow. Signed API velocities are sparse point readbacks, not integrated discharge or a physical source budget.",
        },
    )
    return {
        "freeze_sha256": sha(output / "profile-freeze.json"),
        "profiles_sha256": sha(output / "profiles.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(stage(args.protocol, args.output))
