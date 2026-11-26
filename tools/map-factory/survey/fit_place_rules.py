"""Retrospective stock fit for place-promise rules (PL-1119).

Reads the shipped CS1 map corpus directly with the existing survey decoders:
`read_any` for package formats 4..12, `parse_metadata`, `parse_terrain`,
`parse_water` and `parse_resources`. CO.crp, the blank editor system package, is
excluded; the remaining 104 packages must carry metadata ``builtin == 1``.

The split is deterministic and label-blind: filenames are sorted by
SHA256("PL1119-place-v1:" + filename); the first 21 are held out and the other
83 train the land threshold. No threshold is fitted on the held-out names.

Stock grid orientation: `measure_maps.parse_terrain` and `parse_water` decode the
native 1081-square south-first grid (row 0 is south, as documented in
survey/README.md and START_CAPABILITIES.md). Start-model prepared inputs use the
same order. The exhaustive footprint test below is orientation-agnostic: a
north/south or east/west flip preserves the set of 384 m patches that fit.

usage: python fit_place_rules.py MAPS_DIR OUT.json
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]

import place_rules  # noqa: E402
from start_model import dry_centers  # noqa: E402
from survey.measure_maps import (  # noqa: E402
    CENTRAL,
    data_version,
    parse_metadata,
    parse_resources,
    parse_terrain,
    parse_water,
    read_any,
)

SPLIT_SALT = "PL1119-place-v1:"
EXPECTED_MAPS = 104
HELDOUT_MAPS = 21

GRID = 1081
SPACING = 16
HALF = 8640

FOOTPRINT_HALF_M = 192
MAX_DEPTH_M = 0.1
MAX_SLOPE = 0.15
MAX_RELIEF_M = 8.0
CENTRAL_SQUARE_HALF_M = 960
BORDER_MARGIN_M = 32
CENTER_STEP_M = 64

CONNECTION_FIELDS = {
    "road": "incomingRoads",
    "rail": "incomingTrainTracks",
    "ship": "incomingShipPath",
    "air": "incomingPlanePath",
}
RESOURCE_KEYS = {
    "ore": "central_ore",
    "oil": "central_oil",
    "fertile": "central_fertility",
}
SHIP_WIDTH_M = 256
SPLIT_METHOD = (
    "Sort SHA256('PL1119-place-v1:' + filename) ascending; first 21 are held "
    "out, remaining 83 train; fixed before fitting."
)


def sha_name(name):
    return hashlib.sha256((SPLIT_SALT + name).encode("utf-8")).hexdigest()


def split_names(names):
    """Hash-ordered first 21 test / remaining 83 train; no labels consulted."""
    ordered = sorted(names, key=sha_name)
    return ordered[:HELDOUT_MAPS], ordered[HELDOUT_MAPS:]


def _plain(value):
    """JSON-safe scalar/container conversion (no proprietary bytes included)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def incoming_counts(meta):
    counts = {}
    for kind, field in CONNECTION_FIELDS.items():
        value = meta.get(field)
        counts[kind] = int(value) if isinstance(value, (int, float)) else None
    return counts


def start_exhaustive(ground, depth):
    """Every 16 m center in the central 1920 m square, 32 m border margin.

    A center passes when the 25x25 node patch (384 m) is entirely dry
    (<= 0.1 m), has slope <= 15% at every node, and relief <= 8 m. This is a
    terrain/water geometry test only: no legal native placement, road, hookup or
    service claim. Empty-graph start_model.dry_centers is compared separately.
    """
    dz, dx = np.gradient(ground, SPACING)
    dry = (depth <= MAX_DEPTH_M) & (np.hypot(dx, dz) <= MAX_SLOPE)
    width = 2 * int(np.ceil(FOOTPRINT_HALF_M / SPACING)) + 1
    clear = ndimage.minimum_filter(dry, size=width, mode="constant", cval=0)
    relief = ndimage.maximum_filter(ground, size=width) - ndimage.minimum_filter(
        ground, size=width
    )
    clear &= relief <= MAX_RELIEF_M

    margin = CENTRAL_SQUARE_HALF_M - FOOTPRINT_HALF_M - BORDER_MARGIN_M
    offsets = np.arange(-margin, margin + 1, SPACING)
    rows = np.rint((offsets + HALF) / SPACING).astype(int)
    cols = rows
    hits = clear[np.ix_(rows, cols)]
    centers = {
        (float(x), float(z))
        for z_i, z in enumerate(offsets)
        for x_i, x in enumerate(offsets)
        if hits[z_i, x_i]
    }
    return {"present": bool(centers), "centers": len(centers), "set": centers}


def measure_stock(path):
    """Decode one shipped .crp; raise ValueError for exclusions or bad input."""
    package, assets = read_any(path.read_bytes())
    fmt = package.get("format")
    if not isinstance(fmt, int) or not 4 <= fmt <= 12:
        raise ValueError(f"package format {fmt!r} outside 4..12")
    metadata = parse_metadata(
        next(asset["payload"] for asset in assets if asset["kind"] == 100)
    )
    if metadata.get("builtin") != 1:
        raise ValueError("metadata builtin != 1")
    simulation = next(asset for asset in assets if asset["kind"] == 52)
    data = simulation["payload"]
    version = data_version(data)
    ground = parse_terrain(data)
    depth = parse_water(data)
    if ground.shape != (GRID, GRID) or depth.shape != (GRID, GRID):
        raise ValueError("terrain/water grid is not 1081x1081")

    resources, _ = parse_resources(data, version)
    central = {
        "ore": int(resources["ore"][CENTRAL].sum()),
        "oil": int(resources["oil"][CENTRAL].sum()),
        "fertility": int(resources["fertility"][CENTRAL].sum()),
    }
    metrics = place_rules.measure_place(np.flipud(ground), np.flipud(depth))

    start_reference = start_exhaustive(ground, depth)
    finite = dry_centers(ground, depth, {"nodes": [], "edges": []}, 12)
    finite_set = {(float(center[0]), float(center[1])) for center in finite}
    missing_from_reference = len(finite_set - start_reference["set"])
    start_reference.pop("set")

    return {
        "package_format": fmt,
        "data_version": int(version),
        "geometry": metrics,
        "native": {
            "buildable_area": metadata.get("buildableArea"),
            "central_ore": central["ore"],
            "central_oil": central["oil"],
            "central_fertility": central["fertility"],
            "incoming": incoming_counts(metadata),
        },
        "start": {
            "footprint": start_reference["present"],
            "exhaustive16m_footprint": start_reference["present"],
            "exhaustive16m_centers": start_reference["centers"],
            "finite64m_footprint": bool(finite_set),
            "finite64m_centers": len(finite_set),
            "finite64m_centers_outside_reference": missing_from_reference,
        },
    }


def load_connection_rows(path):
    payload = json.loads(Path(path).read_text())
    return payload, {row["file"]: row for row in payload["rows"]}


def land_label(area, p25):
    if area == 0:
        return "no"
    if area >= p25:
        return "yes"
    return "maybe"


def predicted_land_label(fraction, threshold):
    if fraction is None:
        return "maybe"
    if fraction == 0:
        return "no"
    if fraction >= threshold:
        return "yes"
    return "maybe"


def fit_land_threshold(rows):
    """Maximum balanced accuracy for native buildableArea >= train p25.

    Candidate thresholds are 0.01..0.99 in 0.01 steps on geometry
    buildable_fraction. Ties keep the smaller threshold. The p25 uses every
    training map with native buildableArea; fitting uses the rows that also
    have geometry. Returns None if the training rows lack both classes.
    """
    native_rows = [
        row
        for row in rows
        if isinstance(row.get("native", {}).get("buildable_area"), (int, float))
    ]
    if not native_rows:
        return None
    areas = np.asarray(
        [row["native"]["buildable_area"] for row in native_rows], dtype=float
    )
    p25 = float(np.percentile(areas, 25, method="linear"))
    usable = [
        row
        for row in native_rows
        if isinstance(row.get("geometry", {}), dict)
        and isinstance(row["geometry"].get("buildable_fraction"), (int, float))
    ]
    if not usable:
        return {"threshold": None, "native_p25_percent": p25, "usable": 0}
    usable_areas = np.asarray(
        [row["native"]["buildable_area"] for row in usable], dtype=float
    )
    positive = usable_areas >= p25
    if positive.all() or not positive.any():
        return {
            "threshold": None,
            "native_p25_percent": p25,
            "usable": len(usable),
            "native_maps": len(native_rows),
        }

    best_score, best_threshold = -1.0, None
    for step in range(1, 100):
        threshold = step / 100
        predicted = np.asarray(
            [row["geometry"]["buildable_fraction"] >= threshold for row in usable],
            dtype=bool,
        )
        tp = int((predicted & positive).sum())
        tn = int((~predicted & ~positive).sum())
        sensitivity = tp / int(positive.sum())
        specificity = tn / int((~positive).sum())
        score = (sensitivity + specificity) / 2
        if score > best_score + 1e-15:
            best_score, best_threshold = score, threshold
    return {
        "threshold": best_threshold,
        "native_p25_percent": p25,
        "usable": len(usable),
        "native_maps": len(native_rows),
        "balanced_accuracy": best_score,
        "positives": int(positive.sum()),
        "negatives": int((~positive).sum()),
    }


def land_evaluation(rows, p25, threshold):
    """Three-way agreement counts for one split."""
    if threshold is None:
        return {
            "agree": 0,
            "total": 0,
            "counts": {},
            "native_label_counts": {},
            "predicted_label_counts": {},
        }
    agree = total = 0
    counts = {}
    native_labels = {"yes": 0, "maybe": 0, "no": 0}
    predicted_labels = {"yes": 0, "maybe": 0, "no": 0}
    for row in rows:
        area = row.get("native", {}).get("buildable_area")
        fraction = (
            row.get("geometry", {}).get("buildable_fraction")
            if isinstance(row.get("geometry"), dict)
            else None
        )
        if not isinstance(area, (int, float)) or fraction is None:
            continue
        truth = land_label(area, p25)
        predicted = predicted_land_label(fraction, threshold)
        counts.setdefault(truth, {}).setdefault(predicted, 0)
        counts[truth][predicted] += 1
        native_labels[truth] += 1
        predicted_labels[predicted] += 1
        total += 1
        agree += int(truth == predicted)
    return {
        "agree": agree,
        "total": total,
        "fraction": agree / total if total else None,
        "counts": counts,
        "native_label_counts": native_labels,
        "predicted_label_counts": predicted_labels,
    }


def resource_prediction(metrics, rules):
    decisions = place_rules.place_decisions(metrics, rules=rules)
    details = decisions["resources"]["details"]
    kinds = {
        kind: {
            "predicted_level": details[kind]["level"],
            "eligible_fraction": details[kind].get("eligible_fraction"),
            "target_fraction": details[kind].get("target_fraction"),
        }
        for kind in ("ore", "oil", "fertile")
    }
    return {
        "predicted": any(item["predicted_level"] == "yes" for item in kinds.values()),
        "details": kinds,
    }


def resource_evaluation(rows):
    result = {"aggregate": {}, "per_resource": {}}
    for split, split_rows in rows.items():
        aggregate = {"agree": 0, "total": 0, "confusion": {}}
        per_kind = {
            kind: {
                "predicted_yes": 0,
                "native_yes": 0,
                "predicted_yes_native_yes": 0,
                "predicted_yes_native_no": 0,
                "predicted_no_native_yes": 0,
                "predicted_no_native_no": 0,
                "total": 0,
            }
            for kind in ("ore", "oil", "fertile")
        }
        for row in split_rows:
            resources = row.get("resources")
            if not isinstance(resources, dict):
                continue
            details = resources.get("details", {})
            if "predicted" not in resources:
                continue
            predicted_any = bool(resources["predicted"])
            native_any = bool(resources.get("native_present"))
            aggregate["total"] += 1
            aggregate["agree"] += int(predicted_any == native_any)
            key = f"{'yes' if predicted_any else 'no'}_{'yes' if native_any else 'no'}"
            aggregate["confusion"][key] = aggregate["confusion"].get(key, 0) + 1
            for kind in ("ore", "oil", "fertile"):
                native = bool(details.get(kind, {}).get("native_present"))
                predicted = details.get(kind, {}).get("predicted_level") == "yes"
                bucket = per_kind[kind]
                bucket["total"] += 1
                bucket["native_yes"] += int(native)
                bucket["predicted_yes"] += int(predicted)
                if predicted and native:
                    bucket["predicted_yes_native_yes"] += 1
                elif predicted:
                    bucket["predicted_yes_native_no"] += 1
                elif native:
                    bucket["predicted_no_native_yes"] += 1
                else:
                    bucket["predicted_no_native_no"] += 1
        aggregate["fraction"] = (
            aggregate["agree"] / aggregate["total"] if aggregate["total"] else None
        )
        result["aggregate"][split] = aggregate
        result["per_resource"][split] = per_kind
    return result


def start_evaluation(rows):
    result = {}
    for split, split_rows in rows.items():
        agree = total = 0
        outside = 0
        for row in split_rows:
            start = row.get("start")
            if not isinstance(start, dict):
                continue
            total += 1
            agree += int(
                bool(start.get("exhaustive16m_footprint"))
                == bool(start.get("finite64m_footprint"))
            )
            outside += int(start.get("finite64m_centers_outside_reference", 0))
        result[split] = {
            "agree": agree,
            "total": total,
            "fraction": agree / total if total else None,
            "finite64m_centers_outside_reference": outside,
        }
    return result


def connection_evaluation(split_names, fit_rows):
    result = {}
    for split, names in split_names.items():
        result[split] = {}
        for kind in ("road", "rail", "ship", "air"):
            agree = total = skipped = 0
            for name in names:
                fit = fit_rows.get(name)
                if fit is None or kind not in fit.get("labels", {}):
                    skipped += 1
                    continue
                if kind == "ship":
                    width = fit.get("width_m")
                    predicted = width is not None and width >= SHIP_WIDTH_M
                elif kind == "air":
                    predicted = True  # writer guarantee; stock baseline only
                else:
                    predicted = fit.get(kind)
                    if not isinstance(predicted, bool):
                        skipped += 1
                        continue
                total += 1
                agree += int(predicted == bool(fit["labels"][kind]))
            result[split][kind] = {
                "agree": agree,
                "total": total,
                "fraction": agree / total if total else None,
                "skipped": skipped,
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("maps", type=Path, help="directory of shipped .crp maps")
    parser.add_argument("output", type=Path, help="output JSON path")
    args = parser.parse_args()

    if not hasattr(place_rules, "DEFAULTS") or not isinstance(
        place_rules.DEFAULTS, dict
    ):
        raise SystemExit("place_rules.DEFAULTS is missing or not a dict")
    defaults = dict(place_rules.DEFAULTS)

    files = sorted(path for path in args.maps.glob("*.crp") if path.name != "CO.crp")
    if len(files) != EXPECTED_MAPS:
        raise SystemExit(
            f"expected {EXPECTED_MAPS} builtin maps after excluding CO.crp, "
            f"found {len(files)} in {args.maps}"
        )

    # The partition is fixed from filenames before any map is decoded or fitted.
    test_names, train_names = split_names([path.name for path in files])

    split_of = {name: "test" for name in test_names}
    split_of.update({name: "train" for name in train_names})

    measured = {}
    errors = {}
    for path in files:
        try:
            measured[path.name] = measure_stock(path)
        except Exception as error:  # one bad package should not hide the corpus
            errors[path.name] = f"{type(error).__name__}: {error}"
            print(path.name, errors[path.name], file=sys.stderr, flush=True)

    fit_payload, connection_rows = load_connection_rows(HERE / "connection-fit.json")
    missing_connections = sorted(set(split_of) - set(connection_rows))
    extra_connections = sorted(set(connection_rows) - set(split_of))
    if missing_connections or extra_connections:
        raise SystemExit(
            "connection-fit.json filename mismatch: "
            f"missing={missing_connections[:5]} extra={extra_connections[:5]}"
        )

    # Merge stock measurements, native resource presence and connection rows.
    all_rows = []
    for name in sorted(split_of):
        fit = connection_rows[name]
        row = {
            "file": name,
            "split": split_of[name],
            "connection": {
                "width_m": fit.get("width_m"),
                "labels": fit.get("labels", {}),
                "road_edge": fit.get("road"),
                "rail_edge": fit.get("rail"),
                "ship_fixed256": fit.get("width_m") is not None
                and fit["width_m"] >= SHIP_WIDTH_M,
                "air_writer": True,
                "network_unavailable": fit.get("network_unavailable"),
            },
        }
        if name in measured:
            stock = measured[name]
            geometry = stock["geometry"]
            native = stock["native"]
            areas = [
                native.get(RESOURCE_KEYS[kind], 0) for kind in ("ore", "oil", "fertile")
            ]
            row.update(stock)
            row["resources"] = {
                "native_present": any(value > 0 for value in areas),
                "details": {
                    kind: {
                        "native_amount": native.get(RESOURCE_KEYS[kind], 0),
                        "native_present": bool(native.get(RESOURCE_KEYS[kind], 0) > 0),
                    }
                    for kind in ("ore", "oil", "fertile")
                },
            }
            if isinstance(geometry, dict):
                decision = resource_prediction(geometry, defaults)
                row["resources"]["predicted"] = decision["predicted"]
                for kind, detail in decision["details"].items():
                    row["resources"]["details"][kind].update(detail)
        else:
            row["error"] = errors.get(name, "not measured")
        all_rows.append(row)

    train_rows = [row for row in all_rows if row["split"] == "train"]
    test_rows = [row for row in all_rows if row["split"] == "test"]

    land_fit = fit_land_threshold(train_rows)
    if land_fit is None or land_fit.get("threshold") is None:
        raise SystemExit(f"cannot fit land threshold: {land_fit}")
    threshold = land_fit["threshold"]
    p25 = land_fit["native_p25_percent"]

    for row in all_rows:
        area = row.get("native", {}).get("buildable_area")
        fraction = (
            row.get("geometry", {}).get("buildable_fraction")
            if isinstance(row.get("geometry"), dict)
            else None
        )
        if isinstance(area, (int, float)) and fraction is not None:
            row["land"] = {
                "truth": land_label(area, p25),
                "predicted": predicted_land_label(fraction, threshold),
                "geometry_fraction": fraction,
            }

    land_summary = {
        "threshold": threshold,
        "native_p25_percent": p25,
        "candidate_grid": "0.01..0.99 step 0.01",
        "fit_rule": "maximum balanced accuracy; tie keeps smaller threshold",
        "binary_fit_labels": (
            "positive = geometry buildable_fraction >= threshold and native "
            "buildableArea >= train p25; all other outcomes count negative"
        ),
        "fit": land_fit,
        "train": land_evaluation(train_rows, p25, threshold),
        "heldout": land_evaluation(test_rows, p25, threshold),
    }

    resource_summary = resource_evaluation({"train": train_rows, "heldout": test_rows})
    start_summary = start_evaluation({"train": train_rows, "heldout": test_rows})
    connection_summary = connection_evaluation(
        {"train": train_names, "heldout": test_names}, connection_rows
    )

    rules = dict(defaults)
    rules.update(
        {
            "land_yes_fraction": threshold,
            "connection_ship_width_m": SHIP_WIDTH_M,
            "connection_fit_rules": fit_payload.get("rules"),
            "start": {
                "footprint_m": [384, 384],
                "max_depth_m": MAX_DEPTH_M,
                "max_slope": MAX_SLOPE,
                "max_relief_m": MAX_RELIEF_M,
                "central_square_m": 2 * CENTRAL_SQUARE_HALF_M,
                "border_margin_m": BORDER_MARGIN_M,
                "exhaustive_center_step_m": SPACING,
                "finite_center_step_m": CENTER_STEP_M,
            },
        }
    )

    result = {
        "schema": 1,
        "study": {
            "title": "PL-1119 place-promise stock fit",
            "corpus": "104 shipped CS1 maps (builtin=1, CO.crp excluded), package formats 4..12",
            "retrospective_partition": True,
            "new_unseen_game_evidence": False,
            "blind_prospective_validation": False,
            "thresholds_fitted_on_test": False,
            "forest_model": "not fitted here; remains another owner's Trees model",
            "scalar_output_only": True,
            "measured_maps": len(measured),
            "measurement_errors": errors,
            "split_salt": SPLIT_SALT,
            "split_method": SPLIT_METHOD,
        },
        "rules": rules,
        "parent_defaults": defaults,
        "split": {
            "method": SPLIT_METHOD,
            "salt": SPLIT_SALT,
            "test": test_names,
            "train": train_names,
            "counts": {"test": len(test_names), "train": len(train_names)},
        },
        "summary": {
            "land": land_summary,
            "resources": resource_summary,
            "start": start_summary,
            "connections": connection_summary,
        },
        "rows": all_rows,
        "limitations": [
            "Retrospective partition of the already surveyed 104-map stock corpus; not new unseen game evidence and not a blind prospective validation.",
            "The filename hash split was fixed before fitting and no threshold uses held-out rows; held-out counts are descriptive, not a sealed prospective test.",
            "Native land truth is the editor metadata buildableArea percentage (0..100), not a measured legal-buildability field; the below-train-p25 'maybe' band is a model convention, and predicted land is no at 0, yes above the fitted geometry threshold, else maybe.",
            "Geometry land and resource fractions come from place_rules.measure_place over the central 25 tiles; resource eligible space excludes the central 1920 m square, so these are stock-relative terrain measures, not native service outcomes.",
            "Resource aggregate truth is any positive central native ore, oil or fertility amount; predictions use the parent's current placeDecisions default-balanced targets. Per-resource binary counts treat a predicted 'maybe' as not-yes. Forest is deliberately excluded and remains another owner's Trees model; no forest agreement is invented.",
            "Start footprint is the existence of a 384x384 m patch whose 16 m nodes are dry <=0.1 m, slope <=15% and relief <=8 m inside the central 1920 m square with a 32 m border margin. It is exact geometry, not legal native placement, a start tile, a road hookup or a service guarantee; the comparison uses an empty graph and tile 12.",
            "Stock grids decode south-first (row 0 south). Land/resource measurements flip north-up to match capture sampling; the footprint existence test uses the original south-first grid.",
            "Connection ship predictions use the fixed 256 m mapped-water width rule; road and rail use the existing discrete edge predicates and are skipped where the decoder is unavailable. Air=alwaysYes is the current writer guarantee and this stock comparison is only a baseline.",
            "Rows contain scalar labels and predictions only; no CRP bytes, images or proprietary payloads.",
            "Stock maps have no matched WorldCover urban mask; live fertile-space estimates exclude captured built-up cover where it is available.",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as handle:
        json.dump(_plain(result), handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(all_rows),
                "errors": len(errors),
                "land_threshold": threshold,
                "land_train": land_summary["train"]["agree"],
                "land_heldout": land_summary["heldout"]["agree"],
            }
        )
    )


if __name__ == "__main__":
    main()
