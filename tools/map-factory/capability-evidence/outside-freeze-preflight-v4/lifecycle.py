"""External post-exit supervisor; fixtures own only finite Python children."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

ROLES = frozenset({"game", "driver", "collector", "auditor", "monitor"})


@dataclass(frozen=True)
class OwnedChild:
    process: subprocess.Popen
    pid: int
    start_ticks: int


def identity(pid):
    try:
        # comm may contain spaces or parentheses; field 22 follows final ')'.
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": int(fields[19])}
    except FileNotFoundError:
        return None


def finalize(children, births):
    """Called by the external owner AFTER every child, including driver, exits."""
    if set(children) != ROLES or set(births) != ROLES:
        raise ValueError("full PID/start role coverage required")
    if os.getpid() in {b["pid"] for b in births.values()}:
        raise ValueError("component cannot attest its own absence")
    if len({(b["pid"], b["start_ticks"]) for b in births.values()}) != len(ROLES):
        raise ValueError("distinct process identities required")
    cleanup = {}
    exits = {}
    after_exit = {}
    for role, owned in children.items():
        child = owned.process
        birth = births[role]
        if birth != {"pid": owned.pid, "start_ticks": owned.start_ticks}:
            raise ValueError("birth identity differs from supervisor capture: " + role)
        if child.pid != birth["pid"] or child.poll() is None:
            raise ValueError("post-exit finalization required: " + role)
        after_exit[role] = identity(child.pid)
        if after_exit[role] == birth:
            raise ValueError("owned birth identity still present: " + role)
        cleanup[role] = dict(birth, gone=True)
        exits[role] = child.returncode
    return {
        "stage": "AfterDriverExit",
        "supervisor": identity(os.getpid()),
        "births": births,
        "cleanup": cleanup,
        "exit_codes": exits,
        "after_exit_identities": after_exit,
        "fixture": "CONSTRUCTED Python processes, not game observations",
    }


@contextmanager
def finite_fixture():
    children = {}
    births = {}
    try:
        # Input handoff keeps births observable; timer guarantees finite exit.
        code = (
            "import sys,threading; "
            "threading.Timer(10, lambda: __import__('os')._exit(3)).start(); "
            "sys.stdin.readline(); __import__('os')._exit(0)"
        )
        for role in sorted(ROLES):
            child = subprocess.Popen(
                [sys.executable, "-c", code], stdin=subprocess.PIPE
            )
            births[role] = identity(child.pid)
            # Register before validating so finally always collects this child.
            children[role] = OwnedChild(
                child, child.pid, births[role]["start_ticks"] if births[role] else 0
            )
            if births[role] is None:
                raise ValueError("fixture exited before birth capture")
        yield children, births
    finally:
        for owned in children.values():
            child = owned.process
            if child.poll() is None:
                try:
                    child.stdin.write(b"exit\n")
                    child.stdin.flush()
                except BrokenPipeError:
                    pass
        for owned in children.values():
            child = owned.process
            try:
                child.wait(timeout=12)
            except subprocess.TimeoutExpired:
                child.kill()  # Exact owned Python child; never foreign process.
                child.wait()
            child.stdin.close()


def fixture_receipt():
    with finite_fixture() as (children, births):
        for owned in children.values():
            child = owned.process
            child.stdin.write(b"exit\n")
            child.stdin.flush()
        for owned in children.values():
            owned.process.wait(timeout=12)
        return finalize(children, births)
