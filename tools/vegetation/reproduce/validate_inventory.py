# /// script
# dependencies = ["numpy>=2.0"]
# ///
"""Normalize inventory evidence and run spatially buffered leave-one-block-out.

Run: uv run truth-data/validate_inventory.py

Parameters below were fixed before viewing benchmark results. This measures
source-specific genus composition inference, not full urban/natural abundance,
species identification, individual crown geometry, or generated-map correctness.
"""

import csv
import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(os.environ["VEGETATION_DATA_DIR"]).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
BLOCK_M = 1000
BUFFER_M = 250
LOCAL_K = 256
LOCAL_RADIUS_M = 5000
MIN_LOCAL = 30
PRIOR_STRENGTH = 50
MIN_TEST = 30
NON_TAXA = {
    "unknown",
    "empty",
    "closed",
    "conifer",
    "dead",
    "scheduled",
    "vacant",
    "stump",
    "--",
}


def normalize(source):
    raw_path = ROOT / f"{source}_raw.geojson"
    raw = json.loads(raw_path.read_text())["features"]
    excluded = Counter()
    records, seen = [], set()
    for feature in raw:
        p = feature["properties"]
        identifier = str(p["ObjectId"] if source == "boston" else p["objectid"])
        if identifier in seen:
            raise ValueError(f"Repeated object id: {source}:{identifier}")
        seen.add(identifier)
        if source == "asheville" and (
            p.get("date_removed") or p.get("lifecyclestatus") not in ("Active", None)
        ):
            excluded["removed_or_inactive"] += 1
            continue
        name = str(p.get("spp_bot" if source == "boston" else "genus") or "").strip()
        first = name.split()[0] if name else ""
        if first.lower() in NON_TAXA or not re.fullmatch(r"[A-Za-z]+", first):
            excluded["unknown_non_tree_site_or_missing_taxon"] += 1
            continue
        geom = feature.get("geometry")
        if not geom or not geom.get("coordinates"):
            excluded["missing_geometry"] += 1
            continue
        lon, lat = geom["coordinates"][:2]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            excluded["invalid_coordinates"] += 1
            continue
        genus = first.capitalize()
        # The Asheville field called genus often contains a whole binomial.
        species = (
            name
            if len(name.split()) > 1
            else " ".join([genus, str(p.get("species") or "")]).strip()
        )
        records.append(
            {
                "id": f"{source}:{identifier}",
                "lon": lon,
                "lat": lat,
                "genus": genus,
                "species": species,
                "source": f"{source}_civic_inventory_20261123",
                "kind": "inventory",
                "growth_form": "tree_inventory_record_not_independent_trait",
                "context": ("park" if p.get("park") else "street")
                if source == "boston"
                else "unspecified_public_inventory",
                "height_raw": p.get("height") if source == "asheville" else None,
                "canopy_height_raw": p.get("canopy_height")
                if source == "asheville"
                else None,
                "dimension_units": "not established; raw values not used"
                if source == "asheville"
                else "no height/crown fields",
            }
        )
    path = ROOT / f"{source}_inventory.json"
    path.write_text(json.dumps(records, separators=(",", ":")))
    with (ROOT / f"{source}_inventory.csv").open("w") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    return records, {
        "raw_rows": len(raw),
        "eligible_rows": len(records),
        "excluded": dict(excluded),
        "genera": len({r["genus"] for r in records}),
        "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "normalized_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def score(q, p):
    mid = (q + p) / 2
    nonzero = q > 0
    js = 0.5 * np.sum(q[nonzero] * np.log2(q[nonzero] / mid[nonzero]))
    js += 0.5 * np.sum(p * np.log2(p / mid))
    return {
        "tvd": float(np.abs(q - p).sum() / 2),
        "js_divergence_bits": float(js),
        "cross_entropy_nats": float(-np.sum(q[nonzero] * np.log(p[nonzero]))),
        "top_genus_correct": int(np.argmax(q) == np.argmax(p)),
    }


def benchmark(source, records):
    center_lat = float(np.median([r["lat"] for r in records]))
    xy = np.array(
        [
            [r["lon"] * 111320 * math.cos(math.radians(center_lat)), r["lat"] * 111320]
            for r in records
        ]
    )
    blocks = np.floor(xy / BLOCK_M).astype(np.int64)
    genera = sorted({r["genus"] for r in records})
    labels = {name: index for index, name in enumerate(genera)}
    y = np.array([labels[r["genus"]] for r in records])
    folds = []
    for block, count in sorted(Counter(map(tuple, blocks)).items()):
        if count < MIN_TEST:
            continue
        test = np.all(blocks == block, axis=1)
        low = np.array(block) * BLOCK_M
        high = low + BLOCK_M
        # Rectangular padded exclusion is stricter than a Euclidean buffer at corners.
        in_padded_block = np.all(
            (xy >= low - BUFFER_M) & (xy <= high + BUFFER_M), axis=1
        )
        train = ~in_padded_block
        if train.sum() < 100:
            continue
        assert not np.any(train & test)
        gap = np.linalg.norm(
            np.maximum(np.maximum(low - xy[train], xy[train] - high), 0), axis=1
        )
        min_gap = float(gap.min())
        assert min_gap >= BUFFER_M - 1e-7, min_gap
        regional_count = np.bincount(y[train], minlength=len(genera)).astype(float)
        regional = (regional_count + 0.5) / (regional_count.sum() + 0.5 * len(genera))
        distance = np.linalg.norm(xy - (low + high) / 2, axis=1)
        candidates = np.flatnonzero(train & (distance <= LOCAL_RADIUS_M))
        nearest = candidates[np.argsort(distance[candidates], kind="stable")[:LOCAL_K]]
        fallback = len(nearest) < MIN_LOCAL
        if fallback:
            local = regional.copy()
        else:
            local_count = np.bincount(y[nearest], minlength=len(genera))
            local = (local_count + PRIOR_STRENGTH * regional) / (
                len(nearest) + PRIOR_STRENGTH
            )
        true_count = np.bincount(y[test], minlength=len(genera))
        truth = true_count / true_count.sum()
        regional_score, local_score = score(truth, regional), score(truth, local)
        folds.append(
            {
                "source": source,
                "block_x": int(block[0]),
                "block_y": int(block[1]),
                "test_n": int(test.sum()),
                "train_n": int(train.sum()),
                "buffer_excluded_n": int(in_padded_block.sum() - test.sum()),
                "min_training_distance_to_test_block_m": min_gap,
                "local_n": len(nearest),
                "fallback": fallback,
                "truth_top_genus": genera[int(np.argmax(truth))],
                "regional_top_genus": genera[int(np.argmax(regional))],
                "local_top_genus": genera[int(np.argmax(local))],
                **{f"regional_{key}": value for key, value in regional_score.items()},
                **{f"local_{key}": value for key, value in local_score.items()},
                "truth_proportions": {
                    genera[i]: float(value)
                    for i, value in enumerate(truth)
                    if value > 0
                },
                "local_proportions": {
                    genera[i]: float(value) for i, value in enumerate(local)
                },
            }
        )
    if not folds:
        raise ValueError("No eligible heldout blocks")
    summary = {
        "heldout_blocks": len(folds),
        "heldout_records": sum(f["test_n"] for f in folds),
        "fallback_blocks": sum(f["fallback"] for f in folds),
        "min_training_gap_m": min(
            f["min_training_distance_to_test_block_m"] for f in folds
        ),
        "local_tvd_wins": sum(f["local_tvd"] < f["regional_tvd"] for f in folds),
    }
    for method in ("regional", "local"):
        summary[method] = {
            key: float(np.mean([f[f"{method}_{key}"] for f in folds]))
            for key in (
                "tvd",
                "js_divergence_bits",
                "cross_entropy_nats",
                "top_genus_correct",
            )
        }
        summary[method]["tree_weighted_cross_entropy_nats"] = float(
            np.average(
                [f[f"{method}_cross_entropy_nats"] for f in folds],
                weights=[f["test_n"] for f in folds],
            )
        )
    # Paired block-bootstrap uncertainty, not a proof of independence between neighboring folds.
    delta = np.array([f["regional_tvd"] - f["local_tvd"] for f in folds])
    rng = np.random.default_rng(1327)
    means = np.array(
        [np.mean(rng.choice(delta, len(delta), replace=True)) for _ in range(2000)]
    )
    summary["mean_tvd_reduction"] = float(delta.mean())
    summary["paired_block_bootstrap_tvd_reduction_95pct_interval"] = list(
        map(float, np.quantile(means, [0.025, 0.975]))
    )
    summary["uncertainty_caveat"] = (
        "Bootstrap resamples withheld blocks, but neighboring blocks and repeated training sets are dependent; interval is descriptive only."
    )
    (ROOT / f"{source}_heldout_blocks.json").write_text(json.dumps(folds, indent=2))
    return summary


def main():
    result = {
        "design": {
            "block_width_m": BLOCK_M,
            "exclusion_buffer_m": BUFFER_M,
            "local_nearest_k": LOCAL_K,
            "local_radius_m": LOCAL_RADIUS_M,
            "min_local_for_nonfallback": MIN_LOCAL,
            "local_regional_prior_strength": PRIOR_STRENGTH,
            "min_heldout_trees_per_block": MIN_TEST,
            "baseline_symmetric_dirichlet_alpha": 0.5,
            "projection": "Fixed equirectangular at city median latitude; absolute global grid origin, metre units",
            "evaluation_unit": "Equal-weight heldout 1km blocks; all source records in heldout block removed plus 250m rectangular buffer; no random-row split",
            "point_location_use": "Only block center is queried; withheld tree locations and labels are not model inputs",
            "parameter_selection": "Fixed before measuring either source; no tuning on heldout results",
        },
        "sources": {},
        "limitations": [
            "Public urban inventories are not complete censuses of all city trees, especially private land, and do not establish natural-forest abundance.",
            "Inventory genus identification and timestamps are trusted source attributes, not independently resurveyed.",
            "Genus is parsed from source botanical labels; no species-level accuracy or synonym reconciliation is claimed.",
            "Folds assess within-source spatial transfer, not independent-source or cross-city generalization.",
            "Raw Asheville height/canopy fields lack established units and are excluded from all geometry claims.",
            "This benchmark is a standalone evidence baseline, not proof that the production vegetation engine uses the same estimator or matches heldout records.",
        ],
    }
    for source in ("boston", "asheville"):
        records, receipt = normalize(source)
        result["sources"][source] = {
            **receipt,
            "benchmark": benchmark(source, records),
            "composition": dict(Counter(r["genus"] for r in records).most_common()),
        }
    (ROOT / "inventory_benchmark.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {name: value["benchmark"] for name, value in result["sources"].items()},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
