"""Join per-prefab measurements and explicit human-readable review evidence.

Near-art grades never become timing, ecological, size-class or full-bar passes.
"""

import hashlib
import json
from pathlib import Path

from assemble import classify
from installed import prefab_collisions


def resident_bytes(texture):
    """Serialized compression estimate, full mip chain; not measured VRAM."""
    encoding = texture.get("encoding", "")
    width, height = texture["width"], texture["height"]
    if encoding not in ("DXT1", "DXT5", "RGBA32", "RGB24"):
        return None
    total = 0
    while True:
        if encoding.startswith("DXT"):
            total += max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * (8 if encoding == "DXT1" else 16)
        else:
            total += width * height * (4 if encoding == "RGBA32" else 3)
        if width == height == 1:
            return total
        width, height = max(1, width // 2), max(1, height // 2)


def palette_estimate(prefabs):
    textures = {}
    for prefab in prefabs:
        for texture in prefab.get("textures", []):
            checksum = texture.get("checksum")
            key = checksum or (prefab["name"], texture.get("asset_name", texture.get("name")))
            textures[key] = texture
    sizes = [resident_bytes(t) for t in textures.values()]
    return {
        "unique_texture_count": len(textures),
        "known_compressed_mip_bytes": sum(s for s in sizes if s is not None),
        "unknown_format_count": sum(s is None for s in sizes),
        "basis": "Deduplicated serialized content checksum; full mip estimate, not measured resident VRAM or native sharing proof",
    }


def add_reviews(result, source, directory):
    directory = Path(directory)
    reviews = json.loads((directory / "near-reviews.json").read_text())
    by_review = {r["prefab"]: r for r in reviews["reviews"]}
    multi_path = directory / "multi-view-reviews.json"
    multi = json.loads(multi_path.read_text()) if multi_path.exists() else {"reviews": []}
    by_multi = {r["prefab"]: r for r in multi["reviews"]}
    load_gap_path = directory / "load-gaps.json"
    load_gaps = json.loads(load_gap_path.read_text()) if load_gap_path.exists() else {}
    native, runs, captures = {}, [], {}
    for run in sorted((directory / "runs").iterdir()):
        file = run / "native-catalog.json"
        if not file.exists():
            continue
        catalog = json.loads(file.read_text())
        for folder in ("overview", "props"):
            listing = run / folder / "specimens.json"
            if listing.exists():
                for row in json.loads(listing.read_text()):
                    captures[run.name, row["candidate"]] = row
        build_path = run / "build-at-launch.json"
        if not build_path.exists():
            build_path = run / "build.json"
        build = json.loads(build_path.read_text())
        if build["game_assemblies"]["Assembly-CSharp.dll"] != result["assembly_sha256"]:
            raise ValueError(f"Wrong game assembly in {run.name}")
        receipt_path = run / "session-receipt.json"
        receipt = {}
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt["mod_sha256"] != build["dll_sha256"]:
                raise ValueError(f"Loaded mod differs from build receipt in {run.name}")
        for row in catalog["trees"] + catalog.get("props", []):
            native[row["name"]] = {**row, "source_run": run.name}
        runs.append(
            {
                "run": run.name,
                "catalog_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "cleanup": json.loads((run / "cleanup.json").read_text())
                if (run / "cleanup.json").exists()
                else receipt.get("cleanup"),
            }
        )
    collisions = prefab_collisions(source["workshop_packages"])
    bad_items = {p["workshop_id"] for packages in collisions.values() for p in packages}
    workshop = {w["id"]: w for w in result["workshop"]}
    rows = {}
    for package in source["workshop_packages"]:
        iid = package["workshop_id"]
        for prefab in package.get("prefabs", []):
            if prefab.get("kind") not in ("TreeInfo", "PropInfo"):
                continue
            name = package["name"] + "." + prefab["name"]
            key = prefab["kind"] + ":" + name
            if key not in rows:
                item = workshop.get(iid, {})
                measured = native.get(name)
                review = by_review.get(name)
                near_capture = captures.get((review["source_run"], name)) if review else None
                multi_review = by_multi.get(name)
                traits = classify(prefab["name"])
                if traits["form"] == "unknown":
                    traits = classify(item.get("title", prefab["name"]))
                meshes, textures = prefab.get("meshes", []), prefab.get("textures", [])
                serialized_max = max((m["triangles"] for m in meshes), default=None)
                tri = (measured.get("main") or {}).get("triangles") if measured else None
                size = meshes[0].get("size_m") if meshes else None
                oversized = any(
                    max(t["width"], t["height"]) > result["quality_bar"]["forest_texture_target_px"]
                    for t in textures
                )
                score = review["near_art_score_0_to_4"] if review else None
                gates = {
                    "geometry": "unknown"
                    if tri is None
                    else "fail"
                    if tri > result["quality_bar"]["forest_main_triangle_target"]
                    else "pass",
                    "textures": "unknown" if not textures else "fail" if oversized else "pass",
                    "dependencies": "unknown"
                    if item.get("unresolved_dependencies") or item.get("dependencies") is None
                    else "fail"
                    if item.get("required_mods")
                    else "pass",
                    "native_load": "fail" if iid in bad_items else "pass" if measured else "unknown",
                    "near_art": "unknown"
                    if score is None
                    else "pass"
                    if score >= 3
                    else "limited"
                    if score == 2
                    else "fail",
                    "scale_accuracy": "unknown",
                    "gameplay_art": "unknown",
                    "billboard": "unknown",
                    "wind": "unknown",
                    "snow": "unknown",
                    "save_reload": "unknown",
                    "native_frame_budget": "unknown",
                }
                if multi_review:
                    gates.update(multi_review["gates"])
                rows[key] = {
                    "name": name,
                    "kind": prefab["kind"],
                    "workshop_id": iid,
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "author": item.get("author"),
                    **traits,
                    "main_triangles": tri,
                    "main_triangle_basis": "native readable main mesh" if tri is not None else "unresolved",
                    "serialized_mesh_triangle_max": serialized_max,
                    "bound_meshes": meshes,
                    "lod_triangles": (measured.get("lod") or {}).get("triangles") if measured else None,
                    "unscaled_mesh_size_m": size,
                    "textures": [{**t, "estimated_full_mip_bytes": resident_bytes(t)} for t in textures],
                    "native": measured,
                    "unresolved_load_evidence": load_gaps.get(name),
                    "near_review": review,
                    "near_capture": near_capture,
                    "multi_view_review": multi_review,
                    "gates": gates,
                    "packages": [],
                    "dependencies": item.get("dependencies"),
                    "dependency_closure": item.get("dependency_closure"),
                    "unresolved_dependencies": item.get("unresolved_dependencies"),
                    "recommendation_role": "reject supplied pack: duplicate prefab identities"
                    if iid in bad_items
                    else "near-art reference candidate; not forest certified"
                    if score is not None and score >= 3
                    else "limited near-art representation"
                    if score == 2
                    else "not recommended from current evidence",
                    "reference_rights": "public Workshop reference only; no redistribution license asserted",
                }
            rows[key]["packages"].append(
                {
                    "file": package["file"],
                    "local_path": package.get("local_path"),
                    "sha256": package["sha256"],
                    "checksum_mismatches": package.get("checksum_mismatches", []),
                }
            )
    prefabs = list(rows.values())
    for item in result["workshop"]:
        members = [p for p in prefabs if p["workshop_id"] == item["id"]]
        item["prefab_review_names"] = [p["name"] for p in members]
        if not members:
            item["assessment"]["failed"].append("no_standalone_tree_or_prop_root")
            item["assessment"]["status"] = "fail"
        grades = [
            p["near_review"]["near_art_score_0_to_4"]
            for p in members
            if p["near_review"] and p["near_review"]["near_art_score_0_to_4"] is not None
        ]
        item["best_near_art_score"] = max(grades, default=None)
        item["native_prefabs"] = [p["native"] for p in members if p["native"]]
        item["qualified_near_reference_names"] = [
            p["name"]
            for p in members
            if all(p["gates"][gate] == "pass" for gate in ("native_load", "dependencies", "near_art"))
        ]
        if item["id"] in bad_items:
            item["assessment"]["failed"].append("duplicate_prefab_identities_in_supplied_pack")
            item["assessment"]["status"] = "fail"
    for base in result["base"]:
        base["native"] = native.get(base["name"])
        base["observed_runtime_environment"] = (
            "Loaded in a fresh Grand River Temperate city; not an exclusive theme restriction"
            if base["native"]
            else None
        )
    cells = []
    reference_bins = result["biome_scheme"]["biomes"] + [
        {
            "id": None,
            "name": "Form reference — ecological range unverified",
            "forms": sorted({p["form"] for p in prefabs} - {"unknown"}),
        }
    ]
    for biome in reference_bins:
        forms = sorted(
            set(biome["forms"])
            | {p["form"] for p in prefabs if biome["id"] in p["biomes"] and p["form"] != "unknown"}
        )
        for form in forms:
            matches = [
                p
                for p in prefabs
                if (biome["id"] is None or biome["id"] in p["biomes"])
                and p["form"] == form
                and p["near_review"]
                and p["near_review"]["near_art_score_0_to_4"] is not None
                and p["near_review"]["near_art_score_0_to_4"] >= 3
                and p["gates"]["native_load"] == "pass"
                and p["gates"]["dependencies"] == "pass"
            ]
            matches.sort(
                key=lambda p: (
                    -p["near_review"]["near_art_score_0_to_4"],
                    p["gates"]["geometry"] != "pass",
                    p["gates"]["textures"] != "pass",
                    p["main_triangles"] or 10**9,
                    p["name"],
                )
            )
            eligible = [p for p in matches if p["gates"]["geometry"] == p["gates"]["textures"] == "pass"]
            cells.append(
                {
                    "biome_id": biome["id"],
                    "biome": biome["name"],
                    "form": form,
                    "best_observed_near_art": matches[0]["name"] if matches else None,
                    "best_within_forest_geometry_texture_targets": eligible[0]["name"] if eligible else None,
                    "reviewed_good_candidates": len(matches),
                    "quality": matches[0]["near_review"]["near_art_score_0_to_4"] if matches else None,
                    "status": "qualified near-view reference" if matches else "no vetted match",
                    "limits": "Name-screened biome/form, not ecological validation or full-bar certification",
                }
            )
    result.update(
        schema_version=2,
        prefab_reviews=prefabs,
        best_by_biome_form=cells,
        native_review_runs=runs,
        prefab_name_collisions=collisions,
        near_art_rubric=reviews["rubric"],
    )
    result["review_coverage"] = {
        "measured_prefabs": len(prefabs),
        "measured_items": len({p["workshop_id"] for p in prefabs}),
        "native_loaded_prefabs": sum(p["native"] is not None for p in prefabs),
        "near_attempts_reviewed": sum(p["near_review"] is not None for p in prefabs),
        "near_frames_reviewed": sum(
            p["near_review"] is not None and bool((p["near_capture"] or {}).get("views", {}).get("close"))
            for p in prefabs
        ),
        "near_graded": sum(
            p["near_review"] is not None and p["near_review"]["near_art_score_0_to_4"] is not None
            for p in prefabs
        ),
        "qualified_near_reference_items": sum(
            bool(item["qualified_near_reference_names"]) for item in result["workshop"]
        ),
        "unresolved_native_loads": [p["name"] for p in prefabs if not p["native"]],
        "unattempted_near_identities": [p["name"] for p in prefabs if not p["near_review"]],
    }
    result["review_gate_counts"] = (
        {
            gate: {
                state: sum(p["gates"][gate] == state for p in prefabs)
                for state in ("pass", "limited", "fail", "unknown")
            }
            for gate in prefabs[0]["gates"]
        }
        if prefabs
        else {}
    )
    dlc = directory / "dlc-inventory.json"
    if dlc.exists():
        result["dlc_inventory"] = {
            **json.loads(dlc.read_text()),
            "source": "Read-only SteamApps008, existing offline client, 2026-11-25",
            "scope": "DLC entries returned for CS1 by this client; not a global DLC-store census",
        }
        result["all_dlc_ownership_verified"] = bool(result["dlc_inventory"].get("dlc"))
