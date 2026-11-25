"""Export exact, local-only Workshop controls for the PL-1328 bake trial."""

import argparse
import hashlib
import json
from pathlib import Path


def export(index_path, final, out):
    index = json.loads(index_path.read_text())
    prefabs = {p["name"]: p for p in index["prefab_reviews"]}
    items = {i["id"]: i for i in index["workshop"]}
    extra = final / "references/specimens.json"
    evidence = json.loads(extra.read_text()) if extra.exists() else []
    main = final / "specimens.json"
    if main.exists():
        evidence += json.loads(main.read_text())
    views = {r["candidate"]: r for r in evidence}
    catalog_path = final / "native-catalog.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {"trees": []}
    loaded = {p["name"]: p for p in catalog["trees"]}
    reload_path = final / "save-reload.json"
    reload = json.loads(reload_path.read_text()) if reload_path.exists() else {}

    def reference(name, reason):
        p = prefabs[name]
        item = items[p["workshop_id"]]
        native = {**loaded[name], "source_run": final.name} if name in loaded else None
        if not native:
            raise ValueError(f"Reference was never loaded: {name}")
        entry = views.get(name)
        frames = []
        if entry:
            for view, filename in entry["views"].items():
                path = final / filename
                if not path.exists():
                    path = final / "references" / filename
                frames.append(
                    {"view": view, "file": filename, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                )
        return {
            "loaded_prefab": name,
            "workshop_id": p["workshop_id"],
            "title": p["title"],
            "author": p["author"],
            "url": p["url"],
            "selection_reason": reason,
            "crp_containers": p["packages"],
            "native": native,
            "dependencies": item.get("dependencies"),
            "dependency_closure": item.get("dependency_closure"),
            "unresolved_dependencies": item.get("unresolved_dependencies"),
            "required_mods": item.get("required_mods"),
            "dependency_status": item.get("dependency_status"),
            "near_review": p.get("near_review"),
            "multi_view_evidence": entry,
            "native_frame_hashes": frames,
            "evidence_base_url": "https://blade.tailc29f0.ts.net/shelf/vegetation-supply-pl1326/anchors/",
            "frame_role": "Workshop candidate on the left; stock comparison on the right",
            "bioclip_qualification": "not_run",
            "bioclip_scope": "Close/gameplay/billboard identification is the downstream PL-1328 gate",
            "multi_view_review": p.get("multi_view_review"),
            "save_reload_identity_stable": reload.get("identity_stable")
            if name in reload.get("before_instances", {})
            else None,
            "quality_gates": p["gates"],
            "limits": [
                "Not a forest-fill certification",
                "Genus label is not botanical authentication",
                "Approximately 15 m is a requested model size class, not proof of biological maturity",
            ],
        }

    result = {
        "issue": "PL-1326",
        "consumer": "PL-1328",
        "host": "blade",
        "assembly_sha256": index["assembly_sha256"],
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "scope": "Existing local Workshop references; never redistribute CRPs, meshes or textures",
        "bioclip_qualification": "not_run",
        "bioclip_scope": "No reference is claimed to have passed the downstream classifier gate",
        "genera": {
            "Gleditsia": {
                "status": "no_vetted_match",
                "reference": None,
                "evidence": "Authenticated genus search returned zero; bounded discovery title/description review found no honey-locust match. Not an exhaustive absence claim.",
            },
            "Tilia": {
                "status": "native_reference_with_qualifications",
                "best_intrinsic_size_match": reference(
                    "2928288862.Kaiserlinde 16m_Data",
                    "16.48 m generated height, random scale 0.86–1.11; closest intrinsic ~15 m control",
                ),
                "best_near_art_alternative": reference(
                    "2402946167.Bigleaf Linden_Data",
                    "Stronger near-art grade; 12.30 m generated height before 1–1.5 native random scale",
                ),
            },
            "Ulmus": {
                "status": "native_reference_with_qualifications",
                "reference": reference(
                    "2456536855.American Elm_Data",
                    "14.96 m generated height before random scale; readable spreading/vase form",
                ),
            },
        },
    }
    out.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--final", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    export(args.index, args.final, args.out)
