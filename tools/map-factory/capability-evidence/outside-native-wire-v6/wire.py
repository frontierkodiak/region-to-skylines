"""Harness-compatible line JSON, with one absolute deadline and no worker threads."""

from dataclasses import dataclass
import errno
import hashlib
import json
import math
import select
import socket
import time


class Unknown(ValueError):
    """Stop; this operation must not be retried or replaced."""


class Unavailable(Unknown):
    """A status listener has not started yet; no request bytes were sent."""


@dataclass(frozen=True)
class Deadline:
    end: float

    @classmethod
    def after(cls, seconds, *parents):
        if (
            type(seconds) not in (int, float)
            or not math.isfinite(seconds)
            or seconds <= 0
        ):
            raise Unknown("invalid deadline")
        return cls(min([time.monotonic() + seconds, *(p.end for p in parents)]))

    def remaining(self):
        left = self.end - time.monotonic()
        if left <= 0:
            raise Unknown("absolute deadline expired")
        return left

    def pause(self, seconds):
        time.sleep(min(seconds, self.remaining()))
        self.remaining()


def pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise Unknown("duplicate JSON key: " + key)
        value[key] = item
    return value


def decode(data):
    try:
        return json.loads(
            data,
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                Unknown("nonfinite JSON")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise Unknown("malformed JSON") from error


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


class Wire:
    """Port must come from the injected owner, never discovery or a default."""

    def __init__(self, port, deadline, trace=None, max_bytes=8 * 1024 * 1024):
        if type(port) is not int or not 0 < port < 65536:
            raise Unknown("explicit port required")
        self.port, self.deadline = port, deadline
        self.trace = trace if trace is not None else []
        self.max_bytes = max_bytes

    def wait_socket(self, sock, write):
        readable, writable, failed = select.select(
            [] if write else [sock],
            [sock] if write else [],
            [sock],
            self.deadline.remaining(),
        )
        self.deadline.remaining()
        if failed or not (writable if write else readable):
            raise Unknown("socket readiness failure")

    def call(self, op, **args):
        if type(op) is not str or "op" in args:
            raise Unknown("invalid operation")
        self.deadline.remaining()
        request = encoded(dict(op=op, **args)) + b"\n"
        event = dict(
            op=op, args=args, started=time.monotonic(), sent_bytes=0, received_bytes=0
        )
        self.trace.append(event)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        buf = bytearray()
        try:
            code = sock.connect_ex(("127.0.0.1", self.port))
            if code not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY):
                raise OSError(code, "connect refused")
            if code:
                self.wait_socket(sock, True)
                code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if code:
                    raise OSError(code, "connect failed")
            while event["sent_bytes"] < len(request):
                self.wait_socket(sock, True)
                try:
                    count = sock.send(request[event["sent_bytes"] :])
                except BlockingIOError:
                    continue
                if not count:
                    raise Unknown("partial request send")
                event["sent_bytes"] += count
            while b"\n" not in buf:
                self.wait_socket(sock, False)
                try:
                    part = sock.recv(min(65536, self.max_bytes + 1 - len(buf)))
                except BlockingIOError:
                    continue
                if not part:
                    raise Unknown("incomplete reply: missing newline")
                buf.extend(part)
                event["received_bytes"] = len(buf)
                if len(buf) > self.max_bytes:
                    raise Unknown("oversized reply")
            line, tail = bytes(buf).split(b"\n", 1)
            if tail:
                raise Unknown("extra reply bytes")
            reply = decode(line)
            if type(reply) is not dict or type(reply.get("ok")) is not bool:
                raise Unknown("invalid envelope status")
            if reply["ok"] is not True:
                if set(reply) != {"ok", "error"} or type(reply["error"]) is not str:
                    raise Unknown("invalid error envelope")
                raise Unknown("remote refusal: " + reply["error"])
            if op == "status":
                if any(
                    type(reply.get(key)) is not bool for key in ("loading", "in_game")
                ):
                    raise Unknown("invalid status booleans")
                if "plugins" in reply:
                    if type(reply["plugins"]) is not list or any(
                        type(p) is not dict
                        or any(
                            type(p.get(k)) is not bool for k in ("enabled", "builtin")
                        )
                        for p in reply["plugins"]
                    ):
                        raise Unknown("invalid plugin booleans")
            self.deadline.remaining()
            event["reply_sha256"] = hashlib.sha256(encoded(reply)).hexdigest()
            # Network bytes are retained by Transport.graph. Keep the trace bounded.
            if op != "networks":
                event["reply"] = reply
            return reply
        except (OSError, ValueError) as error:
            event["error"] = str(error)
            event["partial_reply_hex"] = bytes(buf[:256]).hex()
            if (
                isinstance(error, OSError)
                and error.errno == errno.ECONNREFUSED
                and event["sent_bytes"] == 0
            ):
                raise Unavailable(str(error)) from error
            raise Unknown(str(error)) from error
        finally:
            sock.close()
            event["ended"] = time.monotonic()

    def wait(self, predicate, timeout, what, poll=0.1, alive=None):
        deadline = Deadline.after(timeout, self.deadline)
        while True:
            deadline.remaining()
            if alive is not None:
                alive()
            original = self.deadline
            self.deadline = deadline
            try:
                try:
                    status = self.call("status")
                except Unavailable:
                    status = None
            finally:
                self.deadline = original
            if status is not None and predicate(status):
                return status
            deadline.pause(poll)

    def try_status(self):
        # Only an absent startup listener is pollable; corrupt/error envelopes
        # remain terminal. Path constructors never use this method.
        try:
            return self.call("status")
        except Unavailable:
            return None
