"""Host layout for the harness. Defaults are blade's; every path can be overridden."""

from __future__ import annotations

import dataclasses
import os
import pathlib

HOME = pathlib.Path.home()
FLATPAK_ID = "com.valvesoftware.Steam"
SANDBOX_HOME = HOME / ".var" / "app" / FLATPAK_ID


def _path(env: str, default: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.environ.get(env, str(default))).expanduser()


@dataclasses.dataclass
class Config:
    # The game, as installed in the Flatpak Steam library.
    game_dir: pathlib.Path = _path(
        "CS1_GAME_DIR", pathlib.Path("/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines")
    )
    # Inside the Flatpak, XDG_DATA_HOME is the sandbox's ~/.local/share.
    data_dir: pathlib.Path = _path(
        "CS1_DATA_DIR", SANDBOX_HOME / ".local" / "share" / "Colossal Order" / "Cities_Skylines"
    )
    # Harness files the sandbox can see: launch wrapper, session file, staging.
    harness_home: pathlib.Path = _path("CS1_HARNESS_HOME", SANDBOX_HOME / "opt" / "cs1-harness")
    virtualgl: pathlib.Path = _path("CS1_HARNESS_VGL", SANDBOX_HOME / "opt" / "virtualgl-3.1.5")
    x11_shim: str = os.environ.get(
        "CS1_HARNESS_X11_SHIM",
        str(HOME / ".local/lib/blade-x11-filesystem") + "/$LIB/libblade-x11-filesystem.so",
    )
    # The harness's own X server. Never :0, which is Caleb's desktop.
    display: str = os.environ.get("CS1_HARNESS_DISPLAY", ":57")
    # VirtualGL EGL device. On blade egl1 is the RTX 3090, egl0 the 2080 Ti.
    egl_device: str = os.environ.get("CS1_HARNESS_EGL", "egl1")
    nvidia_index: int = int(os.environ.get("CS1_HARNESS_NVIDIA_INDEX", "1"))
    width: int = 1920
    height: int = 1080
    port: int = int(os.environ.get("CS1_HARNESS_PORT", "8779"))
    steam_unit: str = "cs1-harness-steam"
    xvfb_unit: str = "cs1-harness-xvfb"
    dbus_unit: str = "cs1-harness-dbus"
    app_id: str = "255710"
    cache_dir: pathlib.Path = _path("CS1_HARNESS_CACHE", HOME / ".cache" / "cs1-harness")

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
    def lock_file(self) -> pathlib.Path:
        return self.runtime_dir / "run.lock"
