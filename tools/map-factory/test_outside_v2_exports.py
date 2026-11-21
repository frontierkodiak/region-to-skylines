"""Test-only planned activation on actual retained exports, with JS parity.

Run on blade with OUTSIDE_V2_SELECTION pointing to the fixed native selection.
No writer, collector or game is invoked. The activation output is a concrete
review artifact, never an application approval API.
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
    def test_planned_activation_actual_inputs_and_contexts(self):
        ledger = json.loads((ROOT / "capabilities.json").read_bytes())
        candidates = ledger["evidence_studies"][STUDY]["qualification_candidates"]
        activated = copy.deepcopy(ledger)
        activated["native_path_certificates"] = copy.deepcopy(candidates)
        for certificate in activated["native_path_certificates"]:
            self.assertEqual(
                certificate.pop("blocked_by"), ["independent_review_pending"]
            )
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
            report = check(data, ledger)
            self.assertTrue(
                all(c["level"] != "promised" for c in report["capabilities"].values())
            )
            planned = check(data, activated)
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
        script = "import fs from 'node:fs';import {checkCapabilities} from './capability-model.js';const p=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(p.cases.map(d=>Object.fromEntries(Object.entries(checkCapabilities(d,p.ledger).capabilities).map(([k,v])=>[k,v.level])))));"
        actual = json.loads(
            subprocess.check_output(
                ["node", "--input-type=module", "-e", script],
                input=json.dumps({"cases": cases, "ledger": activated}).encode(),
                cwd=ROOT,
            )
        )
        self.assertEqual(actual, expected)
        browser_output = os.environ.get("OUTSIDE_V2_BROWSER_INPUTS")
        if browser_output:
            Path(browser_output).write_bytes(
                encoded(
                    {
                        "scope": "Real retained prepared inputs; proposed activation is constructed, not active or new game evidence.",
                        "cases": originals,
                    }
                )
            )
        output = os.environ.get("OUTSIDE_V2_ACTIVATION_OUT")
        if output:
            Path(output).write_bytes(
                encoded(
                    {
                        "scope": "Proposed only: parent must independently accept exact objects before applying. Test-only activation, not shipped generic bypass.",
                        "ledger_sha256": sha((ROOT / "capabilities.json").read_bytes()),
                        "patch": [
                            {
                                "op": "test",
                                "path": "/native_path_certificates",
                                "value": [],
                            },
                            {
                                "op": "test",
                                "path": f"/evidence_studies/{STUDY}/qualification_candidates",
                                "value": candidates,
                            },
                            {
                                "op": "replace",
                                "path": "/native_path_certificates",
                                "value": activated["native_path_certificates"],
                            },
                        ],
                        "actual_export_results": records,
                        "parity_cases": len(cases),
                        "planned_ship_promotions": promotions,
                    }
                )
            )
        print(
            f"Actual retained exports: 9; planned exact ship promotions: {promotions}; JS/Python parity: {len(cases)}; negative mutation/pan promotions: 0"
        )


if __name__ == "__main__":
    unittest.main()
