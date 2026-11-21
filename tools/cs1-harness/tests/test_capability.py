import contextlib
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs1_harness.capability import digest, prediction, run, sha, surface_observation
from cs1_harness.client import HarnessError


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
            mode="start",
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


class SurfaceLabels(unittest.TestCase):
    def setUp(self):
        self.row = {
            "observed_native_placement": True,
            "observed_surface_service": True,
            "observed_water_capability": True,
            "fixture_qualified": True,
            "consumer_api": "spatial_water_and_sewage",
            "settling_has_load": True,
            "settling_samples": [{"loaded": False}] * 29,
            "expected_settling_cycles": 29,
            "observed_horizon_game_minutes": 60.01,
            "cycles": 843,
            "expected_load_cycles": 843,
            "requested_native_units": 843000,
            "fetched_native_units": 843000,
            "sewage_accepted_native_units": 843000,
            "auxiliary_failure_cycles": 0,
            "timing_failure": False,
            "short_water_cycles": 0,
            "short_sewage_cycles": 0,
            "polluted_delivery_cycles": 0,
        }
        facility = {
            "completed": True,
            "electricity_grid_powered": True,
            "declared_pipe_valid": True,
            "production_rate_native": 100,
            "problems": "None",
            "active": True,
        }
        self.row["samples"] = [
            {
                "fetched": 1000,
                "sewage": 1000,
                "pollution_native": 0,
                "auxiliary_valid": True,
                "loaded": True,
                "consumer_pipe_valid": True,
                "intake": copy.deepcopy(facility),
                "outlet": copy.deepcopy(facility),
            }
            for _ in range(843)
        ]

    def test_complete_measured_service_can_score_positive(self):
        self.assertTrue(surface_observation(self.row)["observed_water_capability"])

    def test_partial_horizon_or_auxiliary_failure_cannot_be_called_service(self):
        for key, value in [
            ("observed_horizon_game_minutes", 59),
            ("auxiliary_failure_cycles", 1),
            ("expected_load_cycles", 844),
            ("fixture_qualified", False),
            ("consumer_api", "pipe_node_sewage"),
            ("settling_has_load", False),
            ("expected_settling_cycles", 30),
        ]:
            with self.subTest(key=key), self.assertRaises(HarnessError):
                surface_observation({**self.row, key: value})

    def test_polluted_delivery_is_a_negative_only_with_qualified_complete_fixture(self):
        self.row.update(
            {"observed_surface_service": False, "observed_water_capability": False, "polluted_delivery_cycles": 1}
        )
        self.row["samples"][0]["pollution_native"] = 1
        self.assertFalse(surface_observation(self.row)["observed_water_capability"])

    def test_short_actual_volume_cannot_be_hidden_by_zero_short_cycle_counter(self):
        self.row["fetched_native_units"] -= 1
        with self.assertRaisesRegex(HarnessError, "disagree"):
            surface_observation(self.row)

    def test_facility_warning_cannot_be_hidden_by_powered_grid_and_zero_aggregate_failures(self):
        self.row["samples"][0]["intake"]["problems"] = "Electricity"
        with self.assertRaisesRegex(HarnessError, "facility-side auxiliary"):
            surface_observation(self.row)

    def test_water_specific_failure_is_not_automatically_an_auxiliary_fault(self):
        self.row.update(
            {
                "observed_surface_service": False,
                "observed_water_capability": False,
                "fetched_native_units": 0,
                "short_water_cycles": 843,
            }
        )
        for cycle in self.row["samples"]:
            cycle["fetched"] = 0
            cycle["intake"].update({"problems": "WaterNotFound", "active": False})
        self.assertFalse(surface_observation(self.row)["observed_water_capability"])

    def test_unattempted_service_cannot_score_without_native_necessary_condition_rejection(self):
        with self.assertRaises(HarnessError):
            surface_observation({"observed_water_capability": True})
        with self.assertRaises(HarnessError):
            surface_observation({"observed_water_capability": False})
        self.assertFalse(
            surface_observation({"observed_water_capability": False, "observed_shore_snap": False})[
                "observed_water_capability"
            ]
        )


if __name__ == "__main__":
    unittest.main()
