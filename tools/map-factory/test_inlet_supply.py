"""A normal invocation must not produce a known-failing native candidate."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class RejectedInletTest(unittest.TestCase):
    def test_ordinary_build_refuses_before_reading_or_creating_inputs(self):
        script = Path(__file__).with_name("inlet_supply.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--repo",
                    str(root),
                    "--inputs",
                    str(root / "missing"),
                    "--native",
                    str(root / "missing"),
                    "--trace",
                    str(root / "missing"),
                    "--trace-case",
                    "case",
                    "--out",
                    str(root / "audit.json"),
                    "--build",
                    str(root / "candidate"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Known native flood/pool failure", result.stderr)
            self.assertFalse((root / "candidate").exists())
            self.assertFalse((root / "audit.json").exists())


if __name__ == "__main__":
    unittest.main()
