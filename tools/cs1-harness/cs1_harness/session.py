"""One harness session: its own X server and D-Bus, a harness-owned Steam, the game.

Steam launches the game through its normal launch flow (-applaunch), so Steam's
own prompts guard the account: if the account is playing on another computer,
Steam asks before launching, and the harness never answers. It reports the
prompt and stops instead.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import threading
import time

from .client import Client, HarnessError
from .config import FLATPAK_ID, Config

EX_TEMPFAIL = 75  # try again later (account in use, Steam busy)
EX_NOPERM = 77  # needs a person (EULA, sign-in)


class Blocked(HarnessError):
    """The launch is waiting on something the harness must not answer."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(*args, check=True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(list(map(str, args)), check=check, text=True, capture_output=True, **kw)


def flatpak_instances() -> list[dict]:
    out = sh("flatpak", "ps", "--columns=instance,pid,application", check=False).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append({"instance": parts[0], "pid": parts[1], "application": parts[2]})
    return rows


def steam_instances() -> list[dict]:
    return [r for r in flatpak_instances() if r["application"] == FLATPAK_ID]


def game_pids() -> list[int]:
    out = sh("pgrep", "-x", "Cities.x64", check=False).stdout
    return [int(p) for p in out.split()]


class GpuMonitor(threading.Thread):
    """Samples temperature and power of the harness GPU every few seconds."""

    FIELDS = "timestamp,index,temperature.gpu,power.draw,power.limit,utilization.gpu,memory.used,clocks.sm,fan.speed"

    def __init__(self, index: int, path: pathlib.Path, every: float = 5.0):
        super().__init__(daemon=True)
        self.index, self.path, self.every = index, path, every
        self.stop_event = threading.Event()

    def run(self):
        with open(self.path, "w") as f:
            f.write(self.FIELDS + "\n")
            while not self.stop_event.is_set():
                r = sh(
                    "nvidia-smi",
                    f"-i={self.index}",
                    f"--query-gpu={self.FIELDS}",
                    "--format=csv,noheader,nounits",
                    check=False,
                )
                if r.returncode == 0:
                    f.write(r.stdout.strip() + "\n")
                    f.flush()
                self.stop_event.wait(self.every)

    def stop(self):
        self.stop_event.set()
        self.join(timeout=15)


class SteamLog:
    """Follows Steam's console log for this launch's GameAction lines."""

    def __init__(self, cfg: Config):
        self.path = pathlib.Path.home() / ".var/app" / FLATPAK_ID / ".local/share/Steam/logs/console-linux.txt"
        self.offset = self.path.stat().st_size if self.path.exists() else 0
        self.app_id = cfg.app_id

    def new_lines(self) -> list[str]:
        if not self.path.exists():
            return []
        with open(self.path, "rb") as f:
            f.seek(self.offset)
            data = f.read()
            self.offset += len(data)
        return data.decode("utf-8", "replace").splitlines()

    def check(self):
        for line in self.new_lines():
            if f"AppID {self.app_id}" not in line and "PlayingSession" not in line:
                continue
            m = re.search(r"waiting for user response to (\w+)", line)
            if m:
                prompt = m.group(1)
                if re.search(r"Play|Session|Kick|Another|Elsewhere", prompt, re.I):
                    raise Blocked(f"Steam says the account is in use elsewhere ({prompt}); not answering", EX_TEMPFAIL)
                if re.search(r"Eula", prompt, re.I):
                    raise Blocked(
                        "Steam wants the Cities: Skylines EULA accepted on this machine; that is the account "
                        "owner's call",
                        EX_NOPERM,
                    )
                raise Blocked(f"Steam launch is waiting on a prompt the harness won't answer: {prompt}", EX_NOPERM)
            if "PlayingSession" in line and re.search(r"blocked|another", line, re.I):
                raise Blocked(f"Steam playing-session conflict: {line.strip()}", EX_TEMPFAIL)


class Session(contextlib.AbstractContextManager):
    def __init__(self, cfg: Config, stage: pathlib.Path, log=print):
        self.cfg = cfg
        self.stage = stage
        self.log = log
        self.client = Client(cfg.port)
        self.gpu: GpuMonitor | None = None
        self.steam_log: SteamLog | None = None
        self.our_instances: set[str] = set()
        self.installed: list[pathlib.Path] = []
        self.lock_fd = None
        self.receipt: dict = {"stage": str(stage)}

    # -- lifecycle -------------------------------------------------------

    def __enter__(self):
        self.cfg.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lock_fd = open(self.cfg.lock_file, "w")
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Blocked("another cs1-harness run holds the lock", EX_TEMPFAIL) from None
        self.preflight()
        self.stage.mkdir(parents=True, exist_ok=True)
        try:
            self.start_display()
            self.install_mod()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc):
        try:
            self.stop()
        finally:
            if self.lock_fd:
                self.lock_fd.close()
        return False

    def preflight(self):
        if self.cfg.display == ":0":
            raise HarnessError("refusing display :0 (Caleb's desktop)")
        if game_pids():
            raise Blocked("Cities.x64 is already running on this host", EX_TEMPFAIL)
        if steam_instances():
            raise Blocked(
                "Steam is already running for this user (maybe on :0); the harness only uses a Steam it started itself",
                EX_TEMPFAIL,
            )
        if (pathlib.Path("/tmp/.X11-unix") / f"X{self.cfg.display.lstrip(':')}").exists():
            raise Blocked(f"display {self.cfg.display} is already in use", EX_TEMPFAIL)
        for unit in (self.cfg.steam_unit, self.cfg.dbus_unit, self.cfg.xvfb_unit):
            sh("systemctl", "--user", "reset-failed", unit, check=False)

    def unit(self, name: str, *cmd, env: dict | None = None, props=()):
        args = ["systemd-run", "--user", f"--unit={name}", "--collect", "--quiet", *props]
        for k, v in (env or {}).items():
            args.append(f"--setenv={k}={v}")
        sh(*args, *cmd)

    def start_display(self):
        c = self.cfg
        self.unit(
            c.xvfb_unit,
            "/usr/bin/Xvfb",
            c.display,
            "-screen",
            "0",
            f"{c.width}x{c.height}x24",
            "-nolisten",
            "tcp",
            "-noreset",
        )
        sock = pathlib.Path("/tmp/.X11-unix") / f"X{c.display.lstrip(':')}"
        for _ in range(50):
            if sock.exists():
                break
            time.sleep(0.2)
        else:
            raise HarnessError(f"Xvfb {c.display} did not start")
        # A private session bus whose activation environment carries the harness
        # DISPLAY. Steam's Flatpak requires one; the desktop's bus has none and
        # must not be pointed at the harness display.
        bus = c.runtime_dir / "bus"
        bus.unlink(missing_ok=True)
        env = {
            "DISPLAY": c.display,
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
            "XDG_DATA_DIRS": f"{pathlib.Path.home()}/.local/share/flatpak/exports/share:"
            "/var/lib/flatpak/exports/share:/usr/local/share:/usr/share",
        }
        self.unit(c.dbus_unit, "/usr/bin/dbus-daemon", "--session", "--nofork", f"--address={c.bus_address}", env=env)
        for _ in range(50):
            if bus.exists():
                break
            time.sleep(0.2)
        else:
            raise HarnessError("private D-Bus did not start")
        self.receipt["display"] = c.display
        self.log(f"display {c.display} and private bus up")

    def install_mod(self):
        c = self.cfg
        dll = c.build_dir / "Cs1Harness.dll"
        if not dll.exists():
            raise HarnessError("mod not built; run `cs1-harness build` first")
        c.mod_dir.mkdir(parents=True, exist_ok=True)
        target = c.mod_dir / dll.name
        shutil.copy2(dll, target)
        self.installed.append(c.mod_dir)
        c.harness_home.mkdir(parents=True, exist_ok=True)
        (c.harness_home / "session.env").write_text(
            f"CS1_HARNESS_DISPLAY={c.display}\nCS1_HARNESS_EGL={c.egl_device}\n"
            f"CS1_HARNESS_PORT={c.port}\nCS1_HARNESS_VGL={c.virtualgl}\n"
        )
        self.receipt["mod_sha256"] = sha256(target)

    def install_map(self, crp: pathlib.Path) -> pathlib.Path:
        target = self.cfg.maps_dir / crp.name
        self.cfg.maps_dir.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha256(target) != sha256(crp):
            raise HarnessError(f"{target} exists with different contents; rename the map or remove it")
        if not target.exists():
            shutil.copy2(crp, target)
            self.installed.append(target)
        self.receipt["map"] = {"source": str(crp), "installed": str(target), "sha256": sha256(target)}
        return target

    def flatpak_env(self) -> tuple[dict, list[str]]:
        c = self.cfg
        env = dict(os.environ, DISPLAY=c.display, XAUTHORITY="/dev/null", DBUS_SESSION_BUS_ADDRESS=c.bus_address)
        opts = [
            f"--env=DISPLAY={c.display}",
            "--env=TZ=America/New_York",
            f"--env=LD_PRELOAD={c.x11_shim}",
            f"--env=PATH={c.harness_home / 'bin'}:/app/bin:/app/utils/bin:/usr/bin:/bin",
        ]
        return env, opts

    def launch(self, game_args: list[str], timeout: float = 600):
        """Start Steam on the harness display with -applaunch; wait for the mod's socket."""
        c = self.cfg
        env, opts = self.flatpak_env()
        before = {r["instance"] for r in steam_instances()}
        self.steam_log = SteamLog(c)
        log_file = self.stage / "game.log"
        args = ["-silent", "-applaunch", c.app_id, *game_args, "-logFile", str(log_file)]
        self.receipt["launch_args"] = args
        props = ["-p", "KillMode=control-group"]
        unit_env = {k: env[k] for k in ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS")}
        self.unit(c.steam_unit, "/usr/bin/flatpak", "run", *opts, FLATPAK_ID, *args, env=unit_env, props=props)
        self.gpu = GpuMonitor(c.nvidia_index, self.stage / "gpu.csv")
        self.gpu.start()
        self.log("Steam starting; waiting for the game")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.our_instances |= {r["instance"] for r in steam_instances()} - before
            self.steam_log.check()
            status = self.client.try_status()
            if (
                status
                and status.get("scene") not in (None, "", "IntroScreen", "Startup", "LoadingScreen")
                and not status.get("loading")
            ):
                self.receipt["menu_status"] = status
                self.log(f"game at main menu: {status.get('gpu')}, {status.get('screen')}")
                return status
            if not self.steam_alive():
                raise HarnessError(f"Steam exited before the game started; see the journal for {c.steam_unit}")
            time.sleep(3)
        raise HarnessError(f"game did not reach the main menu within {timeout:.0f} s")

    def steam_alive(self) -> bool:
        return sh(
            "systemctl", "--user", "is-active", "--quiet", self.cfg.steam_unit, check=False
        ).returncode == 0 or bool(self.our_instances & {r["instance"] for r in steam_instances()})

    def alive(self):
        """Raise if the game went away or Steam reported a conflict mid-run."""
        if self.steam_log:
            self.steam_log.check()
        if not game_pids():
            raise Blocked(
                "the game process ended unexpectedly (crash, or the account started playing elsewhere)", EX_TEMPFAIL
            )

    def gpu_processes(self) -> str:
        return sh("nvidia-smi", check=False).stdout

    def stop(self):
        """Quit the game, shut Steam down, stop the X server and bus, uninstall what we installed."""
        c = self.cfg
        env, opts = self.flatpak_env()
        pids = game_pids()
        if pids:
            with contextlib.suppress(Exception):
                self.client.call("quit")
            for _ in range(60):
                if not game_pids():
                    break
                time.sleep(1)
            for pid in game_pids():
                self.log(f"game {pid} ignored quit; terminating it")
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, 15)
        if self.steam_alive() and (self.cfg.runtime_dir / "bus").exists():
            sh("timeout", "60", "flatpak", "run", *opts, FLATPAK_ID, "-shutdown", check=False, env=env)
            for _ in range(90):
                if not self.steam_alive():
                    break
                time.sleep(1)
        for inst in self.our_instances & {r["instance"] for r in steam_instances()}:
            self.log(f"Steam instance {inst} still up; killing it")
            sh("flatpak", "kill", inst, check=False)
        for unit in (c.steam_unit, c.dbus_unit, c.xvfb_unit):
            sh("systemctl", "--user", "stop", unit, check=False)
        if self.gpu:
            self.gpu.stop()
        for path in reversed(self.installed):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        (c.harness_home / "session.env").unlink(missing_ok=True)
        leftovers = {
            "game": game_pids(),
            "steam_instances": [r["instance"] for r in steam_instances()],
            "units_active": [
                u
                for u in (c.steam_unit, c.dbus_unit, c.xvfb_unit)
                if sh("systemctl", "--user", "is-active", "--quiet", u, check=False).returncode == 0
            ],
        }
        self.receipt["cleanup"] = leftovers
        (self.stage / "session-receipt.json").write_text(json.dumps(self.receipt, indent=2, default=str) + "\n")
