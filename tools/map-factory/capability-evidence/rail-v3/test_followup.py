"""Continuation preserves failed attempts and never repeats a completed case."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

import followup


class FollowupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.study = Path(self.temp.name)
        self.selection = json.loads((followup.BASE / "selection.json").read_text())
        (self.study / "selection.json").write_bytes(
            (followup.BASE / "selection.json").read_bytes()
        )
        self.manifest = json.loads((followup.BASE / "integrity.json").read_text())
        followup.unpack(followup.BASE, self.manifest, self.study)

    def case(self, slug):
        return next(c for c in self.selection["cohort"] if c["slug"] == slug)

    def test_failed_queue_attempt_is_preserved_with_a_new_output_slug(self):
        path = self.study / "raw/rio/observation.json"
        original = path.read_bytes()
        planned = followup.choose_attempt(self.study, self.case("rio"))
        self.assertEqual(planned["slug"], "rio-attempt-2")
        self.assertEqual(planned["original_case"], "rio")
        self.assertEqual(
            planned["artifact_sha256"], self.case("rio")["artifact_sha256"]
        )
        self.assertEqual(path.read_bytes(), original)
        (self.study / "raw/rio-attempt-2").mkdir()
        self.assertEqual(
            followup.choose_attempt(self.study, self.case("rio"))["slug"],
            "rio-attempt-3",
        )

    def test_completed_bound_case_is_not_repeated_and_unbound_completion_is_not_accepted(
        self,
    ):
        self.assertIsNone(followup.choose_attempt(self.study, self.case("asheville")))
        path = self.study / "raw/rio/observation.json"
        observation = json.loads(path.read_text())
        observation["completed"] = True
        path.write_text(json.dumps(observation))
        self.assertIsNotNone(followup.choose_attempt(self.study, self.case("rio")))

    def test_changed_raw_hash_is_rejected_before_interpretation(self):
        changed = copy.deepcopy(self.manifest)
        changed["files"][0]["sha256"] = "wrong"
        self.assertNotEqual(
            changed["files"][0]["sha256"], self.manifest["files"][0]["sha256"]
        )
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            followup.unpack(followup.BASE, changed, self.study / "tampered")

    def test_completed_finite_miss_is_not_repeated_to_select_a_better_result(self):
        path = self.study / "raw/asheville/observation.json"
        observation = json.loads(path.read_text())
        for row in observation["paths"]:
            row["result"].update(success=False, flags=8, positions=[])
        path.write_text(json.dumps(observation))
        rows = followup.attempts(self.study, self.case("asheville"))
        self.assertEqual(rows[0][1]["boundary_successes"], 0)
        self.assertTrue(rows[0][1]["completed"])
        self.assertIsNone(followup.choose_attempt(self.study, self.case("asheville")))


if __name__ == "__main__":
    unittest.main()
