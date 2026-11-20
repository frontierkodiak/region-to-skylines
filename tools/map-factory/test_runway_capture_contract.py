"""Historical capture sources remain explicit and tamper-evident in Python."""

import shutil
import tempfile
import unittest
from pathlib import Path

from verify_regions import ROOT, historical_capture_sources

PREFIX = Path("contracts/pl1066-optional-runways-v1")


class HistoricalCaptureSource(unittest.TestCase):
    def test_historical_identity_differs_from_current_compatible_source(self):
        sources = historical_capture_sources(ROOT / "fixtures")
        self.assertEqual(set(sources), {"inputs.js"})
        self.assertNotEqual(
            sources["inputs.js"], (ROOT.parents[1] / "inputs.js").read_bytes()
        )
        self.assertEqual(
            sources["inputs.js"],
            (ROOT / "fixtures" / PREFIX / "historical-inputs.js").read_bytes(),
        )

    def test_archives_and_compatibility_proof_cannot_be_changed(self):
        for name in [
            "historical-inputs.js",
            "capture-compatibility.json",
            "previous-active.json",
            "predecessor.json",
        ]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                shutil.copytree(ROOT / "fixtures" / PREFIX, folder / PREFIX)
                shutil.copyfile(ROOT / "fixtures/active.json", folder / "active.json")
                old = folder / "contracts/pl912-water-risk-v1"
                old.mkdir()
                shutil.copyfile(
                    ROOT / "fixtures/contracts/pl912-water-risk-v1/current.json",
                    old / "current.json",
                )
                target = folder / PREFIX / name
                target.write_bytes(target.read_bytes() + b" ")
                with self.assertRaises(AssertionError):
                    historical_capture_sources(folder)


if __name__ == "__main__":
    unittest.main()
