"""Input-only water-risk measurements, shared by CPython and the browser writer.

No native observations, fixture fingerprints, place names or source IDs enter
these features. Native results are labels only, in the separate calibration tool.
"""

import math

import numpy as np
from scipy import ndimage

SIZE, STEP, HALF = 1081, 16, 8640


def measure(terrain, water, hydro):
    """Measure prepared native-order initial grids and ordinary writer controls."""
    terrain, water = np.asarray(terrain), np.asarray(water)
    if terrain.shape != (SIZE, SIZE) or water.shape != terrain.shape:
        raise ValueError("Water risk needs complete 1081-square initial grids")
    if not np.isfinite(terrain).all() or not np.isfinite(water).all():
        raise ValueError("Water risk inputs contain non-finite values")
    if (
        terrain.min() < 0
        or terrain.max() > 65535
        or water.min() < 0
        or water.max() > 65535
    ):
        raise ValueError("Water risk inputs exceed the encoded grid range")
    ground, depth = terrain.astype(float) / 64, water.astype(float) / 64
    all_wet = depth > 0
    sea = hydro.get("sea_level_m")
    if sea is not None:
        sea = float(sea)
        if not math.isfinite(sea):
            raise ValueError("Invalid sea level")
    at_sea = (
        all_wet & (np.abs(ground + depth - float(sea)) <= 1 / 64)
        if sea is not None
        else np.zeros_like(all_wet)
    )
    edge = np.zeros_like(all_wet)
    edge[0] = edge[-1] = True
    edge[:, 0] = edge[:, -1] = True
    ocean = ndimage.binary_propagation(edge & at_sea, mask=at_sea)
    # Survey complaint #2: land near the actual sea, measured against sea
    # level. A low inland bank must not stand in for a low coastal shoreline.
    coastal_land = (
        ~all_wet & (ndimage.distance_transform_edt(~ocean) <= 4)
        if ocean.any()
        else np.zeros_like(all_wet)
    )
    coastal_freeboard = (
        ground[coastal_land] - math.floor(sea * 64 + 0.5) / 64
        if coastal_land.any()
        else np.array([])
    )
    wet = all_wet & ~ocean
    area = max(int(wet.sum()), 1)
    if all_wet.any():
        distance, nearest = ndimage.distance_transform_edt(
            ~all_wet, return_indices=True
        )
        freeboard = ground - (ground + depth)[tuple(nearest)]
        shore = ~all_wet & (distance <= 4)
        spill = ~all_wet & (distance > 4) & (distance <= 32) & (freeboard < -1.5)
    else:
        freeboard = np.zeros_like(ground)
        shore = spill = np.zeros_like(wet)
    source_list = hydro.get("sources")
    if not isinstance(source_list, list):
        raise ValueError("Water risk needs the generated water controls")
    inlet, exposure = np.zeros_like(wet), np.zeros_like(wet)
    outputs, inputs, input_only, output_only = [], [], 0, 0
    for source in source_list:
        inp = math.floor(float(source["capacity"]) * 65535 + 0.5)
        out = math.floor(
            float(source.get("output_capacity", source["capacity"])) * 65535 + 0.5
        )
        inputs.append(inp)
        outputs.append(out)
        input_only += bool(inp and not out)
        output_only += bool(out and not inp)
        x, _, z = source["position"]
        target = math.floor(float(source["target"]) * 64 + 0.5) / 64
        if not all(math.isfinite(float(v)) for v in [x, z, target]) or not (
            0 <= inp <= 65535 and 0 <= out <= 65535
        ):
            raise ValueError("Invalid generated water control")
        for rate, kind in [(inp if not out else 0, "inlet"), (out, "output")]:
            if not rate:
                continue
            radius = float(np.float32(np.sqrt(np.float32(rate)) * np.float32(0.4) + 10))
            cx, cz = (x + HALF) / STEP, (z + HALF) / STEP
            x0, x1 = (
                max(0, math.floor(cx - radius / STEP)),
                min(SIZE, math.ceil(cx + radius / STEP) + 1),
            )
            z0, z1 = (
                max(0, math.floor(cz - radius / STEP)),
                min(SIZE, math.ceil(cz + radius / STEP) + 1),
            )
            if x0 >= x1 or z0 >= z1:
                continue
            zz, xx = np.mgrid[z0:z1, x0:x1]
            disk = (xx * STEP - HALF - x) ** 2 + (zz * STEP - HALF - z) ** 2 < radius**2
            if kind == "inlet":
                inlet[z0:z1, x0:x1] |= disk
            else:
                # Potential unfilled ground inside an emitter's physical disk,
                # not a claim of simulated flooding or a new flood mask.
                exposure[z0:z1, x0:x1] |= (
                    disk
                    & ~all_wet[z0:z1, x0:x1]
                    & (target - ground[z0:z1, x0:x1] > 1.5)
                )
    gy, gx = np.gradient(ground, STEP)
    width = ndimage.distance_transform_edt(wet) if wet.any() else np.zeros_like(ground)
    river_list = hydro.get("rivers", [])
    lengths = np.asarray([float(r.get("length_m", 0)) for r in river_list])
    total_length = max(float(lengths.sum()), 1)
    profiles = [float(r.get("profile_above_uncarved_m", 0)) for r in river_list]
    return {
        "relief_m": float(np.percentile(ground, 99) - np.percentile(ground, 1)),
        "slope_p95": float(np.percentile(np.hypot(gx, gy), 95)),
        "wet_fraction": float(wet.mean()),
        "ocean_fraction": float(ocean.mean()),
        "coastal_land_km2": float(coastal_land.sum() * STEP**2 / 1e6),
        "coastal_freeboard_p10_m": float(np.percentile(coastal_freeboard, 10))
        if coastal_freeboard.size
        else 0.0,
        "spill_potential_km2": float(spill.sum() * STEP**2 / 1e6),
        "shore_freeboard_p10_m": float(np.percentile(freeboard[shore], 10))
        if shore.any()
        else 0.0,
        "shallow_fraction": float((wet & (depth < 0.125)).sum() / area),
        "thin_fraction": float((wet & (width <= 1)).sum() / area),
        "inlet_wet_fraction": float((inlet & wet).sum() / area),
        "inlet_shallow_fraction": float((inlet & wet & (depth < 0.5)).sum() / area),
        "emitter_exposure_km2": float(exposure.sum() * STEP**2 / 1e6),
        "source_density": float(len(source_list) / (area * STEP**2 / 1e6)),
        "input_output_ratio": float(sum(inputs) / max(sum(outputs), 1)),
        "input_only_fraction": float(input_only / max(len(source_list), 1)),
        "output_only_fraction": float(output_only / max(len(source_list), 1)),
        "bank_limited_fraction": float(
            sum(
                length
                for length, r in zip(lengths, river_list)
                if r.get("bank_limited")
            )
            / total_length
        ),
        "adverse_profile_fraction": float(
            sum(
                length
                for length, r in zip(lengths, river_list)
                if r.get("profile_above_uncarved_m", 0) > 0
            )
            / total_length
        ),
        "unforced_fraction": float(
            sum(
                length
                for length, reach in zip(lengths, river_list)
                if reach.get("unforced_infeasible_stream")
            )
            / total_length
        ),
        "profile_overbank_p95_m": float(np.percentile(profiles, 95))
        if profiles
        else 0.0,
        "sea_present": float(
            hydro.get("sea_level_m") is not None and hydro.get("sea_level_m", 0) > 0
        ),
    }


def feature_description(feature, value):
    descriptions = {
        "relief_m": f"Terrain relief is {value:.0f} m.",
        "slope_p95": f"Steeper terrain slopes reach {value * 100:.0f}%.",
        "wet_fraction": f"Inland water initially covers {value * 100:.1f}% of this square.",
        "ocean_fraction": f"Open-sea water covers {value * 100:.1f}% of this square.",
        "coastal_land_km2": f"{value:.3f} km² of initially dry land lies within 64 m of the sea.",
        "coastal_freeboard_p10_m": f"Lower coastal land sits {abs(value):.1f} m {'below' if value < 0 else 'above'} sea level.",
        "shallow_fraction": f"{value * 100:.0f}% of inland water starts less than 12.5 cm deep.",
        "thin_fraction": f"{value * 100:.0f}% of inland water occupies narrow grid corridors.",
        "inlet_wet_fraction": f"Drainage disks overlap {value * 100:.1f}% of inland water.",
        "inlet_shallow_fraction": f"Drainage disks overlap shallow water across {value * 100:.1f}% of inland water.",
        "emitter_exposure_km2": f"Water sources reach {value:.3f} km² of initially dry low ground.",
        "spill_potential_km2": f"{value:.3f} km² of nearby dry ground lies below the initial water surface.",
        "shore_freeboard_p10_m": f"Lower shores sit {value:.1f} m above nearby initial water.",
        "source_density": f"There are {value:.1f} water controls per km² of inland water.",
        "input_output_ratio": f"Nominal withdrawal capacity is {value:.1f} times supply capacity.",
        "input_only_fraction": f"{value * 100:.0f}% of water controls only withdraw water.",
        "output_only_fraction": f"{value * 100:.0f}% of water controls only supply water.",
        "bank_limited_fraction": f"{value * 100:.0f}% of mapped channel length needs local water-level corrections.",
        "adverse_profile_fraction": f"{value * 100:.0f}% of mapped channel length has an adverse fitted profile.",
        "profile_overbank_p95_m": f"Higher fitted profiles exceed local banks by {value:.1f} m before local-stage correction.",
        "unforced_fraction": f"{value * 100:.0f}% of mapped channel length has no feasible sustained water profile.",
        "sea_present": "This square has open-sea water."
        if value
        else "This square has no open-sea water.",
    }
    return descriptions[feature]


# Global, conservative warning operating points, not native acceptance gates.
# Their retrospective calibration and false alarms are versioned separately.
DEFAULT_RULES = {
    "low_coastal_freeboard_m": 1.5,
    "emitter_exposure_km2": 0.01,
    "bank_limited_fraction": 0.10,
    "input_output_ratio": 2.0,
    "profile_overbank_m": 3.0,
}


def classify(features, rules=DEFAULT_RULES):
    coastal = (
        features["ocean_fraction"] > 0
        and features["coastal_land_km2"] > 0
        and features["coastal_freeboard_p10_m"] < rules["low_coastal_freeboard_m"]
    )
    flood, drying = [], []
    if coastal:
        reason = "Low coastal land can flood."
        detail = feature_description(
            "coastal_freeboard_p10_m", features["coastal_freeboard_p10_m"]
        )
        flood.extend([reason, detail])
    if features["emitter_exposure_km2"] >= rules["emitter_exposure_km2"]:
        flood.append(
            feature_description(
                "emitter_exposure_km2", features["emitter_exposure_km2"]
            )
        )
    if features["bank_limited_fraction"] > rules["bank_limited_fraction"]:
        drying.append(
            feature_description(
                "bank_limited_fraction", features["bank_limited_fraction"]
            )
        )
    if features["input_output_ratio"] > rules["input_output_ratio"]:
        drying.append(
            "Large withdrawal capacity relative to supply; streams may dry out."
        )
    if features["unforced_fraction"] > 0:
        drying.append(
            feature_description("unforced_fraction", features["unforced_fraction"])
        )
    elif features["profile_overbank_p95_m"] > rules["profile_overbank_m"]:
        drying.append(
            "Fitted channel levels exceed the ordinary incision budget; stream continuity needs review."
        )
    return {"flood": flood, "drying": drying}


def assess(terrain, water, hydro, model=None):
    """Screen any square without consulting native data or identity registries."""
    import json
    from pathlib import Path

    if model is None:
        model = json.loads(
            (Path(__file__).parent / "water-risk-model.json").read_text()
        )
    if model.get("schema") != 1 or model.get("version") != "water-risk-v1":
        raise ValueError("Unsupported water-risk model")
    try:
        features = measure(terrain, water, hydro)
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        return {
            "schema": 1,
            "model": model["version"],
            "status": "declined",
            "native_tested": False,
            "reasons": ["The water check could not assess this square's inputs."],
            "detail": str(error),
            "risks": {},
            "features": None,
            "calibration": model["calibration"],
        }
    flags = classify(features, model["rules"])
    outside = [
        f
        for f in model["features"]
        if not model["ranges"][f][0] - 1e-9
        <= features[f]
        <= model["ranges"][f][1] + 1e-9
    ]
    reasons = []
    for kind, entries in flags.items():
        if entries:
            reasons.append(
                "Flooding risk flagged." if kind == "flood" else "Drying risk flagged."
            )
            reasons.extend(entries)
    if outside:
        reasons.append(
            "This square has water/terrain patterns outside the calibration range."
        )
        reasons.extend(feature_description(f, features[f]) for f in outside[:2])
    return {
        "schema": 1,
        "model": model["version"],
        "status": "warning" if reasons else "lower",
        "native_tested": False,
        "risks": {
            kind: {"level": "flagged" if entries else "not_flagged", "reasons": entries}
            for kind, entries in flags.items()
        },
        "reasons": list(dict.fromkeys(reasons)),
        "features": features,
        "outside_calibration": outside,
        "calibration": model["calibration"],
        "scope": "Input-based screen, not a native simulation or a guarantee that every stream stays wet.",
    }
