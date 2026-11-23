"""Portable, real wall-clock socket tests. No game imports, ports or licensed bytes."""

from pathlib import Path
import socket
import tempfile
import time
import unittest

from loopback_fixture import server
from wire import Deadline, Wire, Unknown, decode


class WireTests(unittest.TestCase):
    def exercise(self, row, timeout=0.12, max_bytes=4096):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "server"
            with server([row], directory) as owned:
                trace = []
                start = time.monotonic()
                client = Wire(owned["port"], Deadline.after(timeout), trace, max_bytes)
                try:
                    result = client.call(row["op"])
                except Unknown as error:
                    result = str(error)
                elapsed = time.monotonic() - start
            calls = decode((directory / "calls.json").read_bytes())
            self.assertIsNone(owned["after"])
            self.assertEqual(owned["exit_code"], 0)
            self.assertEqual(len(calls), 1)
            self.assertLess(elapsed, 0.75)
            return result, trace, calls, elapsed

    def test_success_protocol(self):
        result, trace, calls, _ = self.exercise(
            dict(op="status", reply=dict(ok=True, loading=False))
        )
        self.assertEqual(result, dict(ok=True, loading=False))
        self.assertEqual(calls[0]["request"], dict(op="status"))
        self.assertGreater(trace[0]["sent_bytes"], 0)

    def test_blocked_read_has_actual_server_evidence(self):
        result, trace, calls, elapsed = self.exercise(
            dict(op="stats", reply=dict(ok=True), mode="blocked")
        )
        self.assertIn("deadline", result)
        self.assertGreater(elapsed, 0.09)
        self.assertGreater(calls[0]["blocked_until"], trace[0]["ended"])
        self.assertEqual(trace[0]["received_bytes"], 0)

    def test_no_newline_and_drip_share_absolute_deadline(self):
        for mode in ("no-newline", "drip"):
            with self.subTest(mode=mode):
                result, trace, _, elapsed = self.exercise(
                    dict(op="stats", reply=dict(ok=True, data="x" * 100), mode=mode)
                )
                self.assertIn("deadline", result)
                self.assertGreater(trace[0]["received_bytes"], 0)
                self.assertGreater(elapsed, 0.09)

    def test_envelopes_fail_closed(self):
        for raw in (
            '{"ok":false,"error":"no"}\n',
            '{"ok":"false"}\n',
            '{"ok":true,"ok":true}\n',
            '{"ok":true,"nested":{"x":1,"x":2}}\n',
            '{"ok":true,"x":NaN}\n',
            "{bad}\n",
            "[]\n",
            '{"ok":1}\n',
            "{}\n",
            '{"ok":true}\n{}\n',
        ):
            with self.subTest(raw=raw):
                result, trace, _, _ = self.exercise(dict(op="status", raw=raw))
                self.assertIsInstance(result, str)
                self.assertIn("error", trace[0])

    def test_oversize_and_eof(self):
        result, _, _, _ = self.exercise(
            dict(op="status", reply=dict(ok=True, data="x" * 1000)), max_bytes=100
        )
        self.assertIn("oversized", result)
        result, _, _, _ = self.exercise(dict(op="status", raw='{"ok":true}'))
        self.assertIn("missing newline", result)

    def test_expired_budget_makes_no_call(self):
        trace = []
        with self.assertRaises(Unknown):
            Wire(1, Deadline(time.monotonic() - 1), trace).call("path_start")
        self.assertEqual(trace, [])

    def test_blocked_connect_uses_owned_backlog(self):
        # A full accept queue keeps the second handshake pending on Linux.
        listener = socket.socket()
        first = socket.socket()
        trace = []
        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(0)
            first.settimeout(0.5)
            first.connect(listener.getsockname())
            start = time.monotonic()
            with self.assertRaisesRegex(Unknown, "deadline"):
                Wire(listener.getsockname()[1], Deadline.after(0.12), trace).call(
                    "status"
                )
            self.assertGreater(time.monotonic() - start, 0.09)
            self.assertLess(time.monotonic() - start, 0.75)
            self.assertEqual(trace[0]["sent_bytes"], 0)
            accepted, _ = listener.accept()
            accepted.close()
        finally:
            first.close()
            listener.close()

    def test_minimum_deadline_not_renewed(self):
        parent = Deadline.after(0.04)
        child = Deadline.after(30, parent)
        self.assertEqual(child.end, parent.end)
        time.sleep(0.05)
        with self.assertRaises(Unknown):
            child.remaining()


class ExternalWorkerTests(unittest.TestCase):
    def test_stalled_ignoring_worker_is_killed_and_joined_by_identity(self):
        import sys
        from wire_supervisor import Owned, await_file

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            code = (
                "import signal,time,pathlib,sys; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                "pathlib.Path(sys.argv[1]).write_text('blocked'); time.sleep(30)"
            )
            owned = Owned.start(
                [sys.executable, "-c", code, str(directory / "ready")],
                "collector",
                directory,
            )
            try:
                await_file(directory / "ready", Deadline.after(2), owned.birth)
                started = time.monotonic()
                with self.assertRaises(Unknown):
                    owned.wait(Deadline.after(0.1))
                owned.stop(grace=0.05)
                self.assertLess(time.monotonic() - started, 1)
                self.assertTrue(owned.forced)
                self.assertIsNone(owned.receipt()["after"])
                self.assertNotEqual(owned.receipt()["exit_code"], 0)
            finally:
                owned.stop()

    def test_changed_birth_refuses_kill(self):
        import sys
        from wire_supervisor import Owned

        with tempfile.TemporaryDirectory() as temp:
            owned = Owned.start(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                "collector",
                Path(temp),
            )
            real = owned.birth
            try:
                owned.birth = dict(real, start_ticks=real["start_ticks"] + 1)
                with self.assertRaisesRegex(Unknown, "PID/start changed"):
                    owned.stop()
                self.assertIsNone(owned.process.poll())
            finally:
                owned.birth = real
                owned.stop()

    def test_cancelled_worker_descendants_are_externally_reaped(self):
        import sys
        from wire_supervisor import Owned, await_file, child_reaper
        from loopback_fixture import identity

        with tempfile.TemporaryDirectory() as temp, child_reaper():
            root = Path(temp)
            code = (
                "import subprocess,sys,pathlib,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)"
            )
            owned = Owned.start(
                [sys.executable, "-c", code, str(root / "child")], "collector", root
            )
            try:
                pid = int(await_file(root / "child", Deadline.after(2), owned.birth))
                birth = identity(pid)
                self.assertIsNotNone(birth)
                owned.capture_descendants()
                owned.stop(grace=0.05)
                self.assertIsNone(identity(pid))
                self.assertIsNone(owned.receipt()["after"])
            finally:
                owned.stop()

    def test_external_lease_survives_worker_exit_until_cleanup(self):
        import fcntl
        import sys
        from lease import Lease
        from wire_supervisor import Owned, await_file

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            code = (
                "import pathlib,fcntl,sys,time; f=open(sys.argv[1],'w'); "
                "fcntl.flock(f,fcntl.LOCK_EX); pathlib.Path(sys.argv[2]).write_text('held'); time.sleep(30)"
            )
            owned = Owned.start(
                [sys.executable, "-c", code, str(root / "lock"), str(root / "ready")],
                "collector",
                root,
            )
            lease = Lease(owned.birth, root / "lock")
            try:
                await_file(root / "ready", Deadline.after(2), owned.birth)
                self.assertTrue(lease.pin())
                owned.stop()
                with (root / "lock").open("r") as other:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lease.close()
                    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                owned.stop()
                lease.close()


class ConstructedAuthorityParserTests(unittest.TestCase):
    def test_records_are_exact_separate_and_ordered(self):
        import copy
        from dataclasses import dataclass
        from authority import (
            OWNER,
            TARGET,
            descriptor,
            validate_records,
            ParentAuthority,
        )
        from wire import encoded

        @dataclass
        class FixtureRequest:
            freeze_sha256: str = "f" * 64
            binding: bytes = b"{}"
            session: str = "CONSTRUCTED-parser"
            limits: bytes = b"{}"
            purpose: str = "CONSTRUCTED"

        request = FixtureRequest()
        frozen = dict(source_revision="a" * 40, v5=dict(fresh_build=dict(dll="b" * 64)))

        def record(action, number):
            body = dict(
                schema=6,
                action=action,
                request=descriptor(request),
                target=TARGET,
                source_revision=frozen["source_revision"],
                build_sha256="b" * 64,
            )
            return dict(
                id="CONSTRUCTED-" + str(number),
                author_id=OWNER,
                author_type="agent",
                revision=1,
                created_at=f"2026-11-24T00:00:0{number}Z",
                content=encoded(body).decode(),
            )

        acceptance, budget = record("accept-study", 1), record("authorize-openings", 2)
        self.assertTrue(validate_records(acceptance, budget, request, frozen))
        for mutation in ("actor", "source", "extra", "same", "order"):
            bad = copy.deepcopy(budget)
            if mutation == "actor":
                bad["author_id"] = "caller"
            if mutation in {"source", "extra"}:
                body = decode(bad["content"])
                body["source_revision" if mutation == "source" else "extra"] = "wrong"
                bad["content"] = encoded(body).decode()
            if mutation == "same":
                bad["id"] = acceptance["id"]
            if mutation == "order":
                bad["created_at"] = acceptance["created_at"]
            with self.assertRaises(Unknown):
                validate_records(acceptance, bad, request, frozen)
        # A valid constructed parser result is never native authority.
        with self.assertRaises(Unknown):
            ParentAuthority("x", "y").authorize(request, frozen)


if __name__ == "__main__":
    unittest.main()
