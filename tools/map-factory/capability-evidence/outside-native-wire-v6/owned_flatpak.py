"""Owned Flatpak helper. Instance identity travels on a dedicated inherited FD.

Only native_session installs this shim, after external parent authorization.
No Steam, game or Flatpak command is executed by off-game fixture verification.
"""

import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time

from loopback_fixture import identity
from wire import Deadline, Unknown
from wire_supervisor import atomic


def main():
    record, end, *argv = sys.argv[1:]
    deadline = Deadline(float(end))
    if argv[:2] != ["/usr/bin/flatpak", "run"]:
        raise Unknown("expected reviewed Flatpak run protocol")
    readfd, writefd = os.pipe()
    os.set_blocking(readfd, False)
    cmd = [*argv[:2], "--instance-id-fd=" + str(writefd), *argv[2:]]
    child = subprocess.Popen(cmd, pass_fds=(writefd,))
    birth = identity(child.pid)
    os.close(writefd)
    state = dict(
        kind="NATIVE", launcher=birth, instance=None, identity=None, error=None
    )
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    raw = bytearray()
    try:
        while child.poll() is None:
            deadline.remaining()
            ready, _, _ = select.select(
                [readfd], [], [], min(0.02, deadline.remaining())
            )
            if ready:
                data = os.read(readfd, 256)
                raw.extend(data)
                if len(raw) > 128:
                    raise Unknown("oversized Flatpak instance identity")
                if (
                    raw
                    and (not data or raw.endswith(b"\n"))
                    and state["instance"] is None
                ):
                    instance = raw.decode().strip()
                    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", instance):
                        raise Unknown("invalid Flatpak instance identity")
                    state["instance"] = instance
                    r = subprocess.run(
                        ["flatpak", "ps", "--columns=instance,pid,application"],
                        capture_output=True,
                        timeout=2,
                        check=True,
                    )
                    matches = [
                        line.split()
                        for line in r.stdout.decode().splitlines()
                        if line.split() and line.split()[0] == instance
                    ]
                    if (
                        len(matches) != 1
                        or len(matches[0]) != 3
                        or matches[0][2] != "com.valvesoftware.Steam"
                    ):
                        raise Unknown("cannot bind owned Flatpak instance")
                    state["identity"] = identity(int(matches[0][1]))
                    if state["identity"] is None:
                        raise Unknown("owned Flatpak process missing")
                    atomic(Path(record), state)
            if stopping:
                break
            time.sleep(0.005)
    except BaseException as error:
        state["error"] = str(error)
    finally:
        atomic(Path(record), state)
        if child.poll() is None:
            if birth is None or identity(child.pid) != birth:
                raise Unknown("refuse launcher kill: PID/start changed")
            child.terminate()
            try:
                child.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                if identity(child.pid) != birth:
                    raise Unknown("launcher identity changed")
                child.kill()
                child.wait(timeout=2)
        state["launcher_exit"] = child.returncode
        state["launcher_after"] = identity(child.pid)
        atomic(Path(record), state)
        os.close(readfd)


if __name__ == "__main__":
    main()
