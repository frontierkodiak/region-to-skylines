"""A slow carbon gets time to answer, but inconclusive checks never launch."""

import pathlib
import subprocess
import unittest
from unittest.mock import patch

from cs1_harness.config import Config
from cs1_harness.session import Blocked, EX_TEMPFAIL, Session


class CarbonIdleTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(Config.for_host(), pathlib.Path("unused-stage"))

    @patch("cs1_harness.session.sh")
    def test_only_exact_idle_sentinel_passes_with_longer_timeout(self, shell):
        shell.return_value = subprocess.CompletedProcess([], 0, "NO_STEAM_GAME_PROCESS_FOUND\n", "")
        self.session.check_carbon_idle()
        self.assertTrue(self.session.receipt["carbon_preflight"]["idle"])
        self.assertIn("ConnectTimeout=60", shell.call_args.args)
        self.assertEqual(shell.call_args.kwargs["timeout"], 90)

    @patch("cs1_harness.session.sh")
    def test_active_game_network_failure_and_unexpected_output_still_block(self, shell):
        for code, output in [(0, ""), (255, ""), (0, "NO_STEAM_GAME_PROCESS_FOUND\nother")]:
            with self.subTest(code=code, output=output):
                shell.return_value = subprocess.CompletedProcess([], code, output, "")
                with self.assertRaises(Blocked) as error:
                    self.session.check_carbon_idle()
                self.assertEqual(error.exception.code, EX_TEMPFAIL)
                self.assertNotIn("carbon_preflight", self.session.receipt)

    @patch("cs1_harness.session.sh", side_effect=subprocess.TimeoutExpired("ssh", 90))
    def test_hung_remote_process_check_blocks(self, shell):
        with self.assertRaises(Blocked) as error:
            self.session.check_carbon_idle()
        self.assertEqual(error.exception.code, EX_TEMPFAIL)
        self.assertNotIn("carbon_preflight", self.session.receipt)
