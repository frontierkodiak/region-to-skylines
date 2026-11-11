"""Observe and drive only the game window in a named, private harness session.

This does not answer Steam prompts. It exists for strict --disableMods checks,
where the in-game control socket intentionally does not exist.
"""

from __future__ import annotations

import ctypes as c
import json
import pathlib
import subprocess
import time

from .client import HarnessError
from .config import Config


class GameWindow:
    def __init__(self, expected_stage: str):
        cfg = Config.for_host()
        state = json.loads(cfg.state_file.read_text())
        if pathlib.Path(state["stage"]).name != expected_stage or state["display"] == ":0":
            raise HarnessError("not the requested private harness session")
        self._open(state["display"])

    @classmethod
    def from_session(cls, session):
        """An active foreground Session already owns the private display lock."""
        if session.lock_fd is None or session.lock_fd.closed or session.cfg.display == ":0":
            raise HarnessError("window capture requires an owned private Session")
        if session.alive() is False:
            raise HarnessError("game process ended before window capture")
        window = cls.__new__(cls)
        window._open(session.cfg.display)
        return window

    def _open(self, display_name):
        self.display_name = display_name
        self.x = c.CDLL("libX11.so.6")
        self.xt = c.CDLL("libXtst.so.6")
        self.x.XOpenDisplay.argtypes = [c.c_char_p]
        self.x.XOpenDisplay.restype = c.c_void_p
        self.x.XDefaultRootWindow.argtypes = [c.c_void_p]
        self.x.XDefaultRootWindow.restype = c.c_ulong
        self.x.XQueryTree.argtypes = [
            c.c_void_p,
            c.c_ulong,
            c.POINTER(c.c_ulong),
            c.POINTER(c.c_ulong),
            c.POINTER(c.POINTER(c.c_ulong)),
            c.POINTER(c.c_uint),
        ]
        self.x.XFetchName.argtypes = [c.c_void_p, c.c_ulong, c.POINTER(c.c_void_p)]
        self.x.XFree.argtypes = [c.c_void_p]
        self.x.XTranslateCoordinates.argtypes = [
            c.c_void_p,
            c.c_ulong,
            c.c_ulong,
            c.c_int,
            c.c_int,
            c.POINTER(c.c_int),
            c.POINTER(c.c_int),
            c.POINTER(c.c_ulong),
        ]
        self.x.XSetInputFocus.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_ulong]
        self.x.XGetGeometry.argtypes = [
            c.c_void_p,
            c.c_ulong,
            c.POINTER(c.c_ulong),
            c.POINTER(c.c_int),
            c.POINTER(c.c_int),
            c.POINTER(c.c_uint),
            c.POINTER(c.c_uint),
            c.POINTER(c.c_uint),
            c.POINTER(c.c_uint),
        ]
        self.x.XStringToKeysym.argtypes = [c.c_char_p]
        self.x.XStringToKeysym.restype = c.c_ulong
        self.x.XKeysymToKeycode.argtypes = [c.c_void_p, c.c_ulong]
        self.x.XKeysymToKeycode.restype = c.c_uint
        self.x.XFlush.argtypes = [c.c_void_p]
        self.x.XCloseDisplay.argtypes = [c.c_void_p]
        self.xt.XTestFakeMotionEvent.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_ulong]
        self.xt.XTestFakeButtonEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
        self.xt.XTestFakeKeyEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
        self.display = self.x.XOpenDisplay(self.display_name.encode())
        if not self.display:
            raise HarnessError("cannot open the private harness display")
        self.root = self.x.XDefaultRootWindow(self.display)
        pending, matches = [self.root], []
        while pending:
            window = pending.pop()
            name = c.c_void_p()
            if self.x.XFetchName(self.display, window, c.byref(name)) and name:
                title = c.string_at(name).decode(errors="replace")
                self.x.XFree(name)
                if title == "Cities: Skylines":
                    matches.append(window)
            root, parent, children, count = c.c_ulong(), c.c_ulong(), c.POINTER(c.c_ulong)(), c.c_uint()
            if self.x.XQueryTree(
                self.display, window, c.byref(root), c.byref(parent), c.byref(children), c.byref(count)
            ):
                pending.extend(children[i] for i in range(count.value))
                if children:
                    self.x.XFree(children)
        if len(matches) != 1:
            self.close()
            raise HarnessError(f"expected one Cities: Skylines window, found {len(matches)}")
        self.window = matches[0]

    def capture(self, path: pathlib.Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["import", "-display", self.display_name, "-window", str(self.window), str(path)], check=True)

    def click(self, x: int, y: int):
        root, left, top = c.c_ulong(), c.c_int(), c.c_int()
        width, height, border, depth = c.c_uint(), c.c_uint(), c.c_uint(), c.c_uint()
        self.x.XGetGeometry(
            self.display,
            self.window,
            c.byref(root),
            c.byref(left),
            c.byref(top),
            c.byref(width),
            c.byref(height),
            c.byref(border),
            c.byref(depth),
        )
        if not (0 <= x < width.value and 0 <= y < height.value):
            raise HarnessError("click is outside the game window")
        rx, ry, child = c.c_int(), c.c_int(), c.c_ulong()
        self.x.XTranslateCoordinates(
            self.display, self.window, self.root, 0, 0, c.byref(rx), c.byref(ry), c.byref(child)
        )
        self.x.XSetInputFocus(self.display, self.window, 2, 0)
        self.xt.XTestFakeMotionEvent(self.display, -1, rx.value + x, ry.value + y, 0)
        self.x.XFlush(self.display)
        time.sleep(0.1)
        self.xt.XTestFakeButtonEvent(self.display, 1, 1, 0)
        self.x.XFlush(self.display)
        time.sleep(0.12)
        self.xt.XTestFakeButtonEvent(self.display, 1, 0, 0)
        self.x.XFlush(self.display)

    def keys(self, *names: str):
        codes = [self.x.XKeysymToKeycode(self.display, self.x.XStringToKeysym(name.encode())) for name in names]
        if not all(codes):
            raise HarnessError("unknown X11 key name")
        self.x.XSetInputFocus(self.display, self.window, 2, 0)
        for code in codes:
            self.xt.XTestFakeKeyEvent(self.display, code, 1, 0)
        self.x.XFlush(self.display)
        time.sleep(0.12)
        for code in reversed(codes):
            self.xt.XTestFakeKeyEvent(self.display, code, 0, 0)
        self.x.XFlush(self.display)

    def close(self):
        if self.display:
            self.x.XCloseDisplay(self.display)
            self.display = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
