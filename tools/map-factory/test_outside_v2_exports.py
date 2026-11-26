"""Exact certificate checks on actual retained exports, with JS parity.

Run on blade with OUTSIDE_V2_SELECTION pointing to the fixed native selection.
No writer, collector or game is invoked. Contexts are replayed from the same
retained observations, not evidence of a fresh game launch or a pan-time promise.
"""

import copy
import json
import os
from pathlib import Path
import subprocess
import unittest

from capabilities import check, prepared_input
from integrate_outside_v2 import ROOT, STUDY, encoded, sha

SELECTION = os.environ.get("OUTSIDE_V2_SELECTION")


@unittest.skipUnless(SELECTION, "Set OUTSIDE_V2_SELECTION to actual blade export paths")
class ActualExportTests(unittest.TestCase):
    def test_exact_certificates_actual_inputs_and_contexts(self):
        ledger = json.loads((ROOT / "capabilities.json").read_bytes())
        candidates = ledger["evidence_studies"][STUDY]["qualification_candidates"]
        activated = copy.deepcopy(ledger)
        activated["native_path_certificates"] = copy.deepcopy(candidates)
        for certificate in activated["native_path_certificates"]:
            self.assertEqual(
                certificate.pop("blocked_by"), ["independent_review_pending"]
            )
        self.assertEqual(
            ledger["native_path_certificates"], activated["native_path_certificates"]
        )
        unqualified = copy.deepcopy(ledger)
        unqualified["native_path_certificates"] = []
        selection_bytes = Path(SELECTION).read_bytes()
        self.assertEqual(
            sha(selection_bytes), ledger["evidence_studies"][STUDY]["selection_sha256"]
        )
        by_artifact = {c["artifact_sha256"]: c for c in candidates}
        cases, records, promotions = [], [], 0
        originals = []
        for selected in json.loads(selection_bytes)["cases"]:
            package = Path(selected["package"])
            self.assertEqual(sha(package.read_bytes()), selected["artifact_sha256"])
            data = prepared_input(package.parent)
            certificate = by_artifact.get(selected["artifact_sha256"])
            identity = {
                "artifact_sha256": sha(package.read_bytes()),
                "inputs_sha256": {
                    name: sha((package.parent / name).read_bytes())
                    for name in ("terrain.u16", "water.u16", "hydrology.json")
                },
                "native_context": copy.deepcopy(certificate["native_context"])
                if certificate
                else None,
            }
            if certificate:
                self.assertEqual(
                    identity["inputs_sha256"], certificate["inputs_sha256"]
                )
            data["export_identity"] = identity
            report = check(data, unqualified)
            self.assertTrue(
                all(c["level"] != "promised" for c in report["capabilities"].values())
            )
            planned = check(data, ledger)
            promised = [
                k
                for k, c in planned["capabilities"].items()
                if c["level"] == "promised"
            ]
            self.assertEqual(promised, ["ship"] if certificate else [])
            promotions += len(promised)
            cases.append(data)
            originals.append(data)
            records.append(
                {
                    "artifact_sha256": identity["artifact_sha256"],
                    "inputs_sha256": identity["inputs_sha256"],
                    "planned_promotions": promised,
                }
            )
            if not certificate:
                continue
            mutations = [
                lambda d: d.__setitem__("mode", "estimate"),
                lambda d: d.pop("export_identity"),
                lambda d: d["export_identity"].__setitem__("artifact_sha256", "0" * 64),
                lambda d: d["export_identity"]["inputs_sha256"].__setitem__(
                    "terrain.u16", "0" * 64
                ),
                lambda d: d["export_identity"]["native_context"]["opening_plugins"][
                    0
                ].__setitem__("enabled", True),
                lambda d: d["export_identity"]["native_context"][
                    "opening_runtime_identity"
                ]["assemblies"][1].__setitem__("sha256", "0" * 64),
                lambda d: d["export_identity"]["native_context"][
                    "opening_runtime_identity"
                ].__setitem__("namespace_pid", 1),
                lambda d: d["export_identity"]["native_context"][
                    "opening_runtime_identity"
                ].__setitem__("process_start_ticks", "1"),
                lambda d: d["export_identity"]["native_context"][
                    "collector_sources"
                ].__setitem__("runtime_identity.py", "0" * 64),
            ]
            for mutate in mutations:
                changed = copy.deepcopy(data)
                mutate(changed)
                self.assertTrue(
                    all(
                        c["level"] != "promised"
                        for c in check(changed, activated)["capabilities"].values()
                    )
                )
                cases.append(changed)
        self.assertEqual(promotions, 4)
        expected = [
            {k: v["level"] for k, v in check(data, activated)["capabilities"].items()}
            for data in cases
        ]
        # Complete Start grids make the former single JSON payload exceed V8's
        # string limit. Stream one normalized input at a time, retaining every
        # real-input and certificate mutation check at full fidelity.
        script = "import {createInterface} from 'node:readline';import {checkCapabilities} from './capability-model.js';for await(const line of createInterface({input:process.stdin})){const p=JSON.parse(line);console.log(JSON.stringify(Object.fromEntries(Object.entries(checkCapabilities(p.data,p.ledger).capabilities).map(([k,v])=>[k,v.level]))));}"
        actual = []
        with subprocess.Popen(
            ["node", "--input-type=module", "-e", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            cwd=ROOT,
        ) as process:
            for data in cases:
                process.stdin.write(
                    json.dumps({"data": data, "ledger": activated}) + "\n"
                )
                process.stdin.flush()
                actual.append(json.loads(process.stdout.readline()))
            process.stdin.close()
            self.assertEqual(process.wait(), 0)
        self.assertEqual(actual, expected)
        browser_output = os.environ.get("OUTSIDE_V2_BROWSER_INPUTS")
        if browser_output:
            Path(browser_output).write_bytes(
                encoded(
                    {
                        "scope": "Real retained prepared inputs with replayed exact native contexts; not fresh game evidence or a pan-time promise.",
                        "cases": originals,
                    }
                )
            )
        output = os.environ.get("OUTSIDE_V2_EXPORT_RESULTS")
        if output:
            Path(output).write_bytes(
                encoded(
                    {
                        "scope": "Exact retained exports and replayed observation contexts; no fresh native run or pan-time promise.",
                        "ledger_sha256": sha((ROOT / "capabilities.json").read_bytes()),
                        "certificate_receipts": [
                            c["runtime_identity_evidence"]
                            for c in ledger["native_path_certificates"]
                        ],
                        "actual_export_results": records,
                        "parity_cases": len(cases),
                        "exact_context_ship_promotions": promotions,
                    }
                )
            )
        print(
            f"Actual retained exports: 9; exact-context ship promotions: {promotions}; JS/Python parity: {len(cases)}; negative mutation/pan promotions: 0"
        )


if __name__ == "__main__":
    unittest.main()
