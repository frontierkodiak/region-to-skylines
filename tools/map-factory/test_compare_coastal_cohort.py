"""Fixed failed probes cannot disappear from an intervention comparison."""

import json
from pathlib import Path
import tempfile
import unittest

from compare_coastal_cohort import compare
from water_risk_corpus import sha


class CoastalCohortTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.baseline, self.intervention = self.root / "before", self.root / "after"
        self.audit, self.receipt = self.root / "audit.json", self.root / "receipt.json"
        self.old = {
            "name": "river [river] #1:00",
            "x": 0,
            "z": 0,
            "wet_start": True,
            "wet_end": False,
            "wet_within_64m_end": False,
            "nearby_samples": 13,
            "dry_within_64m_samples": 12,
        }
        self.new = {**self.old, "wet_end": True, "wet_within_64m_end": True}
        for directory, point in [
            (self.baseline, self.old),
            (self.intervention, self.new),
        ]:
            directory.mkdir()
            (directory / "probes.json").write_text("{}")
            (directory / "report.json").write_text(json.dumps({"points": [point]}))
        self.audit.write_text(
            json.dumps(
                {
                    "files": {
                        "native_report": {"sha256": sha(self.baseline / "report.json")},
                        "native_probes": {"sha256": sha(self.baseline / "probes.json")},
                    },
                    "static_ocean_connectivity": {
                        "cohort": "previously lost development probes",
                        "lost_probe_count": 1,
                        "probes": [
                            {**self.old, "ocean_connected": {"4": True, "8": True}}
                        ],
                    },
                }
            )
        )
        self.bind_receipt()

    def bind_receipt(self):
        self.receipt.write_text(
            json.dumps(
                {
                    key: {
                        name: sha(directory / name)
                        for name in ("report.json", "probes.json")
                    }
                    for key, directory in [
                        ("baseline_files_sha256", self.baseline),
                        ("native_files_sha256", self.intervention),
                    ]
                }
            )
        )

    def result(self):
        return compare(self.audit, self.baseline, self.intervention, self.receipt)

    def test_endpoint_recovery_does_not_imply_throughout_retention(self):
        group = self.result()["groups"]["river"]
        self.assertEqual(group["intervention_wet_end"], 1)
        self.assertEqual(group["intervention_wet_throughout"], 0)

    def test_receipt_drift_is_not_scored(self):
        (self.intervention / "probes.json").write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, "validated native receipt"):
            self.result()

    def test_missing_failed_probe_is_not_a_success_even_with_new_receipt(self):
        (self.intervention / "report.json").write_text('{"points":[]}')
        self.bind_receipt()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.result()
