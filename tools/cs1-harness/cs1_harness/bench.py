"""Does watching slow the game? A/B/A windows with the observers off, on, off.

Each window measures simulation frames per second, the mod's smoothed render
frame time, and CPU used by the game and by the observer processes. "On" means
the timelapse grabber, the live page writer, and x11vnc with a viewer attached
that keeps requesting updates, which is the most the watch feature costs.
"""

from __future__ import annotations

import contextlib
import os
import socket
import struct
import subprocess
import threading
import time

from . import observe
from .client import Client
from .session import game_pids

CLK = os.sysconf("SC_CLK_TCK")


def cpu_seconds(pids: list[int]) -> float:
    total = 0.0
    for pid in pids:
        with contextlib.suppress(FileNotFoundError, ProcessLookupError):
            fields = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
            total += (int(fields[11]) + int(fields[12])) / CLK
    return total


def unit_pids(units: list[str]) -> list[int]:
    pids = []
    for u in units:
        r = subprocess.run(
            ["systemctl", "--user", "show", "-p", "MainPID", "--value", u], capture_output=True, text=True
        )
        pid = int(r.stdout.strip() or 0)
        if pid:
            pids.append(pid)
            out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout
            pids += [int(x) for x in out.split()]
    return pids


class Viewer(threading.Thread):
    """Minimal RFB 3.8 client: VNC auth, raw encoding, incremental update requests, data discarded."""

    def __init__(self, port: int, password: str):
        super().__init__(daemon=True)
        self.port, self.password = port, password
        self.stop_event = threading.Event()
        self.bytes = 0
        self.error = None

    def recv(self, s, n):
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("closed")
            buf += chunk
        return buf

    def run(self):
        try:
            from Crypto.Cipher import DES  # pycryptodome: uv run --with pycryptodome

            s = socket.create_connection(("127.0.0.1", self.port), 10)
            self.recv(s, 12)
            s.sendall(b"RFB 003.008\n")
            types = self.recv(s, self.recv(s, 1)[0])
            if 2 not in types:
                raise RuntimeError(f"no VNC auth offered: {list(types)}")
            s.sendall(b"\x02")
            challenge = self.recv(s, 16)
            key = bytes(int(f"{b:08b}"[::-1], 2) for b in self.password.encode().ljust(8, b"\0")[:8])
            s.sendall(DES.new(key, DES.MODE_ECB).encrypt(challenge))
            if struct.unpack(">I", self.recv(s, 4))[0] != 0:
                raise RuntimeError("VNC auth failed")
            s.sendall(b"\x01")  # shared
            w, h = struct.unpack(">HH", self.recv(s, 4))
            pf = self.recv(s, 16)
            self.recv(s, struct.unpack(">I", self.recv(s, 4))[0])
            bpp = pf[0] // 8
            s.sendall(struct.pack(">BxHi", 2, 1, 0))  # SetEncodings: raw
            s.sendall(struct.pack(">BBHHHH", 3, 0, 0, 0, w, h))
            while not self.stop_event.is_set():
                kind = self.recv(s, 1)[0]
                if kind != 0:
                    continue
                self.recv(s, 1)
                (n,) = struct.unpack(">H", self.recv(s, 2))
                for _ in range(n):
                    x, y, rw, rh, enc = struct.unpack(">HHHHi", self.recv(s, 12))
                    self.recv(s, rw * rh * bpp)
                    self.bytes += rw * rh * bpp
                s.sendall(struct.pack(">BBHHHH", 3, 1, 0, 0, w, h))
            s.close()
        except Exception as e:  # noqa: BLE001 - reported in the bench result
            self.error = repr(e)


def window(client: Client, seconds: float, observer_units: list[str]) -> dict:
    game = game_pids()
    st0, t0 = client.call("stats"), time.monotonic()
    g0, o0 = cpu_seconds(game), cpu_seconds(unit_pids(observer_units))
    frame_ms = []
    while time.monotonic() - t0 < seconds:
        time.sleep(5)
        frame_ms.append(client.call("status")["frame_ms"])
    st1, t1 = client.call("stats"), time.monotonic()
    g1, o1 = cpu_seconds(game), cpu_seconds(unit_pids(observer_units))
    dt = t1 - t0
    return {
        "seconds": round(dt, 1),
        "sim_frames_per_s": round((st1["frame"] - st0["frame"]) / dt, 1),
        "frame_ms_mean": round(sum(frame_ms) / len(frame_ms), 2),
        "game_cpu_pct": round(100 * (g1 - g0) / dt, 1),
        "observer_cpu_pct": round(100 * (o1 - o0) / dt, 1),
    }


def run(session, seconds: float = 60) -> dict:
    cfg, client = session.cfg, session.client
    units = [cfg.rec_unit, cfg.live_unit, cfg.vnc_unit]
    out = {"off_1": window(client, seconds, units)}
    observe.start(session, record=True, live=True, label=session.label or "observer bench")
    info = observe.watch_start(session)
    time.sleep(3)
    viewer = Viewer(info["port"], info["password"])
    viewer.start()
    out["on"] = window(client, seconds, units)
    viewer.stop_event.set()
    out["on"]["viewer_mb_per_s"] = round(viewer.bytes / 1e6 / out["on"]["seconds"], 1)
    out["on"]["viewer_error"] = viewer.error
    for u in units:
        subprocess.run(["systemctl", "--user", "stop", u], check=False)
    out["off_2"] = window(client, seconds, units)
    return out


SPEED_SETTINGS = [
    ("default", {"fps": 0, "camera": True}),
    ("fps10", {"fps": 10, "camera": True}),
    ("fps2", {"fps": 2, "camera": True}),
    ("camera_off", {"fps": 2, "camera": False}),
    ("default_again", {"fps": 0, "camera": True}),
]


def speed(session, seconds: float = 45) -> dict:
    """Simulation frames per second at speed 3 with drawing throttled in steps, then restored."""
    client = session.client
    out = {}
    for name, setting in SPEED_SETTINGS:
        applied = client.call("render", **setting)
        time.sleep(5)  # let the frame rate settle
        out[name] = {**window(client, seconds, []), "render": applied}
        out[name].pop("observer_cpu_pct", None)
    client.call("render", fps=0, camera=True)
    base = (out["default"]["sim_frames_per_s"] + out["default_again"]["sim_frames_per_s"]) / 2
    for name in out:
        out[name]["vs_default"] = round(out[name]["sim_frames_per_s"] / base, 3) if base else None
    return out
