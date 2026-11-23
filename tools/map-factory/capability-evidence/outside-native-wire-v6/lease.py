"""Keep an owned worker's existing flock alive through external cancellation.

Linux pidfd_getfd duplicates the SAME open-file description. Reopening the lock
path does not. This changes no queue, permission, ptrace setting or guard.
"""

import ctypes
import fcntl
import os
from pathlib import Path
import platform

from loopback_fixture import identity
from wire import Unknown


class Lease:
    def __init__(self, birth, path):
        self.birth, self.path = birth, Path(path)
        self.fd = None

    def pin(self):
        if self.fd is not None:
            return True
        if platform.machine() != "x86_64" or identity(self.birth["pid"]) != self.birth:
            raise Unknown("lease owner identity/platform unavailable")
        try:
            target = self.path.stat()
            candidates = list(Path(f"/proc/{self.birth['pid']}/fd").iterdir())
        except FileNotFoundError:
            return False
        libc = ctypes.CDLL(None, use_errno=True)
        pidfd = libc.syscall(
            ctypes.c_long(434), ctypes.c_int(self.birth["pid"]), ctypes.c_uint(0)
        )
        if pidfd < 0:
            raise Unknown("pidfd_open unavailable; no guard workaround")
        try:
            for candidate in candidates:
                try:
                    stat = candidate.stat()
                    if (stat.st_dev, stat.st_ino) != (target.st_dev, target.st_ino):
                        continue
                    fd = libc.syscall(
                        ctypes.c_long(438),
                        ctypes.c_int(pidfd),
                        ctypes.c_int(int(candidate.name)),
                        ctypes.c_uint(0),
                    )
                    if fd < 0:
                        raise Unknown("pidfd_getfd unavailable; no permission changes")
                    same = os.fstat(fd)
                    if identity(self.birth["pid"]) != self.birth or (
                        same.st_dev,
                        same.st_ino,
                    ) != (target.st_dev, target.st_ino):
                        os.close(fd)
                        raise Unknown("lease identity changed while duplicating")
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        os.close(fd)
                        return False
                    self.fd = fd
                    return True
                except FileNotFoundError:
                    continue
            return False
        finally:
            os.close(pidfd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
