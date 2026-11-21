import json
from pathlib import Path
import tempfile
import unittest

from natural_storage_candidate import write
from test_maintained_water_inventory import line
from test_waterway_pieces import geometry
from unprepared_stream_ledger import geometry_only, preflight, sha, stage


class UnpreparedLedgerTests(unittest.TestCase):
    def test_missing_physical_support_is_unknown_not_dry_or_empty_controls(self):
        g = geometry([line((0, 0), (64, 0)), line((64, 0), (96, 0), brunnel="tunnel")])
        ledger = geometry_only(g)
        self.assertEqual(len(ledger["clips"]), 2)
        self.assertTrue(ledger["captured_geographic_vertex_incidence"])
        self.assertIsNone(ledger["configured_controls"])
        self.assertIsNone(ledger["authored_initial_grid"])
        self.assertFalse(ledger["source_contract_inventory"]["coverage_complete"])
        self.assertTrue(
            all(
                c["authored_initialization"].startswith("unknown")
                for c in ledger["clips"]
            )
        )

    def test_retained_refusal_and_coherent_geometry_omission_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "refused"
            source.mkdir()
            write(source / "geometry.json", geometry([line((0, 0), (64, 0))]))
            write(
                root / "preparation.json",
                {
                    "cases": [
                        {
                            "square": "refused",
                            "status": "refused_under_construction_bounds",
                            "reason": "original fixed-bound refusal",
                        }
                    ]
                },
            )
            output = root / "protocol"
            stage(source, output)
            preflight(output)
            path = output / "ledger.json"
            data = json.loads(path.read_text())
            data["clips"].pop()
            write(path, data)
            fp = output / "freeze.json"
            frozen = json.loads(fp.read_text())
            frozen["files_sha256"]["ledger.json"] = sha(path)
            write(fp, frozen)
            with self.assertRaisesRegex(ValueError, "does not replay"):
                preflight(output)
