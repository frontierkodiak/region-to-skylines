"""A missing or mismatched runtime must never qualify as a build-bound run."""

import copy
import unittest

from cs1_harness.runtime_identity import validate_identity


class RuntimeIdentityTest(unittest.TestCase):
    def test_exact_runtime_and_fail_closed_variants(self):
        build = {
            "game_executable_sha256": "exe",
            "game_assemblies": {"Assembly-CSharp.dll": "game"},
            "dll_sha256": "mod",
        }
        identity = {
            "executable": {"sha256": "exe"},
            "assemblies": [
                {"path": "/game/Assembly-CSharp.dll", "sha256": "game"},
                {"path": "/mod/Cs1Harness.dll", "sha256": "mod"},
            ],
        }
        validate_identity(identity, build)
        wrong_exe = copy.deepcopy(identity)
        wrong_exe["executable"]["sha256"] = "other"
        wrong_game = copy.deepcopy(identity)
        wrong_game["assemblies"][0]["sha256"] = "other"
        missing_mod = copy.deepcopy(identity)
        missing_mod["assemblies"].pop()
        for invalid in [wrong_exe, wrong_game, missing_mod]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_identity(invalid, build)
