"""Input-bound sparse evidence must not silently change another map or head."""

import copy
import unittest

import numpy as np

from wet_reach_admission import SIZE, canonical, digest, replay_arrays


class WetReachContractTests(unittest.TestCase):
    def setUp(self):
        self.terrain = np.full(SIZE, 6400, dtype="<u2")
        self.water = np.zeros(SIZE, dtype="<u2")
        self.water[7] = 64
        bound = {
            "terrain": digest(self.terrain.tobytes()),
            "water": digest(self.water.tobytes()),
            "native_forcing": "test-only source identity",
        }
        self.fingerprint = digest(canonical(bound))
        after_t, after_w = self.terrain.copy(), self.water.copy()
        after_t[7], after_w[7] = 6592, 0
        self.record = {
            "format": 1,
            "fingerprint": self.fingerprint,
            "bindings": bound,
            "edits": [[7, 6400, 6592, 64, 0]],
            "target": {
                "terrain": digest(after_t.tobytes()),
                "water": digest(after_w.tobytes()),
            },
        }

    def test_restores_only_bound_cells_without_mutating_inputs(self):
        t, w = replay_arrays(self.terrain, self.water, self.fingerprint, self.record)
        self.assertEqual(t[7], 6592)
        self.assertEqual(w[7], 0)
        self.assertEqual(np.count_nonzero(t != self.terrain), 1)
        self.assertEqual(self.terrain[7], 6400)
        self.assertEqual(self.water[7], 64)

    def test_changed_source_or_grid_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different inputs"):
            replay_arrays(self.terrain, self.water, "different forcing", self.record)
        changed = self.terrain.copy()
        changed[100] += 1
        with self.assertRaisesRegex(ValueError, "baseline grids changed"):
            replay_arrays(changed, self.water, self.fingerprint, self.record)

    def test_lowering_and_new_water_are_rejected_before_output(self):
        for edit in [[7, 6400, 6399, 64, 0], [7, 6400, 6592, 64, 65]]:
            record = copy.deepcopy(self.record)
            record["edits"] = [edit]
            with self.assertRaisesRegex(ValueError, "deepen floors or add water"):
                replay_arrays(self.terrain, self.water, self.fingerprint, record)

    def test_duplicate_or_out_of_range_edits_are_rejected(self):
        for edits in [self.record["edits"] * 2, [[SIZE, 6400, 6592, 0, 0]]]:
            record = copy.deepcopy(self.record)
            record["edits"] = edits
            with self.assertRaisesRegex(ValueError, "indices"):
                replay_arrays(self.terrain, self.water, self.fingerprint, record)

    def test_tampered_old_value_or_output_digest_is_rejected(self):
        record = copy.deepcopy(self.record)
        record["edits"][0][1] -= 1
        with self.assertRaisesRegex(ValueError, "old values"):
            replay_arrays(self.terrain, self.water, self.fingerprint, record)
        record = copy.deepcopy(self.record)
        record["target"]["terrain"] = "unverified output"
        with self.assertRaisesRegex(ValueError, "target digest"):
            replay_arrays(self.terrain, self.water, self.fingerprint, record)


if __name__ == "__main__":
    unittest.main()
