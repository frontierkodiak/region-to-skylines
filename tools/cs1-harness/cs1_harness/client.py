"""Line-delimited JSON client for the harness mod's loopback socket."""

from __future__ import annotations

import json
import socket
import time


class HarnessError(RuntimeError):
    pass


class Client:
    def __init__(self, port: int, timeout: float = 150.0):
        self.port = port
        self.timeout = timeout

    def call(self, op: str, **args) -> dict:
        request = json.dumps({"op": op, **args}) + "\n"
        with socket.create_connection(("127.0.0.1", self.port), timeout=self.timeout) as s:
            s.sendall(request.encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(1 << 16)
                if not chunk:
                    break
                buf += chunk
        if not buf:
            raise HarnessError(f"{op}: connection closed without a reply")
        reply = json.loads(buf)
        if not reply.get("ok"):
            raise HarnessError(f"{op}: {reply.get('error')}")
        return reply

    def try_status(self) -> dict | None:
        try:
            return self.call("status")
        except (OSError, ValueError, HarnessError):
            return None

    def wait(self, predicate, timeout: float, what: str, poll: float = 2.0, alive=None) -> dict:
        """Poll status until predicate(status) holds; alive() may abort early."""
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            if alive is not None:
                alive()
            last = self.try_status()
            if last is not None and predicate(last):
                return last
            time.sleep(poll)
        raise HarnessError(f"timed out after {timeout:.0f} s waiting for {what}; last status: {last}")
