import contextlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs1_harness.capability import digest, prediction, run, sha


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
            "capabilities": {
                "start": {"witness": self.witness, "witness_sha256": digest(self.witness)},
                "water": {"witness": None, "witness_sha256": None},
            },
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

    def test_rejects_changed_water_witness_under_old_digest(self):
        water = {"intake_water_point": [0, 0, 0]}
        self.row["capabilities"]["water"] = {"witness": water, "witness_sha256": digest(water)}
        water["intake_water_point"][0] = 16
        self.write()
        with self.assertRaisesRegex(ValueError, "Witness binding mismatch: water"):
            prediction(self.path, self.package, self.model_hash)

    def test_rechecks_installed_map_after_queue_and_never_launches_mismatch(self):
        self.write()
        build = self.root / "build"
        build.mkdir()
        (build / "Cs1Harness.dll").write_bytes(b"oracle")
        probes = self.root / "probes.json"
        probes.write_text("{}")
        stage = self.root / "stage"
        original = self.package.read_bytes()
        calls = []

        class Session:
            def __init__(self):
                self.receipt = {}

            def install_map(_, path):
                calls.append("installed")
                path.write_bytes(b"map changed while queued")
                _.receipt["map"] = {"sha256": sha(path)}
                return path

            def launch(_, args):
                calls.append("launch")
                raise AssertionError("must reject changed installed bytes before launch")

        @contextlib.contextmanager
        def fake_slot(*args):
            stage.mkdir()
            try:
                yield Session()
            finally:
                (stage / "session-receipt.json").write_text(
                    json.dumps({"cleanup": {"game": [], "steam_instances": [], "units_active": []}})
                )

        args = SimpleNamespace(
            prediction=self.path,
            map=self.package,
            model_sha256=self.model_hash,
            dll_sha256=sha(build / "Cs1Harness.dll"),
            probes=probes,
            out=self.root / "output",
            issue="synthetic",
            wait_minutes=45,
        )
        with (
            patch("cs1_harness.capability.slot", fake_slot),
            patch("cs1_harness.capability.staging", return_value=stage),
        ):
            self.assertEqual(1, run(SimpleNamespace(build_dir=build), args))
        self.assertNotEqual(original, self.package.read_bytes())
        self.assertEqual(["installed"], calls)
        result = json.loads((args.out / "observation.json").read_text())
        self.assertIsNone(result["observed_start"])
        self.assertIn("Installed map changed", result["error"])


if __name__ == "__main__":
    unittest.main()
