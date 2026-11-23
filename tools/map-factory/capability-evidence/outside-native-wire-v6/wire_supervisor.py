"""External owner of finite workers. No process-name or process-group termination."""

from dataclasses import dataclass, field
from contextlib import contextmanager
import ctypes
import functools
import os
import signal
from pathlib import Path
import subprocess
import time

from loopback_fixture import identity
from wire import Unknown, encoded


@dataclass
class Owned:
    process: subprocess.Popen
    birth: dict
    role: str
    forced: bool = False
    descendants: dict = field(default_factory=dict)

    @classmethod
    def start(cls, argv, role, directory):
        log = (directory / (role + ".stderr")).open("wb")
        try:
            child = subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log
            )
        finally:
            log.close()
        birth = identity(child.pid)
        owner = cls(child, birth, role)
        if birth is None:
            child.wait(timeout=2)
            raise Unknown("worker birth unavailable: " + role)
        return owner

    def wait(self, deadline):
        try:
            return self.process.wait(timeout=deadline.remaining())
        except subprocess.TimeoutExpired as error:
            raise Unknown("worker absolute deadline: " + self.role) from error

    def capture_descendants(self):
        if identity(self.process.pid) != self.birth:
            return
        pending = [self.birth]
        while pending:
            parent = pending.pop()
            try:
                children = (
                    Path(f"/proc/{parent['pid']}/task/{parent['pid']}/children")
                    .read_text()
                    .split()
                )
            except FileNotFoundError:
                continue
            for raw in children:
                try:
                    fields = (
                        Path(f"/proc/{raw}/stat").read_text().rsplit(")", 1)[1].split()
                    )
                    birth = dict(pid=int(raw), start_ticks=int(fields[19]))
                    if (
                        int(fields[1]) != parent["pid"]
                        or identity(parent["pid"]) != parent
                    ):
                        continue
                    key = (birth["pid"], birth["start_ticks"])
                    if key not in self.descendants:
                        self.descendants[key] = birth
                        pending.append(birth)
                except FileNotFoundError:
                    continue

    def stop(self, grace=0.5):
        child = self.process
        self.capture_descendants()
        for birth in reversed(tuple(self.descendants.values())):
            signal_owned(birth, signal.SIGTERM)

        if child.poll() is None:
            if identity(child.pid) != self.birth:
                raise Unknown("refuse termination: owned PID/start changed")
            self.forced = True
            child.terminate()
            try:
                child.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                if identity(child.pid) != self.birth:
                    raise Unknown("refuse escalation: owned PID/start changed")
                child.kill()
                child.wait(timeout=2)
        for birth in reversed(tuple(self.descendants.values())):
            if identity(birth["pid"]) == birth:
                signal_owned(birth, signal.SIGKILL)
            end = time.monotonic() + 2
            while identity(birth["pid"]) == birth:
                try:
                    os.waitpid(birth["pid"], os.WNOHANG)
                except ChildProcessError:
                    pass
                if time.monotonic() >= end:
                    raise Unknown("owned descendant not reaped")
                time.sleep(0.01)
        if child.stdin is not None and not child.stdin.closed:
            child.stdin.close()
        if identity(child.pid) == self.birth:
            raise Unknown("owned worker remains present")

    def receipt(self):
        if self.process.poll() is None:
            raise Unknown("cannot attest live worker absence")
        return dict(
            birth=self.birth,
            exit_code=self.process.returncode,
            after=identity(self.process.pid),
            forced=self.forced,
        )


def atomic(path, value):
    """One writer per role, atomic snapshots for the external owner."""
    path = Path(path)
    pending = path.with_suffix(path.suffix + ".partial")
    pending.write_bytes(encoded(value))
    pending.replace(path)


def await_file(path, deadline, producer=None):
    path = Path(path)
    while not path.exists():
        deadline.remaining()
        if producer is not None and identity(producer["pid"]) != producer:
            raise Unknown("producer exited without handoff")
        time.sleep(min(0.01, deadline.remaining()))
    return path.read_bytes()


def signal_owned(birth, signum):
    if identity(birth["pid"]) != birth:
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    fd = libc.syscall(ctypes.c_long(434), ctypes.c_int(birth["pid"]), ctypes.c_uint(0))
    if fd < 0:
        raise Unknown("owned PID handle unavailable")
    try:
        if identity(birth["pid"]) != birth:
            raise Unknown("owned PID/start changed before signal")
        if (
            libc.syscall(
                ctypes.c_long(424),
                ctypes.c_int(fd),
                ctypes.c_int(signum),
                ctypes.c_void_p(),
                ctypes.c_uint(0),
            )
            < 0
        ):
            raise Unknown("owned PID signal failed")
        return True
    finally:
        os.close(fd)


@contextmanager
def child_reaper():
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    if (
        libc.prctl(37, ctypes.byref(previous), 0, 0, 0) != 0
        or libc.prctl(36, 1, 0, 0, 0) != 0
    ):
        raise Unknown("owned-descendant reaping unavailable")
    try:
        yield
    finally:
        libc.prctl(36, previous.value, 0, 0, 0)


def reap_children(function):
    @functools.wraps(function)
    def run(*args, **kwargs):
        with child_reaper():
            return function(*args, **kwargs)

    return run
