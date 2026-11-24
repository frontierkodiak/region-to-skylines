"""Default-plan potential, mirrored in place-rules.js; no native service claim."""

import math

DEFAULTS = dict(
    land_yes_fraction=0.57, ore_target=0.052, oil_target=0.027, fertile_target=0.034
)


def measure_place(ground, depth, cover=None):
    import numpy as np

    g, d = np.asarray(ground, dtype=float), np.asarray(depth, dtype=float)
    if g.size != 1081**2 or d.size != 1081**2:
        return None
    g, d = g.reshape(1081, 1081), d.reshape(1081, 1081)
    r, c = np.meshgrid(np.arange(240, 840, 4), np.arange(240, 840, 4), indexing="ij")
    wet = np.minimum.reduce([d[r + y, c + x] for y in range(4) for x in range(4)])
    slope = np.hypot((g[r, c + 1] - g[r, c - 1]) / 32, (g[r + 1, c] - g[r - 1, c]) / 32)
    if not np.isfinite(wet).all() or (wet < 0).any() or not np.isfinite(slope).all():
        return None
    dry = wet < 0.25
    outside = ~((r >= 480) & (r < 600) & (c >= 480) & (c < 600))
    screened = cover is not None and len(cover) == 271**2
    urban = (
        np.asarray(cover).reshape(271, 271)[r // 4, c // 4] == 50
        if screened
        else np.zeros(r.shape, dtype=bool)
    )
    result = {
        k: math.floor(float(v.mean()) * 1e6 + 0.5) / 1e6
        for k, v in dict(
            buildable_fraction=dry & (slope < 0.15),
            dry_fraction=dry,
            resource_fraction=dry & outside,
            farm_fraction=dry & outside & (slope <= 0.12) & ~urban,
        ).items()
    }
    result["urban_screened"] = screened
    return result


def place_decisions(metrics, evidence=None, footprint=None, rules=None):
    rules = rules or DEFAULTS
    evidence = evidence or {}
    footprint = footprint or {}
    valid = isinstance(metrics, dict) and all(
        type(metrics.get(k)) in (int, float)
        and math.isfinite(metrics[k])
        and 0 <= metrics[k] <= 1
        for k in (
            "buildable_fraction",
            "dry_fraction",
            "resource_fraction",
            "farm_fraction",
        )
    )
    fraction = metrics["buildable_fraction"] if valid else None
    land = dict(
        level="maybe"
        if not valid
        else "no"
        if fraction == 0
        else "yes"
        if fraction >= rules["land_yes_fraction"]
        else "maybe",
        reason="stock_relative_buildable_land" if valid else "place_data_unavailable",
        fraction=fraction,
        stock_threshold=rules["land_yes_fraction"],
    )
    details = {}
    for kind in ("ore", "oil", "fertile"):
        share = (
            metrics["farm_fraction" if kind == "fertile" else "resource_fraction"]
            if valid
            else None
        )
        target = rules[kind + "_target"]
        records = (
            kind != "fertile"
            and evidence.get("deposits", {}).get(kind, {}).get("central", 0) > 0
        )
        details[kind] = dict(
            level="maybe"
            if not valid
            else "no"
            if share == 0
            else "yes"
            if share >= target or records
            else "maybe",
            reason="recorded_resource_and_dry_land"
            if records
            else "balanced_plan_space",
            eligible_fraction=share,
            target_fraction=target,
        )
    no_land = valid and metrics["dry_fraction"] == 0
    cover = (
        evidence.get("landcover", {}).get("status") == "available"
        and isinstance(
            evidence["landcover"].get("coverage_of_central_land"), (int, float)
        )
        and evidence["landcover"]["coverage_of_central_land"] >= 0.5
        and isinstance(
            evidence.get("vegetation", {}).get("tree_suitability"), (int, float)
        )
    )
    support = (
        0
        if no_land
        else evidence.get("vegetation", {}).get("tree_suitability")
        if cover
        else None
    )
    details["forest"] = dict(
        level="no"
        if no_land
        else "maybe"
        if not cover
        else "yes"
        if support > 0
        else "no",
        reason="no_dry_land"
        if no_land
        else "existing_forest_resource_support"
        if cover
        else "forest_evidence_unavailable",
        suitability=support,
    )
    values = [v["level"] for v in details.values()]
    resources = dict(
        level="yes"
        if "yes" in values
        else "no"
        if all(v == "no" for v in values)
        else "maybe",
        reason="default_resource_plan",
        details=details,
    )
    candidate = footprint.get("footprint") == "candidate"
    miss = footprint.get("reason") == "no_footprint_in_finite_search"
    start = dict(
        level="yes" if candidate else "no" if miss else "maybe",
        reason="dry_flat_384m_footprint"
        if candidate
        else "no_sampled_384m_footprint"
        if miss
        else "footprint_data_unavailable",
        footprint_m=[384, 384],
        hookup="unknown",
        search="central_1920m_square_64m_centers",
    )
    return dict(buildable=land, resources=resources, start_footprint=start)
