"""Prove a startup wetness regression from raw native receipts, not inference."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "cs1-harness"))
from cs1_harness.verdict import MAP_SOAK, required  # noqa: E402


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run, prepared, output):
    session = read(run / "session-receipt.json")
    hydro = read(prepared / "hydrology.json")
    package = prepared / (hydro["map_id"] + ".crp")
    assert session["map"]["sha256"] == sha(package)
    grids = {}
    for name in ["terrain", "water"]:
        actual, expected = run / f"grids/t000-{name}.u16", prepared / f"{name}.u16"
        assert actual.read_bytes() == expected.read_bytes(), name
        grids[name] = sha(actual)
    probes = read(run / "probes.json")["points"]
    meta = {p["name"]: p for p in probes}
    assert len(meta) == len(probes)
    rows = [
        json.loads(line) for line in (run / "timeline.jsonl").read_text().splitlines()
    ]
    first = next(row for row in rows if row["kind"] == "sample")
    points = first["water"]["samples"]
    assert len(points) == len(probes)
    for actual, expected in zip(points, probes):
        assert all(actual[k] == expected[k] for k in ["name", "x", "z"])
    cohort = [p for p in points if required(p, meta[p["name"]], MAP_SOAK)]
    dry = [p for p in cohort if not (p["wet"] or p.get("wet_within_64m"))]
    fraction = (len(cohort) - len(dry)) / len(cohort)
    result = {
        "native_observed": True,
        "not_full_native_qualification": True,
        "crp_sha256": sha(package),
        "initial_grids_exact_sha256": grids,
        "label": first["label"],
        "frame": first["water"]["frame"],
        "required": len(cohort),
        "wet_or_near": len(cohort) - len(dry),
        "fraction": fraction,
        "threshold": MAP_SOAK["wet_end_min_fraction"],
        "fails_wet_throughout_at_start": fraction < MAP_SOAK["wet_end_min_fraction"],
        "dry": dry,
        "receipt_sha256": {
            name: sha(run / name)
            for name in ["timeline.jsonl", "probes.json", "session-receipt.json"]
        },
        "cleanup": session["cleanup"],
        "abort": "Operator called quit after startup regression was proven; raw game-crash triage describes that intentional stop, not a spontaneous crash.",
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "required",
                    "wet_or_near",
                    "fraction",
                    "fails_wet_throughout_at_start",
                    "cleanup",
                ]
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "prepared", "output"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    audit(args.run, args.prepared, args.output)
