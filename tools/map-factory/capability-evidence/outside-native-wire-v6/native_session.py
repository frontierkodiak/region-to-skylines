"""Future native owner: shared slot/staging/Session, never attach or steal a session.

NOT invoked by this issue. This module contains no native authorization provider.
"""

from contextlib import contextmanager, ExitStack
import copy
from pathlib import Path
import uuid

from wire import Deadline, Wire, Unknown


class NativeSession:
    purpose = "NATIVE"

    def __init__(self, cfg, directory, source, trace):
        self.cfg, self.directory, self.source, self.trace = (
            cfg,
            directory,
            source,
            trace,
        )

    @contextmanager
    def open(self, native, inputs, request, store, total):
        from cs1_harness.cli import slot, staging

        # Config's per-checkout build_dir is retained; never overwrite shared staging.
        built = self.cfg.build_dir / "Cs1Harness.dll"
        if (
            self.source.spec.hashed(built.read_bytes())
            != native.descriptor["fresh_build"]["dll"]
        ):
            raise Unknown("reviewed build is not staged in this checkout")
        self.total = total
        self.first_opening = Deadline.after(900, total)
        self.initial_load = Deadline.after(600, self.first_opening)
        self.native, self.request = native, request
        self.stack = ExitStack()
        try:
            yield self
        finally:
            self.stack.close()

    def begin(self, control, deadline):
        from cs1_harness.cli import slot, staging

        # A second new_game cannot run in a loaded city. Each opening owns a new slot.
        self.stack.close()
        self.stack = ExitStack()
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
        session.require_offline, session.record, session.live = True, False, False
        self.installed = self._install(control)
        session.client = Wire(self.cfg.port, deadline, self.trace)
        self.client = session.client
        session.launch(["--noWorkshop"], timeout=deadline.remaining())
        self.receipt = session.receipt

    def install(self, control):
        # PackageManager enumerates maps at startup; the copy happened before launch.
        return self.installed

    def _install(self, control):
        controls = self.source.spec.read(self.source.spec.OLD / "freeze.json")[
            "controls"
        ]
        row = next(r for r in controls if r["case_id"] == control["case_id"])
        path = Path(row["locator"])
        if self.source.spec.hashed(path.read_bytes()) != control["artifact_sha256"]:
            raise Unknown("control package bytes changed")
        return self.session.install_map(path)

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
