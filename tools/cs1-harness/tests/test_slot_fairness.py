"""Isolated queue receipts; no game, host lock, registry or service is touched."""

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from cs1_harness import cli, slots
from cs1_harness.session import Blocked


class SlotFairnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.cfg = SimpleNamespace(runtime_dir=root, lock_file=root / "lock", state_file=root / "session.json")
        self.context = MagicMock()
        self.session = SimpleNamespace(detached=False)
        self.context.__enter__.return_value = self.session
        self.addCleanup(patch.stopall)
        patch("cs1_harness.slots.log_event").start()
        self.constructor = patch("cs1_harness.cli.Session", return_value=self.context).start()

    def test_new_request_cannot_jump_an_older_waiter_even_if_lock_is_free(self):
        waiting = slots.waiter_dir(self.cfg)
        waiting.mkdir()
        # A live PID in an isolated synthetic receipt, not another host's ticket.
        older = waiting / f"{os.getppid()}.json"
        older.write_text(json.dumps({"pid": os.getppid(), "since": 1.0}))
        with self.assertRaises(Blocked):
            with cli.slot(self.cfg, self.cfg.runtime_dir / "new", 0):
                pass
        self.constructor.assert_not_called()
        self.assertTrue(older.exists())
        self.assertFalse((waiting / f"{os.getpid()}.json").exists())

    def test_uncontended_request_acquires_and_cleans_its_queue_receipt(self):
        with cli.slot(self.cfg, self.cfg.runtime_dir / "new", 0) as session:
            self.assertIs(session, self.session)
        self.assertFalse(list(slots.waiter_dir(self.cfg).glob("*.json")))
        self.assertFalse(slots.holder_file(self.cfg).exists())

    def test_nonbusy_preflight_failure_does_not_leave_a_waiter(self):
        self.context.__enter__.side_effect = Blocked("isolated preflight error", 77)
        with self.assertRaises(Blocked):
            with cli.slot(self.cfg, self.cfg.runtime_dir / "new", 1):
                pass
        self.assertFalse(list(slots.waiter_dir(self.cfg).glob("*.json")))
