"""Versioned reference assessment; frozen judge files and receipts are never edited.

Inputs are complete, north-up, co-located grids in source metres. Independent
vector-water rasterization and original source provenance belong in the bound
bundle metadata. No export score participates in reference selection.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt, label

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cs1-harness"))
from cs1_harness import groundtruth as gt  # noqa: E402

POLICY_PATH = Path(__file__).with_name("reference-policy-v1.json")
POLICY = json.loads(POLICY_PATH.read_text())


def grid(value, shape=None):
    value = np.asarray(value)
    if value.ndim != 2 or value.shape[0] != value.shape[1]:
        raise ValueError("Expected a square, north-up grid")
    if shape is not None and value.shape != shape:
        raise ValueError("All grids must cover identical sample points")
    if not np.isfinite(value).all():
        raise ValueError("Incomplete/nonfinite coverage; no point exclusion allowed")
    return value


def scores(game, reference):
    values = {
        name: round(gt.corr(game, turn(reference)), 4)
        for name, turn in gt.TRANSFORMS.items()
    }
    margin = values["as is"] - max(v for k, v in values.items() if k != "as is")
    limits = POLICY["acceptance"]
    return {
        "correlation": values,
        "identity_margin": round(margin, 4),
        "passed": values["as is"] >= limits["minimum_correlation"]
        and margin >= limits["minimum_orientation_margin"],
    }


def alarms(canonical, z13, z14, tile_x, tile_y, policy=POLICY):
    """Reference-only tests: no generated terrain or city identity is read."""
    shape = grid(canonical).shape
    z13, z14, tile_x, tile_y = [grid(a, shape) for a in (z13, z14, tile_x, tile_y)]
    delta = z13 - z14
    rms = float(np.sqrt(np.mean((delta - delta.mean()) ** 2)))
    correlation = gt.corr(z13, z14)
    zoom = policy["zoom_disagreement"]
    zoom_alarm = (
        correlation < zoom["maximum_correlation"]
        and rms >= zoom["minimum_centered_rmse_m"]
    )
    source_delta = z13 - canonical
    source_rms = float(np.sqrt(np.mean((source_delta - source_delta.mean()) ** 2)))
    source_correlation = gt.corr(canonical, z13)
    source_limits = policy.get("canonical_disagreement")
    source_alarm = bool(
        source_limits
        and source_correlation < source_limits["maximum_correlation"]
        and source_rms >= source_limits["minimum_centered_rmse_m"]
    )
    seams = []
    limits = policy["seam"]
    for axis in (0, 1):
        before = (
            (slice(None, -1), slice(None))
            if axis == 0
            else (slice(None), slice(None, -1))
        )
        after = (
            (slice(1, None), slice(None))
            if axis == 0
            else (slice(None), slice(1, None))
        )
        ids = np.stack(
            [tile_x[before], tile_y[before], tile_x[after], tile_y[after]], axis=-1
        )
        changed = (ids[..., 0] != ids[..., 2]) | (ids[..., 1] != ids[..., 3])
        for pair in np.unique(ids[changed], axis=0):
            mask = changed & np.all(ids == pair, axis=-1)
            count = int(mask.sum())
            if count < limits["minimum_pairs"]:
                continue
            jumps = {
                name: float(np.median(np.abs((a[after] - a[before])[mask])))
                for name, a in [("z13", z13), ("z14", z14), ("canonical", canonical)]
            }
            comparison = max(
                jumps["z14"], jumps["canonical"], limits["comparison_floor_m"]
            )
            fired = (
                jumps["z13"] >= limits["minimum_median_jump_m"]
                and jumps["z13"] >= comparison * limits["minimum_jump_ratio"]
            )
            seams.append(
                {
                    "axis": axis,
                    "tile_pair": pair.astype(int).tolist(),
                    "pairs": count,
                    "median_jump_m": jumps,
                    "alarm": bool(fired),
                }
            )
    return {
        "zoom_correlation": correlation,
        "zoom_centered_rmse_m": rms,
        "zoom_alarm": bool(zoom_alarm),
        "canonical_correlation": source_correlation,
        "canonical_centered_rmse_m": source_rms,
        "canonical_alarm": source_alarm,
        "seams": seams,
        "alarm": bool(zoom_alarm or source_alarm or any(row["alarm"] for row in seams)),
    }


def shoreline(mask):
    # Erode both classes with replicated edges: map boundaries are not coasts.
    padded = np.pad(mask, 1, mode="edge")
    edge = ~(binary_erosion(padded) | binary_erosion(~padded))[1:-1, 1:-1]
    edge[[0, -1], :] = False
    edge[:, [0, -1]] = False
    return edge


def coastal_components(mask):
    """Coastal water reaches the square edge; interior ponds are not coast."""
    components, _ = label(mask)
    ids = np.unique(
        np.concatenate(
            [components[0], components[-1], components[:, 0], components[:, -1]]
        )
    )
    return np.isin(components, ids[ids != 0])


def registration(canonical, vector_water, spacing_m, policy=POLICY):
    """Hydro-flattened DEM shore versus independently projected OSM water."""
    shape = grid(canonical).shape
    water = grid(vector_water, shape).astype(bool)
    if not np.isfinite(spacing_m) or spacing_m <= 0:
        raise ValueError("Source sample spacing must be positive")
    limits = policy["registration"]
    bins, counts = np.unique(
        np.rint(canonical / limits["mode_bin_m"]).astype(np.int64), return_counts=True
    )
    level = float(bins[np.argmax(counts)] * limits["mode_bin_m"])
    flat = np.abs(canonical - level) <= limits["water_level_tolerance_m"]
    if limits.get("footprint") == "edge-connected-water-only":
        water, flat = coastal_components(water), coastal_components(flat)
    fractions = {
        "vector_water": float(water.mean()),
        "canonical_flat": float(flat.mean()),
    }
    if any(
        min(v, 1 - v) < limits["minimum_class_fraction"] for v in fractions.values()
    ):
        return {
            "status": "unresolved",
            "reason": "insufficient land/water support",
            "fractions": fractions,
            "level_m": level,
        }
    edges = [shoreline(mask) for mask in (water, flat)]
    if min(int(edge.sum()) for edge in edges) < limits["minimum_shore_cells"]:
        return {
            "status": "unresolved",
            "reason": "insufficient interior shoreline",
            "fractions": fractions,
            "level_m": level,
        }
    distances = (
        np.concatenate(
            [
                distance_transform_edt(~edges[0])[edges[1]],
                distance_transform_edt(~edges[1])[edges[0]],
            ]
        )
        * spacing_m
    )
    agreement = {}
    for name, turn in gt.TRANSFORMS.items():
        moved = turn(flat)
        agreement[name] = float((moved[water].mean() + (~moved[~water]).mean()) / 2)
    identity = agreement["as is"]
    margin = identity - max(v for k, v in agreement.items() if k != "as is")
    median, p90 = np.percentile(distances, [50, 90])
    passed = (
        identity >= limits["minimum_balanced_accuracy"]
        and margin >= limits["minimum_orientation_margin"]
        and median <= limits["maximum_median_shore_distance_m"]
        and p90 <= limits["maximum_p90_shore_distance_m"]
    )
    return {
        "status": "pass" if passed else "unresolved",
        "level_m": level,
        "fractions": fractions,
        "shore_cells": [int(e.sum()) for e in edges],
        "balanced_accuracy": agreement,
        "identity_margin": margin,
        "median_shore_distance_m": float(median),
        "p90_shore_distance_m": float(p90),
    }


def assess(
    canonical,
    z13,
    z14,
    tile_x,
    tile_y,
    vector_water,
    spacing_m,
    game=None,
    terracing=None,
    policy=POLICY,
    canonical_eligible=True,
):
    canonical = grid(canonical)
    for value in (z13, z14, tile_x, tile_y, vector_water):
        grid(value, canonical.shape)
    evidence = alarms(canonical, z13, z14, tile_x, tile_y, policy)
    registered = registration(canonical, vector_water, spacing_m, policy)
    confirmed = (
        evidence["alarm"] and registered["status"] == "pass" and canonical_eligible
    )
    state = (
        "reference_defect"
        if confirmed
        else "unresolved"
        if evidence["alarm"]
        else "no_reference_alarm"
    )
    result = {
        "policy": policy["version"],
        "state": state,
        "defect_evidence": evidence,
        "independent_registration": registered,
        "selected_reference": "canonical_source" if confirmed else "frozen_z13",
        "reference_diagnostic": {
            "canonical_vs_z13": scores(canonical, z13),
            "canonical_vs_z14": scores(canonical, z14),
        },
        "acceptance_limits": policy["acceptance"],
        "water_qualified": False,
        "canonical_reference_eligible": bool(canonical_eligible),
    }
    if game is not None:
        game = grid(game, canonical.shape)
        result["frozen_score"] = scores(game, z13)
        result["canonical_score"] = scores(game, canonical)
        result["z14_contrast"] = scores(game, z14)
        selected = result["canonical_score"] if confirmed else result["frozen_score"]
        result["terracing"] = terracing
        result["accepted"] = bool(
            state != "unresolved"
            and selected["passed"]
            and terracing is not None
            and np.isfinite(terracing)
            and 0 <= terracing <= policy["acceptance"]["maximum_terracing"]
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bundle",
        type=Path,
        help="NPZ complete north-up arrays, metadata JSON string and spacing_m",
    )
    parser.add_argument("output", type=Path, help="New JSON receipt; no overwrite")
    parser.add_argument("--policy-version", choices=["1", "2"], default="1")
    args = parser.parse_args()
    policy_path = POLICY_PATH.with_name(f"reference-policy-v{args.policy_version}.json")
    policy = json.loads(policy_path.read_text())
    with np.load(args.bundle, allow_pickle=False) as bundle:
        keys = [
            "canonical",
            "z13",
            "z14",
            "tile_x",
            "tile_y",
            "vector_water",
            "spacing_m",
        ]
        values = {k: bundle[k] for k in keys}
        values["spacing_m"] = float(values["spacing_m"])
        if "game" in bundle:
            values.update(game=bundle["game"], terracing=float(bundle["terracing"]))
        metadata = json.loads(str(bundle["metadata"]))
        # The caller supplies a source acquisition receipt, not just an array
        # which happens to correlate with its own exported map.
        digest = metadata.get("canonical_file_sha256", "")
        eligible = (
            metadata.get("canonical_reference_kind")
            in {"usgs-3dep-bare-earth", "county-lidar-terrain"}
            and len(digest) == 64
            and all(c in "0123456789abcdef" for c in digest)
        )
        result = assess(**values, policy=policy, canonical_eligible=eligible)
        result["input_metadata"] = metadata
    result["sha256"] = {
        "bundle": hashlib.sha256(args.bundle.read_bytes()).hexdigest(),
        "policy": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "assessor": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
