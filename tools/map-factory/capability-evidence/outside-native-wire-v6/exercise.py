"""Full constructed socket/collector/retention/consumer path, using private v5 bytes."""

from contextlib import contextmanager
import copy
import gzip
import os
from pathlib import Path
import sys

import accepted_api as api
from authority import ConstructedAuthority as ConstructedAuthority
from loopback_fixture import server, identity
from wire import Deadline, Wire, Unknown, decode


class FixtureSession:
    purpose = "CONSTRUCTED"

    def __init__(self, store, native, port, trace, inventory_override=None):
        self.store, self.native = store, native
        self.inventory_override = inventory_override
        self.client = Wire(port, Deadline.after(10), trace)
        self.receipt = dict(launch_args=["--noWorkshop"])

    def begin(self, control, deadline):
        deadline.remaining()

    def install(self, control):
        return "/CONSTRUCTED/" + control["case_id"]

    def alive(self):
        self.client.deadline.remaining()

    def session_id(self, control):
        return "CONSTRUCTED-wire-v6/" + control["case_id"]

    def read_file(self, path):
        key = self.native.descriptor["inventory"]["files"][path]
        return self.store.read(key, "CONSTRUCTED inventory bytes")

    def inventory(self, api, native):
        # Explicit simulated inventory; real bytes still pass unchanged retention/policy.
        self.client.call("runtime_identity")
        self.client.call("status")
        return copy.deepcopy(
            self.inventory_override
            if self.inventory_override is not None
            else native.descriptor["inventory"]
        )


def script_for(native, store):
    script = []

    def add(op, reply=None, **args):
        script.append(dict(op=op, args=args, reply=dict(ok=True, **(reply or {}))))

    def inventory():
        add("runtime_identity", dict(fixture="CONSTRUCTED"))
        add("status", dict(loading=False, in_game=True))

    for control in native.value["controls"]:
        path = "/CONSTRUCTED/" + control["case_id"]
        # Public input network snapshot; not historical path outcomes.
        file = (
            api.spec.CAP
            / "outside-stock-budget-v1"
            / ("control-" + control["case_id"] + "-networks.json.gz")
        )
        networks = api.spec.decode(gzip.decompress(file.read_bytes()))
        graph = api.collect_v2.graph_value(networks)
        if api.spec.digest(graph) != control["exact_graph_sha256"]:
            raise Unknown("published control input graph differs")

        def stats():
            add(
                "stats",
                dict(frame=2, update_mode="NewGameFromMap", invert_traffic=False),
            )

        def net():
            add("networks", {k: v for k, v in networks.items() if k != "ok"})

        inventory()
        add("maps", dict(maps=[dict(path=path)]))
        add("new_game", dict(job=1), path=path)
        add("status", dict(loading=False, in_game=True))
        stats()
        add("run", paused=True)
        net()
        inventory()
        add("run", paused=False, speed=1)
        for index, plan in enumerate(control["requests"], 1):
            stats()
            net()
            add("study_build_index", dict(build_index=index, frame=2, paused=False))
            mode = {"road": "car", "ship": "ship", "air": "plane"}[plan["mode"]]
            vehicle = {"road": "Car", "ship": "Ship", "air": "Plane"}[plan["mode"]]
            add(
                "path_start",
                dict(
                    id=index,
                    mode=mode,
                    **{
                        "from": plan["request"]["from"],
                        "to": plan["request"]["to"],
                        "max_length": 100000,
                        "build_index": index,
                        "seed": 857,
                        "vehicle": vehicle,
                        "category": "PassengerCar" if mode == "car" else "All",
                        "lane_types": "Vehicle"
                        if mode == "car"
                        else "Vehicle, TransportVehicle, CargoVehicle",
                    },
                ),
                **{
                    "from": plan["request"]["from"],
                    "to": plan["request"]["to"],
                    "mode": mode,
                    "max_length": 100000,
                },
            )
            positive = plan["kind"] == "positive"
            add(
                "path_result",
                dict(
                    id=index,
                    complete=True,
                    released=True,
                    success=positive,
                    flags=4 if positive else 8,
                    length=1 if positive else 0,
                    positions=[plan["request"]["from"], plan["request"]["to"]]
                    if positive
                    else [],
                ),
                id=index,
            )
            stats()
            net()
        add("run", paused=True)
        net()
        inventory()
    return script


class Factory:
    purpose = "CONSTRUCTED"

    def __init__(self, directory, script=None, limits=None, inventory_override=None):
        self.directory, self.script, self.limits = directory, script, limits
        self.inventory_override = inventory_override
        self.effects = []
        self.trace = []

    @contextmanager
    def open(self, native, inputs, request, store, total):
        self.effects.append("constructed session owner")
        script = self.script if self.script is not None else script_for(native, store)
        limits = self.limits or native.descriptor["limits"]
        total = Deadline.after(limits["total_seconds"], total)
        first_opening = Deadline.after(limits["opening_seconds"], total)
        initial_load = Deadline.after(limits["load_seconds"], first_opening)
        with server(script, self.directory / "server") as game:
            self.game = game
            session = FixtureSession(store, native, game["port"], self.trace)
            session.total, session.first_opening, session.initial_load = (
                total,
                first_opening,
                initial_load,
            )
            yield session


class ConnectedFixture:
    purpose = "CONSTRUCTED"

    def __init__(self, config, trace):
        self.config, self.trace = config, trace

    @contextmanager
    def open(self, native, inputs, request, store, total):
        from exercise import FixtureSession

        c = self.config
        session = FixtureSession(
            store, native, c["port"], self.trace, c.get("inventory_override")
        )
        session.total = Deadline(min(c["total_end"], total.end))
        session.first_opening = Deadline(min(c["opening_end"], session.total.end))
        session.initial_load = Deadline(min(c["load_end"], session.first_opening.end))
        yield session


def run(frozen, store, request, authority, factory):
    """External owner; collection, handoff, audit and monitoring run in four workers."""
    from entry import enter
    from authority import descriptor
    from wire_supervisor import Owned, atomic

    children, births = {}, {}
    failure = None
    result = None
    with enter(frozen, store, request, authority, factory) as session:
        native = session.native
        births["game"] = factory.game["birth"]
        external = Deadline.after(20, session.total)
        worker = Path(__file__).with_name("roles.py")
        atomic(factory.directory / "freeze.json", frozen)
        try:
            for role in sorted(api.lifecycle.ROLES - {"game"}):
                owner = Owned.start(
                    [
                        sys.executable,
                        str(worker),
                        role,
                        str(factory.directory),
                        str(external.end),
                    ],
                    role,
                    factory.directory,
                )
                children[role] = owner
                births[role] = owner.birth
            atomic(
                factory.directory / "config.json",
                dict(
                    freeze=str(factory.directory / "freeze.json"),
                    store=str(store.root),
                    request=descriptor(request),
                    binding=native.bindings(),
                    births=births,
                    port=session.client.port,
                    inventory_override=factory.inventory_override,
                    total_end=session.total.end,
                    opening_end=session.first_opening.end,
                    load_end=session.initial_load.end,
                    limits=factory.limits or native.descriptor["limits"],
                ),
            )
            # Reaping the collector lets the independent driver observe its exit.
            if children["collector"].wait(external) != 0:
                raise Unknown("collector exited nonzero")
            for role in ("driver", "auditor", "monitor"):
                if children[role].wait(external) != 0:
                    raise Unknown(role + " exited nonzero")
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
        finally:
            for owned in children.values():
                owned.stop()
    receipts = {role: owned.receipt() for role, owned in children.items()}
    births["game"] = factory.game["birth"]
    cleanup = {
        role: dict(birth, gone=identity(birth["pid"]) != birth)
        for role, birth in births.items()
    }
    exits = {role: owned.process.returncode for role, owned in children.items()}
    exits["game"] = factory.game["exit_code"]
    after = {role: identity(birth["pid"]) for role, birth in births.items()}
    collector_file = factory.directory / "collector.json"
    collected = (
        decode(collector_file.read_bytes())
        if collector_file.exists()
        else dict(
            records=[],
            trace=[],
            pending="worker stopped before first snapshot",
            error="collector handoff missing",
            done=False,
        )
    )
    records = collected["records"]
    failure = failure or collected["error"]
    if not collected["done"]:
        failure = failure or "collector did not complete handoff"
    receipt = dict(
        stage="AfterDriverExit",
        supervisor=identity(os.getpid()),
        births=births,
        cleanup=cleanup,
        exit_codes=exits,
        after_exit_identities=after,
        fixture="CONSTRUCTED role processes, not game observations",
        external_finalizer_pid=os.getpid(),
    )
    handoff_file = factory.directory / "driver.json"
    if handoff_file.exists():
        handoff_bytes = handoff_file.read_bytes()
        handoff = decode(handoff_bytes)
        if handoff["records"] != records:
            failure = failure or "driver/collector handoff differs"
        receipt["driver_handoff_sha256"] = api.spec.put(store, handoff_bytes)
    else:
        failure = failure or "independent driver handoff missing"
    if failure is None:
        for record in records:
            record["observed"]["cleanup"] = cleanup
            record["observed"]["owned_processes"] = cleanup
        policy = api.pipeline.runtime_policy(native, native.descriptor["inventory"])
        bundle = api.adapter.bundle(
            native, native.bindings(), records, policy, receipt, store
        )
        result = api.adapter.gate(bundle, frozen["v5"], store)
        result.update(
            fresh_build=False,
            build_scope="reused accepted compile, no compiler invocation",
        )
    else:
        bundle = None
        result = dict(
            structural_pass=False, control_admission="Unknown", reason=failure
        )
    return dict(
        result=result,
        bundle=bundle,
        lifecycle=receipt,
        workers=receipts,
        trace=collected["trace"],
        server_calls=decode((factory.directory / "server/calls.json").read_bytes()),
        records=records,
        pending=collected["pending"],
        inventory_captures=collected.get("inventories", []),
        source_revision=frozen["source_revision"],
        freeze_sha256=api.spec.digest(frozen),
    )
