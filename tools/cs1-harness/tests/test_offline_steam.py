"""The lead's failed-offline-sync evidence passes; online records still stop."""

import pathlib
import json
import tempfile
import unittest

from cs1_harness.offline_steam import Guard, OfflineError


OFFLINE = "[2026-11-20 06:14:59] [AppID 7] Failed sync for 'eval,' [login=false][offlineMode=true]\n"
CONFIG = '"users" { "1" { "WantsOfflineMode" "1" "SkipOfflineModeWarning" "1" } }'


class OfflineSteamTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "logs").mkdir()
        self.config = self.root / "config/loginusers.vdf"
        self.log = self.root / "logs/cloud_log.txt"
        self.config.write_text(CONFIG)
        self.log.write_text(OFFLINE)

    def append(self, text):
        with self.log.open("a") as stream:
            stream.write(text)

    def test_lead_evidence_and_more_failed_offline_syncs_pass_without_edits(self):
        before = self.config.read_bytes()
        guard = Guard(self.root)
        self.append("Cloud client initialized\n" + OFFLINE)
        self.assertEqual(guard.check()["fresh_syncs"], 1)
        self.assertEqual(self.config.read_bytes(), before)

    def test_flags_alone_are_not_proof(self):
        self.log.write_text("Cloud client initialized\n")
        with self.assertRaisesRegex(OfflineError, "no timestamped"):
            Guard(self.root)

    def test_evidence_and_failures_do_not_publish_account_or_sync_names(self):
        secret = "private-account-and-save-name"
        self.config.write_text(CONFIG.replace('"WantsOfflineMode"', f'"AccountName" "{secret}" "WantsOfflineMode"'))
        self.log.write_text(OFFLINE.replace("eval,", secret))
        guard = Guard(self.root)
        self.assertNotIn(secret, json.dumps(guard.check()))
        self.append(OFFLINE.replace("eval,", secret).replace("login=false", "login=true"))
        with self.assertRaises(OfflineError) as error:
            guard.check()
        self.assertNotIn(secret, str(error.exception))

    def test_latest_offline_transition_can_supersede_historical_online_mode(self):
        historical = OFFLINE.replace("06:14:59", "05:00:00").replace("login=false", "login=true")
        self.log.write_text(historical + OFFLINE)
        Guard(self.root).check()

    def test_any_online_record_in_latest_batch_stops(self):
        for text in (
            OFFLINE.replace("login=false", "login=true"),
            OFFLINE.replace("offlineMode=true", "offlineMode=false"),
        ):
            self.log.write_text(text + OFFLINE)
            with self.assertRaisesRegex(OfflineError, "login=true or offlineMode=false"):
                Guard(self.root)

    def test_new_online_record_cannot_be_erased_by_later_offline_record(self):
        guard = Guard(self.root)
        self.append(OFFLINE.replace("login=false", "login=true") + OFFLINE)
        with self.assertRaisesRegex(OfflineError, "login=true or offlineMode=false"):
            guard.check()

    def test_online_record_stops_even_before_its_newline(self):
        guard = Guard(self.root)
        self.append(OFFLINE.replace("offlineMode=true", "offlineMode=false").rstrip())
        with self.assertRaisesRegex(OfflineError, "login=true or offlineMode=false"):
            guard.check()

    def test_config_change_during_game_stops(self):
        guard = Guard(self.root)
        self.config.write_text(CONFIG.replace('"WantsOfflineMode" "1"', '"WantsOfflineMode" "0"'))
        with self.assertRaisesRegex(OfflineError, "does not request offline"):
            guard.check()

    def test_ambiguous_accounts_and_incomplete_state_cannot_pass(self):
        for text in (
            "[2026-11-20 06:14:59] Failed sync [offlineMode=true]\n",
            OFFLINE.replace("login=false", "login=unknown"),
        ):
            self.log.write_text(text)
            with self.assertRaises(OfflineError):
                Guard(self.root)
        self.log.write_text(OFFLINE)
        self.config.write_text('"users" { "1" {} "2" {} }')
        with self.assertRaisesRegex(OfflineError, "unambiguous"):
            Guard(self.root)

    def test_rotation_or_truncation_breaks_audit_continuity(self):
        guard = Guard(self.root)
        self.log.write_text("")
        with self.assertRaisesRegex(OfflineError, "rotated or truncated"):
            guard.check()


if __name__ == "__main__":
    unittest.main()
