"""Host profiles for the harness. `--host` (or CS1_HARNESS_HOST) picks one; the
default is this machine's hostname. Environment variables override fields."""

from __future__ import annotations

import dataclasses
import os
import pathlib
import socket

HOME = pathlib.Path.home()
FLATPAK_ID = "com.valvesoftware.Steam"
SANDBOX_HOME = HOME / ".var" / "app" / FLATPAK_ID

# The GPU the game renders on, by PCI bus ID. Both hosts use their RTX 2080 Ti
# so the 3090s (blade's experiment lane; worm's desktop and its loud fan) do no
# rendering. Power limits are host-owned; the harness never changes them.
PROFILES = {
    "blade": {
        "steam": "flatpak",
        "steam_root": SANDBOX_HOME / ".local/share/Steam",
        "game_dir": pathlib.Path("/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines"),
        # Inside the Flatpak, XDG_DATA_HOME is the sandbox's ~/.local/share.
        "data_dir": SANDBOX_HOME / ".local/share/Colossal Order/Cities_Skylines",
        # Files the game writes must be visible inside the sandbox.
        "harness_home": SANDBOX_HOME / "opt/cs1-harness",
        "virtualgl": SANDBOX_HOME / "opt/virtualgl-3.1.5",
        "gpu_bus": "00000000:05:00.0",
    },
    "worm": {
        "steam": "native",
        "steam_root": HOME / ".local/share/Steam",
        "game_dir": HOME / "Games/SteamLibrary/steamapps/common/Cities_Skylines",
        "data_dir": HOME / ".local/share/Colossal Order/Cities_Skylines",
        "harness_home": HOME / ".local/share/cs1-harness",
        "virtualgl": HOME / ".local/opt/virtualgl-3.1.5",
        "gpu_bus": "00000000:05:00.0",
    },
}


def _env_path(name: str, default: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.environ.get(name, str(default))).expanduser()


@dataclasses.dataclass
class Config:
    host: str
    steam: str  # "flatpak" or "native"
    steam_root: pathlib.Path
    game_dir: pathlib.Path
    data_dir: pathlib.Path
    harness_home: pathlib.Path
    virtualgl: pathlib.Path
    gpu_bus: str
    x11_shim: str = os.environ.get(
        "CS1_HARNESS_X11_SHIM",
        str(HOME / ".local/lib/blade-x11-filesystem") + "/$LIB/libblade-x11-filesystem.so",
    )
    # The harness's own X server. Never :0, a person's desktop.
    display: str = os.environ.get("CS1_HARNESS_DISPLAY", ":57")
    width: int = 1920
    height: int = 1080
    port: int = int(os.environ.get("CS1_HARNESS_PORT", "8779"))
    steam_unit: str = "cs1-harness-steam"
    xvfb_unit: str = "cs1-harness-xvfb"
    dbus_unit: str = "cs1-harness-dbus"
    gpu_unit: str = "cs1-harness-gpu"
    app_id: str = "255710"
    cache_dir: pathlib.Path = _env_path("CS1_HARNESS_CACHE", HOME / ".cache" / "cs1-harness")

    @classmethod
    def for_host(cls, host: str | None = None) -> Config:
        here = socket.gethostname().split(".")[0]
        host = host or os.environ.get("CS1_HARNESS_HOST") or here
        if host not in PROFILES:
            raise SystemExit(f"no harness profile for host {host!r}; known: {', '.join(PROFILES)}")
        if host != here and not os.environ.get("CS1_HARNESS_ALLOW_FOREIGN"):
            raise SystemExit(
                f"the {host} profile runs on {host}, and this is {here}. Run it there: "
                f"ssh {host} 'cd <checkout>/tools/cs1-harness && uv run cs1-harness --host {host} ...'"
            )
        p = dict(PROFILES[host])
        for key in ("steam_root", "game_dir", "data_dir", "harness_home", "virtualgl"):
            p[key] = _env_path(f"CS1_{key.upper()}", p[key])
        p["gpu_bus"] = os.environ.get("CS1_HARNESS_GPU_BUS", p["gpu_bus"])
        return cls(host=host, **p)

    @property
    def dotnet_root(self) -> pathlib.Path:
        return self.cache_dir / "dotnet"

    @property
    def build_dir(self) -> pathlib.Path:
        return self.cache_dir / "build"

    @property
    def mod_dir(self) -> pathlib.Path:
        return self.data_dir / "Addons" / "Mods" / "Cs1Harness"

    @property
    def maps_dir(self) -> pathlib.Path:
        return self.data_dir / "Maps"

    @property
    def runtime_dir(self) -> pathlib.Path:
        return pathlib.Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "cs1-harness"

    @property
    def bus_address(self) -> str:
        return f"unix:path={self.runtime_dir / 'bus'}"

    @property
    def state_file(self) -> pathlib.Path:
        return self.runtime_dir / "session.json"

    @property
    def lock_file(self) -> pathlib.Path:
        return self.runtime_dir / "run.lock"
