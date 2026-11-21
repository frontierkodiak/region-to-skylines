"""Freeze package identities; never export, recapture or change cohort squares."""

import argparse
import hashlib
import json
from pathlib import Path

SOURCE = "0986cf14baabd3317a3b4c18d6690349fc713fb3"
ROOT = Path(__file__).resolve().parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(baseline, boston):
    plan = json.loads((baseline / "cohort.json").read_text())
    slugs = plan["fixtures"] + [s["slug"] for s in plan["fresh"]]
    if slugs != [
        "asheville",
        "innsbruck",
        "rio",
        "pittsburgh",
        "charleston",
        "grand-canyon",
        "hong-kong",
        "yosemite",
    ]:
        raise ValueError("frozen cohort changed")
    cases = []
    for slug in slugs + ["boston"]:
        source = baseline if slug != "boston" else boston
        report_path = source / "cpu-report.json"
        row = json.loads(report_path.read_text())["cases"][slug]
        package = next((source / "maps" / slug).glob("*.crp"))
        digest = sha(package)
        if digest != row["generation"]["package"]["sha256"]:
            raise ValueError(f"package changed: {slug}")
        sq = json.loads((source / "inputs" / slug / "geometry.json").read_text())["sq"]
        if slug == "boston" and [
            sq[k] for k in ["lon", "lat", "rotation", "scale"]
        ] != [-71.057, 42.36, 0, 1]:
            raise ValueError("Boston square changed")
        for name, expected in row["inputs_sha256"].items():
            if sha(source / "inputs" / slug / name) != expected:
                raise ValueError(f"frozen input changed: {slug}/{name}")
        hashes = row["source_files_sha256"]
        mismatches = [
            n for n, h in hashes.items() if sha(ROOT / "tools/map-factory" / n) != h
        ]
        cases.append(
            {
                "slug": slug,
                "square": sq,
                "package": str(package),
                "probes": str(source / "stage/maps" / slug / "probes.json"),
                "artifact_sha256": digest,
                "requested_source_sha": SOURCE,
                "exporter_source_sha": SOURCE if not mismatches else None,
                "source_revision_limitation": mismatches,
                "exporter_source_files_sha256": hashes,
                "cpu_report": str(report_path),
                "cpu_report_sha256": sha(report_path),
                "water_risk_status": row["water_risk"]["status"],
                "water_risk_sha256": sha(source / "maps" / slug / "water-risk.json"),
                "role": "held-out named acceptance"
                if slug == "boston"
                else "fixed observational cohort; no fitted bounds",
            }
        )
    return {
        "schema": 1,
        "issue": "PL-1121",
        "selection_rule": "Five unchanged fixtures, all other PRESETS sorted by slug unchanged, then central Boston (-71.057,42.36), rotation 0 scale 1. Fixed in assignment before results.",
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("boston", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.baseline.resolve(), args.boston.resolve())
    raw = json.dumps(result, indent=2) + "\n"
    if args.out.exists() and args.out.read_text() != raw:
        raise ValueError("refusing to change frozen selection")
    args.out.write_text(raw)
