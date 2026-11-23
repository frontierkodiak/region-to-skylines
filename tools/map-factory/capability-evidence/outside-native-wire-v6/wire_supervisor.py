"""External owner of finite workers. No process-name or process-group termination."""

from dataclasses import dataclass
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

    def stop(self, grace=0.5):
        child = self.process
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
