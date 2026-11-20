"""Remeasure only the frozen old corpus; preserve labels and physical bindings."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from calibrate_water_risk import calibrate
from water_risk import assess, measure

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def refresh(experiments, output):
    fixtures = ROOT / "fixtures"
    contract_path = fixtures / "contracts/pl912-water-risk-v1/current.json"
    contract = json.loads(contract_path.read_text())
    corpus_path = fixtures / contract["corpus_file"]
    original = json.loads(corpus_path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    changes = []
    # Preserve the exact landed screen and old feature values before refreshing.
    for name, raw in {
        "original-corpus.json": corpus_path.read_bytes(),
        "original-contract.json": contract_path.read_bytes(),
        "original-model.json": (ROOT / "water-risk-model.json").read_bytes(),
    }.items():
        (output / name).write_bytes(raw)
    for row in original:
        run = experiments / row["run"]
        for name, expected in row["receipt_hashes"].items():
            if sha(run / name) != expected:
                raise ValueError(f"Old native receipt changed: {row['run']}/{name}")
        report = json.loads((run / "report.json").read_text())
        package = Path(report["session"]["map"]["source"])
        if sha(package) != row["package_sha256"]:
            raise ValueError(f"Old package changed: {row['run']}")
        source = package.parent
        for name, expected in row["input_hashes"].items():
            if sha(source / name) != expected:
                raise ValueError(f"Old prepared inputs changed: {row['run']}/{name}")
        features = measure(
            np.fromfile(source / "terrain.u16", "<u2").reshape(1081, 1081),
            np.fromfile(source / "water.u16", "<u2").reshape(1081, 1081),
            json.loads((source / "hydrology.json").read_text()),
        )
        delta = {
            k: [v, features[k]] for k, v in row["features"].items() if v != features[k]
        }
        if set(delta) - {"narrow_film_km2"}:
            raise ValueError(f"Unrelated feature drift: {row['run']}: {delta}")
        if delta:
            changes.append({"run": row["run"], "changed_features": delta})
        row["features"] = features
    coverage = json.loads((fixtures / contract["coverage_file"]).read_text())
    model, report = calibrate(original, coverage)
    write(output / "rows.json", original)
    write(output / "model.json", model)
    write(output / "calibration.json", report)
    write(output / "changes.json", changes)
    # This updates only active screen metadata. Historical contracts, native
    # identities, labels, grids, controls and packages are not regenerated.
    write(corpus_path, original)
    write(ROOT / "water-risk-model.json", model)
    contract["corpus_sha256"] = sha(corpus_path)
    contract["calibration"] = model["calibration"]
    repo = ROOT.parent.parent
    for name in contract["source_files_sha256"]:
        if name not in {
            "tools/map-factory/water_risk.py",
            "tools/map-factory/water-risk-model.json",
        }:
            if sha(repo / name) != contract["source_files_sha256"][name]:
                raise ValueError(f"Physical writer/source changed: {name}")
        contract["source_files_sha256"][name] = sha(repo / name)
    for case in contract["cases"]:

        def frozen(name):
            path = case["fixture_files"].get(name, case["slug"] + "/" + name)
            return gzip.decompress((fixtures / path).read_bytes())

        contract["risk_cases"][case["slug"]] = assess(
            np.frombuffer(frozen("terrain.u16.gz"), "<u2").reshape(1081, 1081),
            np.frombuffer(frozen("water.u16.gz"), "<u2").reshape(1081, 1081),
            json.loads(frozen("hydrology.json.gz")),
            model,
        )
    write(contract_path, contract)
    print(
        json.dumps(
            {
                "rows": len(original),
                "changed_rows": len(changes),
                "results": model["calibration"]["results"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiments", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    refresh(args.experiments, args.output)
