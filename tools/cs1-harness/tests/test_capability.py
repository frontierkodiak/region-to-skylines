import json
from pathlib import Path
import tempfile
import unittest

from cs1_harness.capability import digest, prediction, sha


class PredictionBinding(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / "map.crp"
        self.package.write_bytes(b"exact package")
        self.path = self.root / "prediction.json"
        model = {"id": "synthetic", "parameters": {"spacing": 16}}
        self.model_hash = digest(model)
        self.witness = {"schema": 1, "steps": [{"from": "a", "to": "b"}]}
        self.row = {
            "model": {**model, "sha256": self.model_hash},
            "artifact_sha256": sha(self.package),
            "capabilities": {"start": {"witness": self.witness, "witness_sha256": digest(self.witness)}},
        }

    def write(self):
        self.path.write_text(json.dumps(self.row))

    def test_accepts_exact_map_model_and_witness(self):
        self.write()
        self.assertEqual(self.row, prediction(self.path, self.package, self.model_hash))

    def test_rejects_changed_map_before_controller_acquisition(self):
        self.write()
        self.package.write_bytes(b"different package")
        with self.assertRaisesRegex(ValueError, "exact map"):
            prediction(self.path, self.package, self.model_hash)

    def test_rejects_model_parameter_change_under_old_digest(self):
        self.row["model"]["parameters"]["spacing"] = 32
        self.write()
        with self.assertRaisesRegex(ValueError, "Model binding"):
            prediction(self.path, self.package, self.model_hash)

    def test_rejects_changed_ordered_witness_under_old_digest(self):
        self.row["capabilities"]["start"]["witness"]["steps"].reverse()
        self.row["capabilities"]["start"]["witness"]["steps"].append({"from": "b", "to": "a"})
        self.write()
        with self.assertRaisesRegex(ValueError, "Witness binding"):
            prediction(self.path, self.package, self.model_hash)


if __name__ == "__main__":
    unittest.main()
