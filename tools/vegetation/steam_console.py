"""Owned Steam-only console session for authorized Workshop downloads on blade.

No game, subscription, purchase, publishing or credential input operations.
Control actions are explicit files in the experiment directory. Never use :0.
"""

from __future__ import annotations

import argparse
import ctypes as c
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cs1-harness"))


class Input:
    def __init__(self, display, delay=0.025):
        if display == ":0":
            raise ValueError("Not a private display")
        self.x = c.CDLL("libX11.so.6")
        self.delay = delay
        self.t = c.CDLL("libXtst.so.6")
        self.x.XOpenDisplay.argtypes = [c.c_char_p]
        self.x.XOpenDisplay.restype = c.c_void_p
        self.x.XStringToKeysym.argtypes = [c.c_char_p]
        self.x.XStringToKeysym.restype = c.c_ulong
        self.x.XKeysymToKeycode.argtypes = [c.c_void_p, c.c_ulong]
        self.x.XKeysymToKeycode.restype = c.c_uint
        self.x.XFlush.argtypes = [c.c_void_p]
        self.t.XTestFakeMotionEvent.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_ulong]
        self.t.XTestFakeButtonEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
        self.t.XTestFakeKeyEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
        self.d = self.x.XOpenDisplay(display.encode())
        if not self.d:
            raise ValueError("Private display unavailable")

    def key(self, *names):
        codes = [self.x.XKeysymToKeycode(self.d, self.x.XStringToKeysym(n.encode())) for n in names]
        if not all(codes):
            raise ValueError("Unknown key")
        for code in codes:
            self.t.XTestFakeKeyEvent(self.d, code, 1, 0)
        self.x.XFlush(self.d)
        time.sleep(self.delay)
        for code in reversed(codes):
            self.t.XTestFakeKeyEvent(self.d, code, 0, 0)
        self.x.XFlush(self.d)

    def text(self, text):
        if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_ ./-" for ch in text):
            raise ValueError("Only Workshop command ASCII is permitted")
        for ch in text:
            if ch == "_":
                self.key("Shift_L", "minus")
            else:
                self.key({" ": "space", ".": "period", "/": "slash", "-": "minus"}.get(ch, ch))

    def click(self, x, y):
        self.t.XTestFakeMotionEvent(self.d, -1, x, y, 0)
        self.x.XFlush(self.d)
        time.sleep(0.1)
        self.t.XTestFakeButtonEvent(self.d, 1, 1, 0)
        self.x.XFlush(self.d)
        time.sleep(0.1)
        self.t.XTestFakeButtonEvent(self.d, 1, 0, 0)
        self.x.XFlush(self.d)


def run(out, duration, wait_minutes):
    from cs1_harness.cli import slot, staging
    from cs1_harness.config import Config
    from cs1_harness import audio

    if socket.gethostname().split(".")[0] != "blade":
        raise ValueError("Downloads use blade's private harness session")
    out.mkdir(parents=True, exist_ok=False)
    cfg = Config.for_host()
    with slot(
        cfg,
        staging(cfg, out),
        wait_minutes,
        {
            "issue": "PL-1326",
            "label": "Authorized Steam-only Workshop acquisition",
            "eta_minutes": duration / 60,
        },
    ) as s:
        before = set(s.steam.instances())
        env = s.steam.base_env()
        unit_env = {
            k: env[k] for k in ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", *audio.environment(cfg))
        }
        s.unit(
            cfg.steam_unit,
            *s.steam.steam_argv(["-console"]),
            env=unit_env,
            props=["-p", "KillMode=control-group"],
        )
        control = Input(cfg.display)
        deadline = time.monotonic() + duration
        seen = set()
        while time.monotonic() < deadline:
            s.our_instances |= set(s.steam.instances()) - before
            for path in sorted(out.glob("action-*.json")):
                if path.name in seen:
                    continue
                action = json.loads(path.read_text())
                if action.get("stop"):
                    deadline = 0
                    break
                if "click" in action:
                    x, y = action["click"]
                    if not 0 <= x < cfg.width or not 0 <= y < cfg.height:
                        raise ValueError("Click outside private display")
                    control.click(x, y)
                if "text" in action:
                    if not re.fullmatch(r"workshop_download_item 255710 [0-9]+", action["text"]):
                        raise ValueError("Not a Workshop download command")
                    control.text(action["text"])
                if "keys" in action:
                    control.key(*action["keys"])
                time.sleep(1)
                subprocess.run(
                    ["import", "-display", cfg.display, "-window", "root", str(out / (path.stem + ".png"))],
                    check=True,
                )
                seen.add(path.name)
                print("action complete", path.name, flush=True)
            time.sleep(0.5)
    (out / "session-receipt.json").write_text(json.dumps(s.receipt, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--duration", type=int, default=3600)
    p.add_argument("--wait-minutes", type=float, default=45)
    a = p.parse_args()
    run(a.out, a.duration, a.wait_minutes)
