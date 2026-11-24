"""Build a provenance-bearing supply index and standalone browse page."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics

ROOT = Path(__file__).resolve().parent

# Name-based screening only. These are not species identifications from renders.
NAMES = [
    (r"mangrove", "broadleaf_evergreen", None, [14]),
    (r"bald cypress", "needleleaf_deciduous", "Taxodium", [4]),
    (r"larch", "needleleaf_deciduous", "Larix", [5, 6]),
    (r"\b(?:pine|ponderosa)(?:\b|(?=\d))", "needleleaf_evergreen", "Pinus", [3, 5, 6, 12]),
    (r"spruce", "needleleaf_evergreen", "Picea", [5, 6]),
    (r"douglas fir", "needleleaf_evergreen", "Pseudotsuga", [5]),
    (r"\bfir\b", "needleleaf_evergreen", "Abies", [5, 6]),
    (r"juniper", "needleleaf_evergreen", "Juniperus", [5, 12, 13]),
    (r"cypress", "needleleaf_unknown", None, [4, 5, 12]),
    (r"redcedar|red cedar", "needleleaf_evergreen", None, [5]),
    (r"redwood", "needleleaf_evergreen", None, [5]),
    (r"conifer", "needleleaf_evergreen", None, [5, 6]),
    (r"yew", "needleleaf_evergreen", "Taxus", [4, 5]),
    (r"birch", "broadleaf_deciduous", "Betula", [4, 6]),
    (r"alder", "broadleaf_deciduous", "Alnus", [4, 5]),
    (r"beech", "broadleaf_deciduous", "Fagus", [4]),
    (r"maple", "broadleaf_deciduous", "Acer", [4]),
    (r"live ?oak", "broadleaf_evergreen", "Quercus", [4, 12]),
    (r"oak", "broadleaf_deciduous", "Quercus", [4]),
    (r"cottonwood|poplar", "broadleaf_deciduous", "Populus", [4]),
    (r"linden", "broadleaf_deciduous", "Tilia", [4]),
    (r"chestnut", "broadleaf_deciduous", None, [4]),
    (r"willow", "broadleaf_deciduous", "Salix", [4]),
    (r"eucalyptus|gumtree|gum tree", "broadleaf_evergreen", "Eucalyptus", [1, 2, 12]),
    (r"olive", "broadleaf_evergreen", "Olea", [12]),
    (r"baobab", "broadleaf_deciduous", "Adansonia", [2, 7]),
    (r"umbrella thorn|acacia", "broadleaf_deciduous", None, [2, 7]),
    (r"coconut", "palm", "Cocos", [1, 7]),
    (r"date palm", "palm", "Phoenix", [1, 2, 7]),
    (r"windmill palm", "palm", "Trachycarpus", [1, 4]),
    (r"palm", "palm", None, [1, 2, 7]),
    (r"banana", "large_herb", "Musa", [1]),
    (r"planetree|plane tree|plane street tree", "broadleaf_deciduous", "Platanus", [4]),
    (r"apple", "broadleaf_deciduous", "Malus", [4]),
    (r"pear", "broadleaf_deciduous", "Pyrus", [4]),
    (r"cherry", "broadleaf_deciduous", "Prunus", [4]),
    (r"orange", "broadleaf_evergreen", "Citrus", [1, 12]),
    (r"rhododendron", "shrub", "Rhododendron", [4, 5]),
    (r"lantana", "shrub", "Lantana", [1, 2]),
    (r"bamboo", "grass", None, [1, 4]),
    (r"fern", "fern", None, [1, 4, 5]),
    (r"grass|reed", "grass", None, [7, 8, 9, 10]),
    (r"forb|flower", "herbaceous", None, []),
    (r"cactus|succulent", "succulent", None, [13]),
    (r"bush|shrub|hedge", "shrub", None, []),
    (r"rock|boulder|pebble", "rock", None, []),
]

LATIN_GENERA = {
    "Pinus": ("needleleaf_evergreen", [3, 5, 6, 12]),
    "Picea": ("needleleaf_evergreen", [5, 6]),
    "Abies": ("needleleaf_evergreen", [5, 6]),
    "Larix": ("needleleaf_deciduous", [5, 6]),
    "Taxodium": ("needleleaf_deciduous", [4]),
    "Acer": ("broadleaf_deciduous", [4]),
    "Betula": ("broadleaf_deciduous", [4, 6]),
    "Fagus": ("broadleaf_deciduous", [4]),
    "Alnus": ("broadleaf_deciduous", [4, 5]),
    "Quercus": ("broadleaf_unknown", [4, 12]),
    "Platanus": ("broadleaf_deciduous", [4]),
    "Eucalyptus": ("broadleaf_evergreen", [1, 2, 12]),
}


def classify(name):
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).replace("_", " ").lower()
    for genus, (form, biomes) in LATIN_GENERA.items():
        if re.search(rf"\b{genus}\b", words, re.I):
            return {
                "form": form,
                "genus": genus,
                "biomes": biomes,
                "classification_basis": "genus token in title; species and ecological suitability unverified",
            }
    if "flower tree" in words:
        return {
            "form": "broadleaf_unknown",
            "genus": None,
            "biomes": [],
            "classification_basis": "flowering tree name; leaf persistence and genus unresolved",
        }
    for pattern, form, genus, biomes in NAMES:
        if re.search(pattern, words):
            return {
                "form": form,
                "genus": genus,
                "biomes": biomes,
                "classification_basis": "name-based hypothesis; visual/ecological review pending",
            }
    return {"form": "unknown", "genus": None, "biomes": [], "classification_basis": "unidentified"}


def percentile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def lod_mesh(name):
    return bool(re.search(r"(?:^|[_ .-])lod\d*(?:$|[_ .-])", name, re.I))


def check_frame(path):
    """Reject the observed sky-only frame without modifying native pixels."""
    from PIL import Image

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        pixels = list(rgb.getdata())[::997]
        blue = sum(b > r * 1.25 and b > g * 1.1 for r, g, b in pixels) / len(pixels)
        if blue > 0.9:
            raise ValueError("Native frame is almost entirely blue; no forest rendering established")
        return {
            "width": image.width,
            "height": image.height,
            "blue_pixel_fraction": blue,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }


def frame_summary(samples):
    summary = []
    for size in sorted({s["size"] for s in samples}):
        rows = [s for s in samples if s["size"] == size]
        baseline = [s for s in rows if s["arm"].startswith("A")]
        candidate = [s for s in rows if s["arm"] == "B"]
        repeats, ratios, drift = [], [], []
        for repeat in sorted({s["repeat"] for s in rows}):
            arms = {s["arm"]: s for s in rows if s["repeat"] == repeat}
            if set(arms) != {"A-before", "B", "A-after"}:
                raise ValueError("Incomplete native A/B/A repeat")
            before, after = [percentile(arms[k]["frame_ms"], 0.95) for k in ("A-before", "A-after")]
            ratios.append(percentile(arms["B"]["frame_ms"], 0.95) / ((before + after) / 2) - 1)
            drift.append(abs(after / before - 1))
            repeats.append(repeat)
        populations = {s["instances"] for s in rows}
        if (
            len(populations) != 1
            or 0 in populations
            or any(s["population"]["instances"] != s["instances"] for s in rows)
        ):
            raise ValueError("Native population did not stay fixed")
        if any(
            len(s["frame_ms"]) != 300 or any(not math.isfinite(v) or v <= 0 for v in s["frame_ms"])
            for s in rows
        ):
            raise ValueError("Invalid native frame samples")
        summary.append(
            {
                "zoom": size,
                "repeats": len(repeats),
                "instances": next(iter(populations)),
                "baseline": baseline[0]["name"],
                "candidate": candidate[0]["name"],
                "baseline_p50_ms_median": statistics.median(
                    statistics.median(s["frame_ms"]) for s in baseline
                ),
                "candidate_p50_ms_median": statistics.median(
                    statistics.median(s["frame_ms"]) for s in candidate
                ),
                "baseline_p95_ms_median": statistics.median(
                    percentile(s["frame_ms"], 0.95) for s in baseline
                ),
                "candidate_p95_ms_median": statistics.median(
                    percentile(s["frame_ms"], 0.95) for s in candidate
                ),
                "candidate_p95_run_range_ms": [
                    min(percentile(s["frame_ms"], 0.95) for s in candidate),
                    max(percentile(s["frame_ms"], 0.95) for s in candidate),
                ],
                "paired_p95_regression_median": statistics.median(ratios),
                "max_baseline_drift": max(drift),
                "drift_gate": "inconclusive" if max(drift) > 0.05 else "within_proposed_drift_limit",
                "performance_verdict": "inconclusive_without_limiter_attribution; not an asset certification",
            }
        )
    return summary


def assess(item, budget):
    """Unknown is not a pass. Popularity and declared budgets cannot override QA."""
    failed, unknown = [], []
    if item.get("availability") != "public":
        failed.append("not_public")
    if item.get("required_mods"):
        failed.append("requires_mods")
    if "Mod" in item.get("tags", []):
        failed.append("workshop_item_is_a_mod")
    if item.get("dependency_status") != "public_page_checked":
        unknown.append("dependencies")
    if item.get("unresolved_dependencies"):
        unknown.append("unresolved_dependencies")
    if item.get("dependencies") and item.get("dependency_closure_review") is not True:
        unknown.append("dependency_closure_review")
    packages = item.get("packages", [])
    if not packages:
        unknown.append("package_metrics")
    for package in packages:
        if package["contains_assembly"]:
            failed.append("embedded_code")
        main = [m for m in package["meshes"] if not lod_mesh(m["name"])]
        if not main:
            unknown.append("main_mesh")
        if main and max(m["triangles"] for m in main) > budget["forest_main_triangle_target"]:
            failed.append("over_forest_fill_triangle_target")
        if any(m.get("vertices", 0) > 65536 for m in main):
            failed.append("vertex_limit")
        textures = [
            t for t in package.get("textures", []) if not re.search(r"snapshot|preview", t["name"], re.I)
        ]
        if not textures:
            unknown.append("material_texture_metrics")
        elif any(max(t["width"], t["height"]) > budget["forest_texture_target_px"] for t in textures):
            failed.append("over_forest_fill_texture_target")
    # Frame timing for one reference candidate calibrates the proposed bar. It
    # does not certify every other item, nor does a successful load certify art.
    for field in (
        "scale_review",
        "gameplay_visual_review",
        "billboard_review",
        "maintenance_review",
        "recommendation_rights_review",
    ):
        if item.get(field) is False:
            failed.append(field)
        elif item.get(field) is not True:
            unknown.append(field)
    if item.get("native_frame_review") is not True:
        unknown.append("native_frame_review")
    return {
        "status": "fail" if failed else "unreviewed" if unknown else "pass",
        "failed": sorted(set(failed)),
        "unknown": sorted(set(unknown)),
        "profile": "forest_fill_proposal",
    }


def build(installed, workshop, native, out):
    from installed import natural_prop

    source = json.loads(installed.read_text())
    catalog = json.loads(workshop.read_text())
    native_catalog = (
        json.loads((native / "native-catalog.json").read_text())
        if native and (native / "native-catalog.json").exists()
        else {"trees": []}
    )
    native_by_name = {t["name"]: t for t in native_catalog["trees"]}
    base = []
    excluded = []
    for row in source["base_prefabs"]:
        if row["name"] == "TreeTemplate" or (row["kind"] == "PropInfo" and not natural_prop(row["name"])):
            excluded.append(row["name"])
            continue
        row = dict(row, **classify(row["name"]))
        row["native"] = native_by_name.get(row["name"])
        row["theme"] = (
            "winter variant"
            if "winter" in row["name"].lower()
            else "not yet resolved from prefab loading/theme masks"
        )
        row["height_m"] = row["meshes"][0]["size_m"][1] if row["meshes"] else None
        row["footprint_m"] = [row["meshes"][0]["size_m"][i] for i in (0, 2)] if row["meshes"] else None
        row["dimensions_basis"] = (
            "unscaled serialized mesh bounds; random native scale reported separately when loaded"
        )
        base.append(row)
    winter_by_stem = {
        re.sub("winter", "", b["name"], flags=re.I).casefold(): b["name"]
        for b in base
        if "winter" in b["name"].lower()
    }
    summer_by_stem = {b["name"].casefold(): b["name"] for b in base if "winter" not in b["name"].lower()}
    for row in base:
        winter = "winter" in row["name"].lower()
        stem = re.sub("winter", "", row["name"], flags=re.I).casefold()
        row["season_variant_relation"] = (summer_by_stem if winter else winter_by_stem).get(stem)
        row["season_behavior_basis"] = "Separate named prefab; not a dynamic season/snow observation"
    tree_triangles = [r["meshes"][0]["triangles"] for r in base if r["kind"] == "TreeInfo" and r["meshes"]]
    distribution = {
        "n": len(tree_triangles),
        "includes_separate_winter_variants": True,
        "min": min(tree_triangles),
        "p25": percentile(tree_triangles, 0.25),
        "p50": statistics.median(tree_triangles),
        "p75": percentile(tree_triangles, 0.75),
        "p95": percentile(tree_triangles, 0.95),
        "max": max(tree_triangles),
    }
    bar = {
        "status": "proposal_not_a_certification",
        "forest_main_triangle_target": math.ceil(distribution["p75"] / 100) * 100,
        "main_visible_cost": "main_triangles × simultaneously visible near instances (not total map count)",
        "lod_visible_cost": "native LOD triangles × visible far instances; alpha fill/overdraw must be measured separately",
        "forest_texture_target_px": 1024,
        "palette_estimated_resident_target_mib": 128,
        "texture_budget_basis": "shared per unique texture including mipmaps; never multiply texture memory by instance count",
        "native_p95_regression_target": 0.10,
        "max_baseline_drift_fraction": 0.05,
        "scale_tolerance_fraction": 0.20,
        "scale_basis": "measured crown/height including native random scale versus a sourced real-plant size class",
        "profiles": {
            "forest_fill": "100k–250k map instances; p75-relative main geometry; at least five A/B/A repeats at two zooms",
            "accent": "up to 5k instances; above-target geometry requires its own measured frame budget",
            "specimen": "up to 200; separate review, never silently promoted to forest fill",
        },
    }
    by_id = {}
    for package in source["workshop_packages"]:
        by_id.setdefault(package["workshop_id"], []).append(package)
    items, other = [], []
    for original in catalog["items"]:
        item = dict(original)
        if "Mod" in item.get("tags", []) or (
            "Tree" not in item.get("tags", [])
            and not natural_prop(item.get("title", ""))
            and item["id"] not in by_id
        ):
            other.append(item)
            continue
        item.update(classify(item.get("title", "")))
        item["packages"] = by_id.get(item["id"], [])
        item["native_prefabs"] = [t for t in native_catalog["trees"] if t["name"].split(".")[0] == item["id"]]
        item["assessment"] = assess(item, bar)
        items.append(item)
    biome_data = json.loads((ROOT / "biomes.json").read_text())
    for biome in biome_data["biomes"]:
        matches = [b for b in base if biome["id"] in b["biomes"]]
        forms = sorted({b["form"] for b in matches})
        biome.update(
            base_named_matches=len(matches),
            base_forms=forms,
            coverage="not established"
            if not matches
            else "relatively broad forms"
            if biome["id"] in (4, 5, 6) and all(f in forms for f in biome["forms"]) and len(matches) >= 10
            else "thin",
            workshop_candidates=sum(biome["id"] in w["biomes"] for w in items),
        )
    result = {
        "schema_version": 1,
        "retrieved_utc": catalog["retrieved_utc"],
        "host": source["host"],
        "assembly_sha256": source["assembly_sha256"],
        "scope": catalog["scope"],
        "complete_workshop_census": False,
        "all_dlc_ownership_verified": False,
        "base_prop_scope": "Name-screened candidates, with explicit non-natural exclusions; not a proof of exhaustive vegetation props",
        "excluded_base_candidates": excluded,
        "base_distribution": distribution,
        "quality_bar": bar,
        "biome_scheme": biome_data,
        "base": base,
        "workshop": items,
        "dependency_page_coverage": {
            "candidates": len(items),
            "checked": sum(w.get("dependency_status") == "public_page_checked" for w in items),
            "rate_limited": sum("429" in w.get("page_error", "") for w in items),
        },
        "nonvegetation_discovery_items": other,
        "collections": catalog["collections"],
        "dependency_items": catalog.get("dependency_items", {}),
        "receipts": catalog["receipts"],
        "scan_failures": source["failures"],
        "files_inspected": source["files_inspected"],
        "native": {
            "available": bool(native_catalog["trees"]),
            "instances": native_catalog.get("instances"),
            "sheet_scope": "20 already-installed candidate prefabs; not the globally best 20 Workshop trees",
        },
    }
    if native:
        result["native"]["reference_views"] = [p.name for p in sorted(native.glob("bench-*.png"))]
        for filename, key in [
            ("specimens.json", "specimens"),
            ("frame-samples.json", "frame_samples"),
            ("cleanup.json", "cleanup"),
            ("session-receipt.json", "session_receipt"),
            ("sheet-session-receipt.json", "sheet_session_receipt"),
            ("control.json", "sheet_control"),
            ("environment.json", "environment"),
            ("resources.json", "resource_samples"),
            ("image-sha256.json", "image_hashes"),
        ]:
            path = native / filename
            if path.exists():
                result["native"][key] = json.loads(path.read_text())
        if "frame_samples" in result["native"]:
            result["native"]["frame_summary"] = frame_summary(result["native"].pop("frame_samples"))
        specimens = result["native"].get("specimens", [])
        result["native"]["images_available"] = bool(specimens) and all(
            (native / name).exists() for entry in specimens for name in entry["views"].values()
        )
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "download-shortlist.json", out / "download-shortlist.json")
    shutil.copyfile(ROOT / "REPORT.md", out / "report.md")
    if native:
        for source_image in native.glob("*.png"):
            (out / "native").mkdir(exist_ok=True)
            shutil.copyfile(source_image, out / "native" / source_image.name)
        for entry in result["native"].get("specimens", []):
            for name in entry["views"].values():
                if Path(name).name != name or not name.endswith(".png"):
                    raise ValueError("Invalid native screenshot filename")
    (out / "index.json").write_text(json.dumps(result, indent=2) + "\n")
    template = (ROOT / "shelf.html").read_text()
    # Embed as inert JSON, including when an asset author supplies HTML-like text.
    payload = (
        json.dumps(result).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    )
    (out / "index.html").write_text(template.replace("__CATALOG_JSON__", payload))
    print(
        f"{len(base)} built-in prefabs; {len(items)} Workshop candidates; {len(other)} nonvegetation/dependency records"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--installed", required=True, type=Path)
    p.add_argument("--workshop", required=True, type=Path)
    p.add_argument("--native", type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    build(args.installed, args.workshop, args.native, args.out)
