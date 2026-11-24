"""Check new Start parity on an explicit retained-export selection; no native runs."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from capabilities import assess_prepared, prepared_input
from start_model import evaluate_start

ROOT = Path(__file__).resolve().parents[2]


def compare(expected, actual):
    """Witness coordinates permit sub-micrometre float arithmetic differences."""
    if isinstance(expected, dict):
        assert expected.keys() == actual.keys()
        for key in expected:
            compare(expected[key], actual[key])
    elif isinstance(expected, list):
        assert len(expected) == len(actual)
        for x, y in zip(expected, actual):
            compare(x, y)
    elif type(expected) is float:
        assert abs(expected - actual) <= 1e-7
    else:
        assert expected == actual, (expected, actual)


def verify(selection, output, browser_inputs):
    """Use package paths and hashes only, never native labels or prior predictions."""
    cases = json.loads(selection.read_text())["cases"]
    rows = []
    browser = []
    for row in cases:
        package = Path(row["package"])
        artifact = hashlib.sha256(package.read_bytes()).hexdigest()
        assert artifact == row["artifact_sha256"], package
        data = prepared_input(package.parent)
        expected = evaluate_start(data)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "normalized.json"
            path.write_text(json.dumps(data))
            actual = json.loads(
                subprocess.check_output(
                    [
                        "node",
                        "--input-type=module",
                        "-e",
                        "import {readFileSync} from 'node:fs';import {evaluateStart} from './start-model.js';console.log(JSON.stringify(evaluateStart(JSON.parse(readFileSync(process.argv[1])))))",
                        str(path),
                    ],
                    cwd=ROOT,
                )
            )
        compare(expected, actual)
        report = assess_prepared(package.parent)
        cap = report["capabilities"]["start"]
        assert cap["binding"]["artifact_sha256"] == artifact
        compare(expected, {k: v for k, v in cap.items() if k != "binding"})
        rows.append({"package": str(package), "report": report, "parity": "pass"})
        # Only the new predicate's physical inputs and result; no old labels.
        browser.append(
            {
                "artifact_sha256": artifact,
                "data": {
                    "schema": 1,
                    "mode": "export",
                    "graph": data["graph"],
                    "start_input": data["start_input"],
                },
                "expected": expected,
            }
        )
        print(package.name, expected["reason"], expected.get("predicted"), flush=True)
    output.write_text(
        json.dumps(
            {
                "scope": "Retained real prepared inputs; new deterministic runtime only, no native score reuse",
                "selection_sha256": hashlib.sha256(selection.read_bytes()).hexdigest(),
                "rows": rows,
            },
            indent=2,
        )
        + "\n"
    )
    browser_inputs.write_text(json.dumps(browser) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--browser-inputs", type=Path, required=True)
    args = parser.parse_args()
    verify(args.selection, args.out, args.browser_inputs)
