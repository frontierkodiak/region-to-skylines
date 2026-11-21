"""An exiting Flatpak helper must settle before the shared slot is released."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from cs1_harness.config import Config
from cs1_harness.session import Session


class SessionCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        env = patch.dict("os.environ", XDG_RUNTIME_DIR=str(self.root / "runtime"))
        env.start()
        self.addCleanup(env.stop)
        cfg = Config.for_host()
        cfg.harness_home = self.root / "home"
        stage = self.root / "stage"
        stage.mkdir()
        self.session = Session(cfg, stage)
        self.session.steam = Mock()
        self.session.steam.base_env.return_value = {}

    def stop(self):
        with (
            patch.object(self.session, "steam_alive", return_value=False),
            patch("cs1_harness.session.game_pids", return_value=[]),
            patch("cs1_harness.session.sh", return_value=subprocess.CompletedProcess([], 3)) as commands,
            patch("cs1_harness.session.observe.mark_idle"),
            patch("cs1_harness.session.time.sleep"),
        ):
            self.session.stop()
        receipt = json.loads((self.session.stage / "session-receipt.json").read_text())
        self.assertFalse(any(call.args[:2] == ("flatpak", "kill") for call in commands.call_args_list))
        return receipt["cleanup"]

    def test_late_helper_exit_is_observed_before_successful_cleanup(self):
        pending = iter([["late-helper"], ["late-helper"]])
        self.session.steam.instances.side_effect = lambda: next(pending, [])
        self.assertEqual(self.stop(), {"game": [], "steam_instances": [], "units_active": []})

    def test_persistent_untracked_instance_is_not_killed_or_hidden(self):
        self.session.steam.instances.return_value = ["not-ours"]
        self.assertEqual(self.stop(), {"game": [], "steam_instances": ["not-ours"], "units_active": []})


if __name__ == "__main__":
    unittest.main()
