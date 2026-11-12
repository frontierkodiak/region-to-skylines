"""Capture ownership guards without opening a real display."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs1_harness.client import HarnessError
from cs1_harness.x11 import GameWindow


class WindowOwnerTests(unittest.TestCase):
    def session(self, display=":57", lock=None, alive=None):
        return SimpleNamespace(cfg=SimpleNamespace(display=display), lock_fd=lock, alive=lambda: alive)

    def test_rejects_missing_closed_lock_and_human_display_before_connecting(self):
        open_lock = SimpleNamespace(closed=False)
        with patch.object(GameWindow, "_open") as connect:
            for session in [
                self.session(),
                self.session(lock=SimpleNamespace(closed=True)),
                self.session(":0", open_lock),
            ]:
                with self.assertRaises(HarnessError):
                    GameWindow.from_session(session)
            connect.assert_not_called()

    def test_live_foreground_owner_only_connects_to_its_display(self):
        session = self.session(lock=SimpleNamespace(closed=False))
        with patch.object(GameWindow, "_open") as connect:
            GameWindow.from_session(session)
            connect.assert_called_once_with(":57")
        with patch.object(GameWindow, "_open") as connect:
            with self.assertRaises(HarnessError):
                GameWindow.from_session(self.session(lock=SimpleNamespace(closed=False), alive=False))
            connect.assert_not_called()
