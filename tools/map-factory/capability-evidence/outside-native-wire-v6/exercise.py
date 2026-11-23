"""Full constructed socket/collector/retention/consumer path, using private v5 bytes."""

from contextlib import contextmanager
import copy
import gzip
import os
import subprocess
import sys

import bridge as api
from fixtures import server, identity
from runtime import Transport, collect
from wire import Deadline, Wire, Unknown


class ConstructedAuthority:
    purpose = "CONSTRUCTED"

    def __init__(self, request):
        self.expected = request

    def authorize(self, request):
        return request == self.expected


class FixtureSession:
    purpose = "CONSTRUCTED"

    def __init__(self, store, native, port, trace):
        self.store, self.native = store, native
        self.client = Wire(port, Deadline.after(10), trace)
        self.receipt = dict(launch_args=["--noWorkshop"])

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
        return copy.deepcopy(native.descriptor["inventory"])


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

    def __init__(self, directory, script=None, limits=None):
        self.directory, self.script, self.limits = directory, script, limits
        self.effects = []
        self.trace = []

    @contextmanager
    def open(self, native, inputs, request, store):
        self.effects.append("constructed session owner")
        script = self.script if self.script is not None else script_for(native, store)
        with server(script, self.directory / "server") as game:
            self.game = game
            yield FixtureSession(store, native, game["port"], self.trace)


def run(frozen, store, request, authority, factory):
    from entry import enter

    children, births = {}, {}
    transport = None
    failure = None
    result = None
    with enter(frozen, store, request, authority, factory) as session:
        native = api.adapter_spec.validate(frozen["v5"], store)
        births["game"] = factory.game["birth"]
        try:
            for role in sorted(api.lifecycle.ROLES - {"game"}):
                code = "import sys,select; select.select([sys.stdin],[],[],20); sys.stdin.readline()"
                child = subprocess.Popen(
                    [sys.executable, "-c", code], stdin=subprocess.PIPE
                )
                birth = identity(child.pid)
                children[role] = api.lifecycle.OwnedChild(
                    child, child.pid, birth["start_ticks"] if birth else 0
                )
                births[role] = birth
                if birth is None:
                    raise Unknown("fixture birth missing")
            transport = Transport(session, native, store, api)
            records = collect(
                transport, births, factory.limits or native.descriptor["limits"]
            )
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
        finally:
            for owned in children.values():
                owned.process.stdin.close()
            for owned in children.values():
                try:
                    owned.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if (
                        identity(owned.pid)
                        != births[next(k for k, v in children.items() if v is owned)]
                    ):
                        raise Unknown("owned PID identity changed")
                    owned.process.kill()
                    owned.process.wait(timeout=3)
        # Game absence cannot be attested until the owning server context exits.
    cleanup = {
        role: dict(birth, gone=identity(birth["pid"]) != birth)
        for role, birth in births.items()
    }
    exits = {role: owned.process.returncode for role, owned in children.items()}
    exits["game"] = factory.game["exit_code"]
    after = {role: identity(birth["pid"]) for role, birth in births.items()}
    records = transport.records if transport else []
    receipt = dict(
        stage="AfterDriverExit",
        supervisor=identity(os.getpid()),
        births=births,
        cleanup=cleanup,
        exit_codes=exits,
        after_exit_identities=after,
        fixture="CONSTRUCTED Python processes, not game observations",
        external_finalizer_pid=os.getpid(),
    )
    handoff = dict(
        kind="CONSTRUCTED",
        binding=native.bindings(),
        births=births,
        driver_pid=births["driver"]["pid"],
        records=copy.deepcopy(records),
    )
    # Parent-owned retention, not a child's self-absence assertion.
    receipt["driver_handoff_sha256"] = api.spec.put_json(store, handoff)
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
        trace=factory.trace,
        records=records,
        pending=transport.pending if transport else None,
        source_revision=frozen["source_revision"],
        freeze_sha256=api.spec.digest(frozen),
    )
