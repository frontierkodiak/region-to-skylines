"""Steam backends: blade's Flatpak Steam and worm's native Steam.

Both run on the harness display with the harness's private session bus. The
backend decides how commands start (inside the Flatpak sandbox or on the host)
and how to tell whether a Steam is already running.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

from .config import FLATPAK_ID, Config


def sh(*args, check=True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(list(map(str, args)), check=check, text=True, capture_output=True, **kw)


class Steam:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @property
    def log_path(self) -> pathlib.Path:
        return self.cfg.steam_root / "logs" / "console-linux.txt"

    def base_env(self) -> dict:
        c = self.cfg
        return dict(os.environ, DISPLAY=c.display, XAUTHORITY="/dev/null", DBUS_SESSION_BUS_ADDRESS=c.bus_address)

    def instances(self) -> list[str]:
        raise NotImplementedError

    def steam_argv(self, args: list[str]) -> list[str]:
        raise NotImplementedError

    def shell_argv(self, script: str) -> list[str]:
        """Run a shell snippet where the game runs (inside the sandbox, or on the host)."""
        raise NotImplementedError

    def vgl_env_script(self) -> str:
        v = self.cfg.virtualgl
        return f"export PATH={v}/opt/VirtualGL/bin:$PATH LD_LIBRARY_PATH={v}/usr/lib:${{LD_LIBRARY_PATH:-}}; "


class FlatpakSteam(Steam):
    def instances(self) -> list[str]:
        out = sh("flatpak", "ps", "--columns=instance,application", check=False).stdout
        return [p[0] for p in (line.split() for line in out.splitlines()) if len(p) >= 2 and p[1] == FLATPAK_ID]

    def opts(self) -> list[str]:
        c = self.cfg
        return [
            f"--env=DISPLAY={c.display}",
            "--env=TZ=America/New_York",
            f"--env=LD_PRELOAD={c.x11_shim}",
            f"--env=PATH={c.harness_home / 'bin'}:/app/bin:/app/utils/bin:/usr/bin:/bin",
        ]

    def steam_argv(self, args):
        return ["/usr/bin/flatpak", "run", *self.opts(), FLATPAK_ID, *args]

    def shell_argv(self, script):
        return ["/usr/bin/flatpak", "run", *self.opts(), "--command=sh", FLATPAK_ID, "-c", script]


class NativeSteam(Steam):
    def instances(self) -> list[str]:
        out = sh("pgrep", "-u", str(os.getuid()), "-x", "steam", check=False).stdout
        return out.split()

    def steam_argv(self, args):
        return ["/usr/bin/steam", *args]

    def shell_argv(self, script):
        return ["/bin/sh", "-c", script]


def backend(cfg: Config) -> Steam:
    return {"flatpak": FlatpakSteam, "native": NativeSteam}[cfg.steam](cfg)
