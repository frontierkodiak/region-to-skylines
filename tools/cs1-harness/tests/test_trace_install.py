"""The optional trace must not leak into a default or unbound installation."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from cs1_harness.client import HarnessError
from cs1_harness.session import Session, sha256


class TraceInstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="trace-install-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.build = self.root / "build"
        self.build.mkdir()
        self.dll = self.build / "Cs1Harness.dll"
        self.dll.write_bytes(b"own synthetic harness sentinel")
        (self.build / "0Harmony.dll").write_bytes(b"own synthetic non-Harmony sentinel")
        self.cfg = SimpleNamespace(build_dir=self.build, mod_dir=self.root / "installed", host="blade", display=":57")
        self.session = Session.__new__(Session)
        self.session.cfg = self.cfg
        self.session.installed = []
        self.session.receipt = {}

    def receipt(self, trace):
        (self.build / "build-receipt.json").write_text(json.dumps({"trace": trace, "dll_sha256": sha256(self.dll)}))

    def test_default_never_copies_leftover_trace_dependency(self):
        self.receipt(None)
        self.session.install_mod()
        self.assertEqual([p.name for p in self.cfg.mod_dir.iterdir()], ["Cs1Harness.dll"])
        self.assertNotIn("disposable_trace", self.session.receipt)

    def test_foreign_host_rejected_before_install_writes(self):
        self.receipt({"enabled": True, "disposable_only": True})
        self.cfg.host = "carbon"
        with self.assertRaisesRegex(HarnessError, "trace binding mismatch"):
            self.session.install_mod()
        self.assertFalse(self.cfg.mod_dir.exists())

    def test_bad_dependency_rejected_before_install_writes(self):
        self.receipt({"enabled": True, "disposable_only": True})
        with self.assertRaisesRegex(HarnessError, "trace binding mismatch"):
            self.session.install_mod()
        self.assertFalse(self.cfg.mod_dir.exists())


if __name__ == "__main__":
    unittest.main()
