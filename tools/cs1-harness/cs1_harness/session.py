"""One harness session: its own X server and D-Bus, a harness-owned Steam, the game.

Steam launches the game through its normal launch flow (-applaunch), so Steam's
own prompts guard the account: if the account is playing on another computer,
Steam asks before launching, and the harness never answers. It reports the
prompt and stops instead.
"""

from __future__ import annotations

import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import time

from . import gpu, observe
from .client import Client, HarnessError
from .config import Config
from .steam import backend

EX_TEMPFAIL = 75  # try again later (account in use, Steam busy)
EX_NOPERM = 77  # needs a person (EULA, sign-in)


class Blocked(HarnessError):
    """The launch is waiting on something the harness must not answer.

    `busy` means another user of this host's harness slot (an agent's run or
    session, or a person's Steam) holds it; it frees on its own, so callers may
    wait for it.
    """

    def __init__(self, message: str, code: int, busy: bool = False):
        super().__init__(message)
        self.code = code
        self.busy = busy


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(*args, check=True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(list(map(str, args)), check=check, text=True, capture_output=True, **kw)


def game_pids(display: str | None = None) -> list[int]:
    """Running Cities.x64 processes; with `display`, only those drawing on that X display.

    Teardown passes the harness display, so it never quits or kills a game
    someone started elsewhere (on :0, say). Preflight passes none: any running
    game blocks a new session.
    """
    out = sh("pgrep", "-x", "Cities.x64", check=False).stdout
    pids = [int(p) for p in out.split()]
    if display is None:
        return pids
    mine = []
    for pid in pids:
        try:
            env = pathlib.Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        except OSError:
            continue
        if f"DISPLAY={display}".encode() in env:
            mine.append(pid)
    return mine


GPU_FIELDS = "timestamp,index,temperature.gpu,power.draw,power.limit,utilization.gpu,memory.used,clocks.sm,fan.speed"


class SteamLog:
    """Follows Steam's logs for this launch's game actions.

    The client logs launch steps to webhelper_js.txt
    ("OnGameActionUserRequest: <app> LaunchApp <Step>", "launch error ...") and
    older builds to console-linux.txt ("waiting for user response to <Step>").
    Steps such as ShowInterstitials or CreatingProcess pass; prompts stop the
    run, because the harness never answers them.
    """

    PASSING = {
        "ShowInterstitials",
        "ProcessingShaderCache",
        "CreatingProcess",
        "SynchronizingCloud",
        "SiteLicenseSeatCheckout",
        "WaitingGameWindow",
        "Completed",
        "RunningInstallScript",
        "VerifyingFiles",
        "None",
    }

    def __init__(self, cfg: Config, path: pathlib.Path):
        self.paths = [path, path.with_name("webhelper_js.txt")]
        self.offsets = {p: (p.stat().st_size if p.exists() else 0) for p in self.paths}
        self.app_id = cfg.app_id

    def new_lines(self) -> list[str]:
        lines = []
        for p in self.paths:
            if not p.exists():
                continue
            with open(p, "rb") as f:
                f.seek(self.offsets[p])
                data = f.read()
                self.offsets[p] += len(data)
            lines += data.decode("utf-8", "replace").splitlines()
        return lines

    def prompt(self, step: str):
        if re.search(r"Play|Session|Kick|Another|Elsewhere|InUse", step, re.I):
            raise Blocked(f"Steam says the account is in use elsewhere ({step}); not answering", EX_TEMPFAIL)
        if re.search(r"Eula", step, re.I):
            raise Blocked(
                "Steam wants the Cities: Skylines EULA accepted on this machine; that is the account owner's call",
                EX_NOPERM,
            )
        raise Blocked(f"Steam launch is waiting on a prompt the harness won't answer: {step}", EX_NOPERM)

    def check(self):
        for line in self.new_lines():
            if self.app_id not in line and "PlayingSession" not in line:
                continue
            m = re.search(r"waiting for user response to (\w+)", line) or re.search(
                rf"OnGameActionUserRequest: {self.app_id} LaunchApp (\w+)", line
            )
            # "SynchronizingCloud syncfailed" opens Steam's cloud-sync-failed dialog (Play anyway /
            # Cancel). It follows the account playing elsewhere; answering could clobber cloud saves.
            if m and m.group(1) == "SynchronizingCloud" and re.search(r"SynchronizingCloud\s+syncfailed", line):
                raise Blocked("Steam's cloud sync failed and it is asking what to do; not answering", EX_TEMPFAIL)
            if m and m.group(1) not in self.PASSING:
                self.prompt(m.group(1))
            m = re.search(rf"launch error \d+ {self.app_id} LaunchApp (\w+)", line)
            if m:
                raise HarnessError(
                    f"Steam could not launch the game ({m.group(1)}); see the Steam window or "
                    "content_log.txt (an update may be required)"
                )
            if "PlayingSession" in line and re.search(r"blocked|another", line, re.I):
                raise Blocked(f"Steam playing-session conflict: {line.strip()}", EX_TEMPFAIL)


class Session(contextlib.AbstractContextManager):
    def __init__(self, cfg: Config, stage: pathlib.Path, log=print):
        self.cfg = cfg
        self.stage = stage
        self.log = log
        self.client = Client(cfg.port)
        self.steam = backend(cfg)
        self.egl: str | None = None
        self.steam_log: SteamLog | None = None
        self.our_instances: set[str] = set()
        self.installed: list[pathlib.Path] = []
        self.lock_fd = None
        self.detached = False
        self.label: str | None = None
        self.record = True
        self.live = True
        self.receipt: dict = {"stage": str(stage)}

    # -- lifecycle -------------------------------------------------------

    def __enter__(self):
        self.cfg.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lock_fd = open(self.cfg.lock_file, "w")
        try:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Blocked("another cs1-harness run holds the lock", EX_TEMPFAIL, busy=True) from None
            if self.cfg.state_file.exists():
                raise Blocked(
                    f"a harness session is up ({self.cfg.state_file}); `cs1-harness down` ends it",
                    EX_TEMPFAIL,
                    busy=True,
                )
            self.preflight()
        except BaseException:
            # Release the lock here: __exit__ doesn't run when __enter__ raises,
            # and a retry in this process would otherwise block on its own lock.
            self.lock_fd.close()
            self.lock_fd = None
            raise
        self.stage.mkdir(parents=True, exist_ok=True)
        try:
            self.start_display()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc):
        try:
            if self.detached and exc[0] is None:
                self.save_state()
            else:
                self.stop()
        finally:
            if self.lock_fd:
                self.lock_fd.close()
        return False

    # -- persistent sessions (cs1-harness up / call / down) ----------------

    def detach(self):
        """Leave the session running when the context exits; `down` ends it."""
        self.detached = True

    def save_state(self):
        state = {
            "stage": str(self.stage),
            "our_instances": sorted(self.our_instances),
            "installed": [str(p) for p in self.installed],
            "receipt": self.receipt,
            "port": self.cfg.port,
            "display": self.cfg.display,
            "egl": self.egl,
            "label": self.label,
            "host": self.cfg.host,
            "started": time.time(),
        }
        self.cfg.state_file.write_text(json.dumps(state, indent=2, default=str) + "\n")

    def capture_window(self, path):
        from .x11 import GameWindow

        with GameWindow.from_session(self) as window:
            window.capture(path)

    @classmethod
    def attach(cls, cfg: Config, log=print) -> "Session":
        state = json.loads(cfg.state_file.read_text())
        s = cls(cfg, pathlib.Path(state["stage"]), log=log)
        s.our_instances = set(state["our_instances"])
        s.installed = [pathlib.Path(p) for p in state["installed"]]
        s.receipt = state["receipt"]
        s.egl = state.get("egl")
        s.label = state.get("label")
        return s

    def preflight(self):
        if self.cfg.display == ":0":
            raise HarnessError("refusing display :0 (Caleb's desktop)")
        if game_pids():
            raise Blocked("Cities.x64 is already running on this host", EX_TEMPFAIL, busy=True)
        if self.steam.instances():
            raise Blocked(
                "Steam is already running for this user (maybe on :0); the harness only uses a Steam it started itself",
                EX_TEMPFAIL,
                busy=True,
            )
        if (pathlib.Path("/tmp/.X11-unix") / f"X{self.cfg.display.lstrip(':')}").exists():
            raise Blocked(f"display {self.cfg.display} is already in use", EX_TEMPFAIL, busy=True)
        for unit in (
            self.cfg.vnc_unit,
            self.cfg.live_unit,
            self.cfg.rec_unit,
            self.cfg.steam_unit,
            self.cfg.gpu_unit,
            self.cfg.dbus_unit,
            self.cfg.xvfb_unit,
        ):
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

    def park_pointer(self):
        """Avoid edge-scroll input at the start of this owned private game.

        Unity's window can place the pointer at its upper-left when it opens.
        Moving the pointer is not a camera override and sends no click/key.
        """
        if self.lock_fd is None or self.cfg.display == ":0":
            raise HarnessError("pointer parking requires an owned private slot")
        x = ctypes.CDLL("libX11.so.6")
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x.XDefaultRootWindow.restype = ctypes.c_ulong
        x.XWarpPointer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
        ]
        x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x.XOpenDisplay(self.cfg.display.encode())
        if not display:
            raise HarnessError("cannot open owned private display to park pointer")
        px, py = self.cfg.width // 2, self.cfg.height // 2
        try:
            root = x.XDefaultRootWindow(display)
            x.XWarpPointer(display, 0, root, 0, 0, 0, 0, px, py)
            x.XSync(display, 0)
        finally:
            x.XCloseDisplay(display)
        self.receipt["pointer_parked"] = {"display": self.cfg.display, "root_position": [px, py]}

    def install_mod(self):
        c = self.cfg
        dll = c.build_dir / "Cs1Harness.dll"
        if not dll.exists():
            raise HarnessError("mod not built; run `cs1-harness build` first")
        c.mod_dir.mkdir(parents=True, exist_ok=True)
        target = c.mod_dir / dll.name
        shutil.copy2(dll, target)
        self.installed.append(c.mod_dir)
        self.receipt["mod_sha256"] = sha256(target)

    def pin_gpu(self):
        """Resolve the EGL device for the configured PCI bus and write the launch wrapper's session file."""
        c = self.cfg
        env = self.steam.base_env()

        def glxinfo(dev):
            script = self.steam.vgl_env_script() + f"vglrun -d {dev} glxinfo -B 2>/dev/null"
            r = subprocess.run(self.steam.shell_argv(script), env=env, capture_output=True, text=True, timeout=120)
            return r.stdout

        self.egl, name = gpu.resolve_egl(c.gpu_bus, glxinfo)
        target = gpu.gpu_at(c.gpu_bus)
        self.receipt["gpu"] = {
            "bus": target["bus"],
            "name": name,
            "egl": self.egl,
            "label": self.label,
            "mem_used_before_mib": target["mem_used"],
            "mem_total_mib": target["mem_total"],
        }
        c.harness_home.mkdir(parents=True, exist_ok=True)
        (c.harness_home / "session.env").write_text(
            f"CS1_HARNESS_DISPLAY={c.display}\nCS1_HARNESS_EGL={self.egl}\n"
            f"CS1_HARNESS_PORT={c.port}\nCS1_HARNESS_VGL={c.virtualgl}\n"
        )
        self.log(
            f"rendering on {name} at {target['bus']} ({self.egl}); {target['mem_total'] - target['mem_used']} MiB free"
        )
        return self.receipt["gpu"]

    def check_placement(self, placed: list[dict] | None = None) -> list[dict]:
        """The game must be on the pinned GPU and nowhere else."""
        if placed is None:
            placed = gpu.game_placement()
        want = gpu.norm_bus(self.cfg.gpu_bus)
        self.receipt["game_gpu"] = placed
        wrong = [p for p in placed if p["bus"] != want]
        if wrong:
            raise HarnessError(f"the game is using GPU(s) {sorted({p['bus'] for p in wrong})}, not {want}")
        if not placed:
            raise HarnessError(f"the game is not on any NVIDIA GPU (software rendering?); expected {want}")
        return placed

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

    def launch(self, game_args: list[str], timeout: float = 600):
        """Launch through Steam; strict vanilla returns at rendering, not menu readiness."""
        c = self.cfg
        if self.egl is None:
            self.pin_gpu()
        control = "--disableMods" not in game_args
        self.receipt["control"] = control
        if control:
            self.install_mod()
        env = self.steam.base_env()
        before = set(self.steam.instances())
        self.steam_log = SteamLog(c, self.steam.log_path)
        log_file = self.stage / "game.log"
        args = ["-silent", "-applaunch", c.app_id, *game_args, "-logFile", str(log_file)]
        self.receipt["launch_args"] = args
        props = ["-p", "KillMode=control-group"]
        unit_env = {k: env[k] for k in ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS")}
        self.unit(c.steam_unit, *self.steam.steam_argv(args), env=unit_env, props=props)
        self.unit(
            c.gpu_unit,
            "/usr/bin/nvidia-smi",
            f"--id={c.gpu_bus}",
            f"--query-gpu={GPU_FIELDS}",
            "--format=csv,nounits",
            "-l",
            "5",
            # nvidia-smi -f buffers until exit; systemd writes each stdout line as it comes.
            props=["-p", f"StandardOutput=file:{self.stage / 'gpu.csv'}"],
        )
        observe.start(self, record=self.record, live=self.live, label=self.label)
        self.log("Steam starting; waiting for the game")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.our_instances |= set(self.steam.instances()) - before
            self.steam_log.check()
            live_games = set(game_pids(self.cfg.display)) if not control else set()
            observed = [p for p in gpu.game_placement() if p["pid"] in live_games] if not control else []
            if observed:
                placed = self.check_placement(observed)
                self.park_pointer()
                self.log("strict --disableMods game rendering; observe menu readiness through the private X display")
                return {"control": False, "menu_ready": None, "game_gpu": placed}
            status = self.client.try_status() if control else None
            # CS1's main menu lives in the IntroScreen scene; it is ready once nothing is loading.
            if status and not status.get("loading") and not status.get("in_game"):
                self.receipt["menu_status"] = status
                placed = self.check_placement()
                self.park_pointer()
                self.log(f"game at main menu: {status.get('gpu')}, {status.get('screen')}; GPU processes {placed}")
                return status
            if not self.steam_alive():
                raise HarnessError(f"Steam exited before the game started; see the journal for {c.steam_unit}")
            time.sleep(3)
        raise HarnessError(f"game did not reach the main menu within {timeout:.0f} s")

    def steam_alive(self) -> bool:
        return sh(
            "systemctl", "--user", "is-active", "--quiet", self.cfg.steam_unit, check=False
        ).returncode == 0 or bool(self.our_instances & set(self.steam.instances()))

    def alive(self):
        """Raise if the game went away or Steam reported a conflict mid-run."""
        if self.steam_log:
            self.steam_log.check()
        if not game_pids(self.cfg.display):
            raise Blocked(
                "the game process ended unexpectedly (crash, or the account started playing elsewhere)", EX_TEMPFAIL
            )

    def gpu_processes(self) -> str:
        return sh("nvidia-smi", check=False).stdout

    def stop(self):
        """Quit the game, shut Steam down, stop the X server and bus, uninstall what we installed."""
        c = self.cfg
        env = self.steam.base_env()
        pids = game_pids(c.display)
        if pids:
            if self.receipt.get("control", True):
                with contextlib.suppress(Exception):
                    self.client.call("quit")
                for _ in range(60):
                    if not game_pids(c.display):
                        break
                    time.sleep(1)
            for pid in game_pids(c.display):
                self.log(
                    f"game {pid} ignored quit; terminating it"
                    if self.receipt.get("control", True)
                    else f"closing uninstrumented game {pid}"
                )
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, 15)
        if self.steam_alive() and (self.cfg.runtime_dir / "bus").exists():
            sh("timeout", "60", *self.steam.steam_argv(["-shutdown"]), check=False, env=env)
            for _ in range(90):
                if not self.steam_alive():
                    break
                time.sleep(1)
        for inst in self.our_instances & set(self.steam.instances()):
            self.log(f"Steam instance {inst} still up; killing it")
            if c.steam == "flatpak":
                sh("flatpak", "kill", inst, check=False)
            else:
                with contextlib.suppress(ProcessLookupError, ValueError):
                    os.kill(int(inst), 15)
        for unit in (c.vnc_unit, c.live_unit, c.rec_unit, c.steam_unit, c.gpu_unit, c.dbus_unit, c.xvfb_unit):
            sh("systemctl", "--user", "stop", unit, check=False)
        for path in reversed(self.installed):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            observe.mark_idle(c, "run ended")
        (c.harness_home / "session.env").unlink(missing_ok=True)
        c.state_file.unlink(missing_ok=True)
        leftovers = {
            "game": game_pids(c.display),
            "steam_instances": self.steam.instances(),
            "units_active": [
                u
                for u in (c.vnc_unit, c.live_unit, c.rec_unit, c.steam_unit, c.gpu_unit, c.dbus_unit, c.xvfb_unit)
                if sh("systemctl", "--user", "is-active", "--quiet", u, check=False).returncode == 0
            ],
        }
        self.receipt["cleanup"] = leftovers
        (self.stage / "session-receipt.json").write_text(json.dumps(self.receipt, indent=2, default=str) + "\n")
