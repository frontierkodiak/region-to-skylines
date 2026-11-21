"""Read-only real-input parity artifact builder; never consumes native outcomes."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile

from capabilities import assess_prepared, prepared_input
from test_water_model import WaterTests, js
from water_model import evaluate_water

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retained-list", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cases = []
    if args.retained_list:
        # Only package locators and exact physical identities, not prior predictions.
        for row in json.loads(args.retained_list.read_text())["rows"]:
            package = Path(row["package"])
            cases.append((package.parent.name, package.parent, package))
    with tempfile.TemporaryDirectory() as temp:
        for slug in ("innsbruck", "pittsburgh", "charleston", "asheville", "rio"):
            folder = Path(temp) / slug
            folder.mkdir()
            for name in ("terrain.u16", "water.u16", "hydrology.json"):
                (folder / name).write_bytes(
                    gzip.decompress(
                        (
                            ROOT / "tools/map-factory/fixtures" / slug / (name + ".gz")
                        ).read_bytes()
                    )
                )
            cases.append(("fixture-" + slug, folder, None))
        rows = []
        for i, (name, folder, package) in enumerate(cases):
            data = prepared_input(folder)
            expected = evaluate_water(data)
            WaterTests().same(expected, js(data))
            report = assess_prepared(folder)
            (args.out / f"{i}.json").write_text(json.dumps(data, separators=(",", ":")))
            (args.out / f"{i}-report.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
            rows.append(
                {
                    "case": name,
                    "file": f"{i}.json",
                    "expected": expected,
                    "artifact_sha256": sha(package) if package else None,
                    "inputs_sha256": {
                        f: sha(folder / f)
                        for f in ("terrain.u16", "water.u16", "hydrology.json")
                    },
                    "parity": "python_node_pass",
                    "report": f"{i}-report.json",
                }
            )
            print(name, expected["reason"], flush=True)
        (args.out / "cases.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
