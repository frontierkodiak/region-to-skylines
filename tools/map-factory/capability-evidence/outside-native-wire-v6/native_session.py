"""Native Session boundary. Only the future authenticated entry invokes it.

The actual shared cli.slot, staging and Session are used unchanged. Only this
newly-owned Session instance receives bounded cleanup/ownership delegates.
"""

from contextlib import contextmanager, ExitStack
import copy
import os
from pathlib import Path
import signal
import sys
import uuid

from loopback_fixture import identity
from native_context import config_from, cleanup
from wire import Deadline, Wire, Unknown, decode
from wire_supervisor import atomic, await_file


class NativeSession:
    purpose = "NATIVE"

    def __init__(self, directory, source, trace, case, inherited=None):
        self.directory, self.source, self.trace, self.case = (
            directory,
            source,
            trace,
            case,
        )
        self.inherited = inherited
        self.births = None
        self.game = None

    def bind(self, frozen, inputs):
        cases = frozen["controls"] + inputs["holdout_cases"]
        if not any(
            self.source.spec.canonical(self.case) == self.source.spec.canonical(c)
            for c in cases
        ):
            raise Unknown("opening/request not in the frozen study")
        if (
            Path(frozen["native"]["source_directory"]).resolve()
            != self.source.HERE.resolve()
        ):
            raise Unknown("native invocation source location differs")
        self.frozen, self.inputs = frozen, inputs
        self.cfg = config_from(frozen["native"]["configuration"])

    @contextmanager
    def open(self, native, inputs, request, store, total):
        self.native, self.request = native, request
        if request.session != self.frozen["native"]["session_id"]:
            raise Unknown("native session differs from accepted authorization")
        built = self.cfg.build_dir / "Cs1Harness.dll"
        if (
            self.source.spec.hashed(built.read_bytes())
            != native.descriptor["fresh_build"]["dll"]
        ):
            raise Unknown("reviewed retained build bytes missing/different")
        self.total = (
            Deadline(min(total.end, self.inherited["total_end"]))
            if self.inherited
            else total
        )
        self.first_opening = (
            Deadline(self.inherited["work_end"])
            if self.inherited
            else Deadline.after(840, self.total)
        )
        self.initial_load = Deadline.after(600, self.first_opening)
        if self.inherited:
            self.initial_load = Deadline(
                min(self.initial_load.end, self.inherited["load_end"])
            )
        self.stack = ExitStack()
        self.client = Wire(self.cfg.port, self.initial_load, self.trace)
        self.tracked = []
        try:
            yield self
        finally:
            self.stack.close()

    def begin(self, control, deadline):
        from cs1_harness.cli import slot, staging

        stage = staging(self.cfg, self.directory / control["case_id"])
        session = self.stack.enter_context(
            slot(
                self.cfg,
                stage,
                0,
                {
                    "command": "wire-v6",
                    "issue": "PL-1321",
                    "label": self.request.session,
                },
            )
        )
        self.session = session
        atomic(
            self.directory / "lease.json",
            dict(
                owner=identity(os.getpid()),
                fd=session.lock_fd.fileno(),
                path=str(self.cfg.lock_file),
            ),
        )
        ack = decode(await_file(self.directory / "lease-ack.json", deadline))
        if ack.get("worker") != identity(os.getpid()) or ack.get("parent") != identity(
            os.getppid()
        ):
            raise Unknown("external guard-lease handoff not acknowledged")
        session.require_offline, session.record, session.live = True, False, False
        self.client = session.client = Wire(self.cfg.port, deadline, self.trace)
        self.receipt = session.receipt
        self.audio_inode = (self.cfg.harness_home / "run-audio").stat().st_ino
        # Preserve shared guard/queue behavior. These delegates affect only our
        # newly-created Session object, never old module/class/global state.
        original_steam = session.steam.steam_argv
        original_shell = session.steam.shell_argv
        self.shims = 0

        def owned_argv(argv):
            if self.cfg.steam != "flatpak":
                return argv
            self.shims += 1
            record = self.directory / ("flatpak-" + str(self.shims) + ".json")
            return [
                sys.executable,
                str(Path(__file__).with_name("owned_flatpak.py")),
                str(record),
                str(self.total.end),
                *argv,
            ]

        session.steam.steam_argv = lambda args: owned_argv(original_steam(args))
        session.steam.shell_argv = lambda script: owned_argv(original_shell(script))
        session.stop = self.stop
        original_install_mod = session.install_mod

        def install_mod():
            # Never claim or remove an existing user's plugin directory.
            self.cfg.mod_dir.mkdir(parents=True, exist_ok=False)
            self.mod_inode = self.cfg.mod_dir.stat().st_ino
            original_install_mod()
            dll = self.cfg.mod_dir / "Cs1Harness.dll"
            self.tracked.append(
                (dll, dll.stat().st_ino, self.source.spec.hashed(dll.read_bytes()))
            )

        session.install_mod = install_mod
        self.installed = self._install(control)
        session.launch(["--noWorkshop"], timeout=deadline.remaining())
        deadline.remaining()

    def _install(self, case):
        controls = self.source.spec.read(self.source.spec.OLD / "freeze.json")[
            "controls"
        ]
        row = next((r for r in controls if r["case_id"] == case["case_id"]), None)
        locator = (
            row["locator"]
            if row
            else next(
                r["package_locator"]
                for r in self.inputs["holdout"]
                if r["case_id"] == case["case_id"]
            )
        )
        path = Path(locator)
        if self.source.spec.hashed(path.read_bytes()) != case["artifact_sha256"]:
            raise Unknown("frozen package bytes changed")
        before = set(self.session.installed)
        installed = self.session.install_map(path)
        if installed not in before and installed in self.session.installed:
            self.tracked.append(
                (installed, installed.stat().st_ino, case["artifact_sha256"])
            )
        return installed

    def install(self, control):
        return self.installed

    def alive(self):
        self.client.deadline.remaining()
        self.session.alive()
        self.client.deadline.remaining()

    def read_file(self, path):
        self.client.deadline.remaining()
        result = Path(path).read_bytes()
        self.client.deadline.remaining()
        return result

    def session_id(self, control):
        return self.request.session + "/" + control["case_id"] + "/" + str(uuid.uuid4())

    def inventory(self, api, native):
        build = copy.deepcopy(api.spec.read(api.spec.OLD / "freeze.json")["build"])
        build["dll"]["sha256"] = native.descriptor["fresh_build"]["dll"]
        inv = api.collect_v2.runtime_inventory(self.session, build, native.bindings())
        self.game = dict(pid=inv["pid"], start_ticks=inv["start_ticks"])
        if self.births is not None:
            self.births["game"] = self.game
        atomic(
            self.directory / "native-owner.json",
            dict(
                game=self.game,
                installed=[
                    dict(path=str(p), inode=i, sha256=h) for p, i, h in self.tracked
                ],
            ),
        )
        if inv.pop("unresolved"):
            raise Unknown("unresolved loaded assemblies")
        for key in (
            "pid",
            "start_ticks",
            "source_sha256",
            "dll_sha256",
            "protocol_sha256",
        ):
            inv.pop(key)
        inv["process_roles"] = native.descriptor["inventory"]["process_roles"]
        return inv

    def stop(self):
        # Shared Session.stop uses display-wide PID kills. Do not call it for a
        # native study. The external owner retains the ORIGINAL slot lease.
        deadline = Deadline.after(20, self.total)
        signal.setitimer(signal.ITIMER_REAL, deadline.remaining())
        errors = []
        try:
            self.client.deadline = Deadline.after(2, deadline)
            if self.game and identity(self.game["pid"]) == self.game:
                try:
                    self.client.call("quit")
                except (OSError, ValueError):
                    errors.append("quit not acknowledged")
            result = cleanup(self.cfg, self.directory, deadline, lease_held=True)
            errors.extend(result["unresolved"])
            for path, inode, hashed in self.tracked:
                if path.exists():
                    if (
                        path.stat().st_ino != inode
                        or self.source.spec.hashed(path.read_bytes()) != hashed
                    ):
                        errors.append("installed file changed: " + str(path))
                    else:
                        path.unlink()
            if hasattr(self, "mod_inode") and self.cfg.mod_dir.exists():
                if self.cfg.mod_dir.stat().st_ino == self.mod_inode:
                    try:
                        self.cfg.mod_dir.rmdir()
                    except OSError:
                        errors.append("plugin directory not empty")
            if self.game and identity(self.game["pid"]) == self.game:
                errors.append("game identity remains present")
            if result["clean"]:
                import shutil

                audio = self.cfg.harness_home / "run-audio"
                if audio.exists() and audio.stat().st_ino == self.audio_inode:
                    shutil.rmtree(audio)
                env = self.cfg.harness_home / "session.env"
                if env.exists():
                    env.unlink()
            atomic(
                self.directory / "native-cleanup.json",
                dict(
                    game=self.game, cleanup=result, unresolved=errors, clean=not errors
                ),
            )
            if errors:
                raise Unknown("native cleanup unresolved: " + "; ".join(errors))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
