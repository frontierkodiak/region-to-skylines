"""park_pointer: the requested position reaches XWarpPointer (no X server needed)."""

import ctypes
import types
import unittest
from unittest import mock

from cs1_harness.session import Session


class FakeXlib:
    def __init__(self):
        self.warps = []
        for name in ["XOpenDisplay", "XDefaultRootWindow", "XWarpPointer", "XSync", "XCloseDisplay"]:
            setattr(self, name, mock.MagicMock(name=name))
        self.XOpenDisplay.return_value = 1234
        self.XDefaultRootWindow.return_value = 99
        self.XWarpPointer.side_effect = lambda *a: self.warps.append(a[-2:])


def session():
    s = Session.__new__(Session)
    s.lock_fd = object()
    s.cfg = types.SimpleNamespace(display=":91", width=1920, height=1080)
    s.receipt = {}
    return s


class ParkPointer(unittest.TestCase):
    def test_default_is_centre_and_explicit_point_is_used(self):
        fake = FakeXlib()
        s = session()
        with mock.patch.object(ctypes, "CDLL", return_value=fake):
            s.park_pointer()
            s.park_pointer(40, 40)
        self.assertEqual(fake.warps, [(960, 540), (40, 40)])
        self.assertTrue(all(isinstance(v, int) for w in fake.warps for v in w))
        self.assertEqual(s.receipt["pointer_parked"]["root_position"], [40, 40])

    def test_refuses_the_real_display(self):
        s = session()
        s.cfg.display = ":0"
        with self.assertRaises(Exception):
            s.park_pointer()


if __name__ == "__main__":
    unittest.main()
