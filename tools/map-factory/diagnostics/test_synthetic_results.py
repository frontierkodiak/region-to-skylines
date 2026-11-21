import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from synthetic_results import COMMENT, authorized, floor_checks, runtime_locations, sha


class AuthorizedResultTests(unittest.TestCase):
    def test_runtime_missing_or_mismatched_location_bytes_are_not_identity_passes(self):
        receipt = {"game_assemblies": {"Engine.dll": "engine"}, "dll_sha256": "mod"}
        records = [
            {
                "modules": [
                    {"name": "Cs1Harness, Version=1", "current_location_sha256": "mod"}
                ]
            }
        ]
        result = runtime_locations(records, receipt)
        self.assertEqual([r["status"] for r in result["checks"]], ["unknown", "pass"])
        records[0]["modules"][0]["current_location_sha256"] = "different"
        self.assertEqual(
            runtime_locations(records, receipt)["checks"][1]["status"], "fail"
        )

    def test_authorization_is_not_a_review_pass_and_binds_exact_protocol(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder / "protocol.json").write_text("unchanged prospective protocol")
            path = folder / "authorization.json"
            record = {
                "authorizing_comment": COMMENT,
                "frozen_protocol_sha256": sha(folder / "protocol.json"),
                "independent_results_review_before_adoption": True,
            }
            path.write_text(json.dumps(record))
            self.assertNotIn("status", authorized(folder, path))
            (folder / "protocol.json").write_text("changed cohort")
            with self.assertRaisesRegex(ValueError, "exact user"):
                authorized(folder, path)

    def test_actual_bank_or_channel_drift_fails_separately_from_depth(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "grids").mkdir()
            path = root / "grids/ws000000-water-ground.u16"
            floor = np.full((1081, 1081), 6400, np.uint16)
            floor[540, 540] = 6272
            construction = {
                "nodes": [{"node_rc": [540, 540], "stage_q": 6368}],
                "rim_rc": [
                    [r, c]
                    for r in range(539, 542)
                    for c in range(539, 542)
                    if (r, c) != (540, 540)
                ],
            }

            def check():
                np.flipud(floor).astype("<u2").tofile(path)
                return floor_checks(
                    root,
                    {
                        "prefix": "ws000000",
                        "files": {"water-ground": {"sha256": sha(path)}},
                    },
                    construction,
                )

            self.assertEqual(check()["status"], "pass")
            floor[539, 539] = 6368
            self.assertEqual(check()["status"], "fail")
            floor[539, 539], floor[540, 540] = 6400, 6368
            result = check()
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["minimum_authored_stage_to_actual_floor_m"], 0)
