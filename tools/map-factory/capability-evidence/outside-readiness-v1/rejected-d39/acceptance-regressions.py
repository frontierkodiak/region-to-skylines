"""CONSTRUCTED acceptance regressions for PL-1307 PR91 at d39a31e.

Run with: uv run --no-project python acceptance-regressions.py REPOSITORY
These tests must pass before source acceptance. They fail on the reviewed head.
No game, old scorer, native outcomes, or repository files are changed.
"""

import copy
from pathlib import Path
import sys
import unittest

repository = Path(sys.argv.pop(1)).resolve()
sys.path.insert(
    0,
    str(repository / "tools/map-factory/capability-evidence/outside-readiness-v1"),
)
import readiness  # noqa: E402
from test_readiness import constructed  # noqa: E402


class AcceptanceRegressions(unittest.TestCase):
    def test_missing_required_facts_must_not_be_ready(self):
        for fact in (
            "artifact_sha256",
            "protocol_sha256",
            "dll_sha256",
            "mods_inventory_root",
            "consumed_field_hashes",
        ):
            with self.subTest(missing=fact):
                frozen, observed, policy = constructed()
                if fact == "artifact_sha256":
                    frozen[fact] = observed[fact] = None
                elif fact == "protocol_sha256":
                    frozen[fact] = observed[fact] = policy[fact] = None
                    for phase in observed["runtime"].values():
                        phase[fact] = None
                elif fact == "dll_sha256":
                    policy[fact] = None
                    for phase in observed["runtime"].values():
                        phase[fact] = None
                elif fact == "mods_inventory_root":
                    policy["roots"].pop("mods")
                    for phase in observed["runtime"].values():
                        phase["roots"].pop("mods")
                else:
                    frozen["consumed_fields"] = {
                        key: None for key in readiness.CONSUMED_COVERAGE
                    }
                    observed["consumed_fields"] = copy.deepcopy(
                        frozen["consumed_fields"]
                    )
                result = readiness.check(
                    [frozen], {frozen["case_id"]: observed}, policy, set()
                )
                self.assertEqual(result.pre_export_qualification, "unknown")
                self.assertFalse(result.ready_for_measurement, fact)


if __name__ == "__main__":
    unittest.main(verbosity=2)
