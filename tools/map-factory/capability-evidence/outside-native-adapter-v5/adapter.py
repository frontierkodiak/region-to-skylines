"""Adapter effect boundary, collection, retention, bundle and external finalization.

Only a finite recording transport is shipped. No live native transport or grant
is supplied. A future study grant is additional authority, not a freeze field.
"""

from dataclasses import dataclass, field
import copy
import os
import subprocess
import sys
import time

from api import HERE, spec, pipeline, consumer, lifecycle
import adapter_spec


@dataclass
class RecordingTransport:
    calls: list = field(default_factory=list)

    def enter(self, binding):
        self.calls.append(
            {"effect": "CONSTRUCTED queue/launcher seam", "binding": binding}
        )

    def prepare(self, native, store, births):
        fixture = dict(births=births, cleanup={})
        self.records, _ = pipeline.constructed(native.baseline, store, fixture)
        self.inventory = native.descriptor["inventory"]
        self.store = store

    def call(self, operation, case, index=None, arguments=None):
        self.calls.append(
            dict(operation=operation, case=case, index=index, arguments=arguments)
        )
        observed = next(r["observed"] for r in self.records if r["case_id"] == case)
        if operation == "inventory":
            return copy.deepcopy(self.inventory)
        if operation == "opening":
            return copy.deepcopy(
                {
                    k: v
                    for k, v in observed.items()
                    if k not in {"paths", "cleanup", "owned_processes", "runtime"}
                }
            )
        row = observed["paths"][index]
        if operation == "study_build_index":
            return row["pre_build_index"]
        if operation == "create_path":
            if arguments != row["plan"]:
                raise ValueError("request arguments differ from frozen literal plan")
            return copy.deepcopy(row["effective"])
        if operation == "path_result_and_release":
            return copy.deepcopy(row["result"])
        if operation in {"query_pre", "query_post"}:
            return {
                k: copy.deepcopy(v)
                for k, v in row.items()
                if k
                in (
                    {"pre_graph", "pre_context"}
                    if operation == "query_pre"
                    else {"post_graph", "post_context", "error"}
                )
            }
        raise ValueError("unsupported finite stub operation")

    def read_file(self, path):
        return self.store.read(
            self.inventory["files"][path], "CONSTRUCTED runtime bytes"
        )


def collect(native, store, births, transport, clock=time.monotonic):
    """Collection entry, independent pre-call readback, inventory and literal requests.

    The transport owns the native/queue/launcher I/O seam; none is connected here.
    No prediction, decoder or request repair is performed by this collector.
    """
    started = clock()

    def deadline(start, seconds):
        if clock() - start >= seconds or clock() - started >= 4500:
            raise ValueError("STOP Unknown: deadline; no retry/replacement")

    binding = pipeline.collector_binding(native)
    transport.prepare(native, store, births)
    records = []
    policy = pipeline.runtime_policy(native, native.descriptor["inventory"])
    controls = native.value["controls"]
    if len(controls) > 2 or sum(len(c["requests"]) for c in controls) != 12:
        raise ValueError("STOP Unknown: fixed control count")
    for control in controls:
        opening_started = clock()
        deadline(started, 4500)
        load_started = clock()
        case = control["case_id"]
        observed = transport.call("opening", case)
        deadline(load_started, 600)
        observed.update(paths=[], cleanup={}, owned_processes={}, runtime={})
        for phase in ("launch", "pre"):
            inv = transport.call("inventory", case)
            captured = retain_inventory(native, inv, transport.read_file, store)
            observed["runtime"][phase] = dict(
                {k: v for k, v in captured.items() if k != "process_roles"},
                **births["game"],
                unresolved=[],
            )
        for index, plan in enumerate(control["requests"]):
            deadline(opening_started, 900)
            query_started = clock()
            context = transport.call("query_pre", case, index)
            if context["pre_graph"] != control["exact_graph_sha256"]:
                raise ValueError("STOP Unknown: pre-query graph drift")
            before = transport.call("study_build_index", case, index)
            effective = transport.call("create_path", case, index, plan)
            result = transport.call("path_result_and_release", case, index)
            context.update(transport.call("query_post", case, index))
            deadline(query_started, 30)
            request = consumer.Request(
                plan["mode"],
                consumer.position(plan["request"]["from"]),
                consumer.position(plan["request"]["to"]),
                plan["max_length"],
                consumer.integer(before, 0, 2**32 - 1),
            )
            decision = consumer.decide(effective, result, request)
            expected = {
                "positive": consumer.Label.SUCCESS,
                "invalid-vehicle": consumer.Label.NO_PATH,
            }[plan["kind"]]
            if (
                decision.literal_label != expected
                or context["post_graph"] != control["exact_graph_sha256"]
                or context["error"] is not None
            ):
                raise ValueError(
                    "STOP Unknown: query fidelity/result failure; no retry"
                )
            observed["paths"].append(
                dict(
                    context,
                    plan=copy.deepcopy(plan),
                    pre_build_index=before,
                    effective=effective,
                    result=result,
                )
            )
        inv = transport.call("inventory", case)
        captured = retain_inventory(native, inv, transport.read_file, store)
        observed["runtime"]["post"] = dict(
            {k: v for k, v in captured.items() if k != "process_roles"},
            **births["game"],
            unresolved=[],
        )
        deadline(opening_started, 900)
        if captured != policy:
            raise ValueError("runtime drift")
        records.append(
            dict(
                case_id=case,
                kind="CONSTRUCTED",
                binding=copy.deepcopy(binding),
                observed=observed,
            )
        )
    return records


def preflight(
    frozen, store, authority=None, transport=None, source_root=adapter_spec.ROOT
):
    native = adapter_spec.validate(frozen, store, source_root)
    binding = pipeline.collector_binding(native)  # Before any collection/effect.
    grant = spec.exact(authority, {"kind", "spec_sha256", "binding"}, "study authority")
    if grant["spec_sha256"] != native.sha256 or grant["binding"] != binding:
        raise ValueError("authority is for a different source/build/spec")
    if (
        grant["kind"] != "OFFLINE_CONSTRUCTED_ONLY"
        or type(transport) is not RecordingTransport
    ):
        raise ValueError(
            "native study requires separate explicit reviewed authorization and transport"
        )
    # Runtime policy construction at collection entry; no effect before all checks.
    policy = pipeline.runtime_policy(native, native.descriptor["inventory"])
    pipeline.validate_policy(native, policy, store)
    transport.enter(copy.deepcopy(binding))
    return native, binding, policy


def retain_inventory(native, inventory, byte_reader, store):
    """Read and retain every file/assembly at capture, not later during bundling."""
    if spec.canonical(inventory) != spec.canonical(native.descriptor["inventory"]):
        raise ValueError("full captured roots/plugins/files/assemblies differ")
    for path, key in inventory["files"].items():
        if spec.put(store, byte_reader(path)) != key:
            raise ValueError("inventoried file bytes differ: " + path)
    for assembly in inventory["assemblies"].values():
        if spec.put(store, byte_reader(assembly["path"])) != assembly["sha256"]:
            raise ValueError("inventoried assembly differs")
    policy = pipeline.runtime_policy(native, inventory)
    pipeline.validate_policy(native, policy, store)
    return policy


def supervise(native, store, directory, transport=None):
    """External owner captures five births; driver writes facts and actually exits."""
    directory.mkdir(parents=True, exist_ok=False)
    children, births = {}, {}
    handoff = directory / "driver.json"
    try:
        for role in sorted(lifecycle.ROLES):
            argv = (
                [sys.executable, str(HERE / "driver.py"), str(handoff)]
                if role == "driver"
                else [sys.executable, "-c", "import sys; sys.stdin.readline()"]
            )
            child = subprocess.Popen(argv, stdin=subprocess.PIPE)
            birth = lifecycle.identity(child.pid)
            children[role] = lifecycle.OwnedChild(
                child, child.pid, birth["start_ticks"] if birth else 0
            )
            if birth is None:
                raise ValueError("birth missing")
            births[role] = birth
        # Collection happens through the same request seam used by the adapter.
        # Only the injected finite transport supplies constructed native facts.
        transport = transport or RecordingTransport()
        records = collect(native, store, births, transport)
        # Driver writes observations, never cleanup/absence attestations.
        payload = dict(
            kind="CONSTRUCTED",
            binding=pipeline.collector_binding(native),
            births=births,
            driver_pid=children["driver"].pid,
            records=records,
        )
        children["driver"].process.stdin.write(spec.canonical(payload) + b"\n")
        children["driver"].process.stdin.flush()
        children["driver"].process.wait(timeout=10)
        if spec.read(handoff) != payload:
            raise ValueError("driver handoff differs")
    finally:
        for owned in children.values():
            child = owned.process
            if child.poll() is None:
                try:
                    child.stdin.write(b"exit\n")
                    child.stdin.flush()
                except BrokenPipeError:
                    pass
        for owned in children.values():
            try:
                owned.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                owned.process.kill()  # Exact finite owned Python child only.
                owned.process.wait()
            owned.process.stdin.close()
    receipt = lifecycle.finalize(children, births)
    receipt["driver_handoff_sha256"] = spec.put(store, handoff.read_bytes())
    receipt["external_finalizer_pid"] = os.getpid()
    return receipt


def bundle(native, binding, records, policy, cleanup, store):
    adapter_spec.validate(native.descriptor, store)
    pipeline.check_binding(native, binding)
    # Actual v4 bundle code consumes the same composed API view unchanged.
    inner = pipeline.bundle(native, records, policy, store)
    return dict(
        version=5,
        spec_bytes=native.encoded.decode(),
        binding=binding,
        inner=inner,
        lifecycle=cleanup,
    )


def gate(value, frozen, store):
    native = adapter_spec.validate(frozen, store)
    b = spec.exact(
        value,
        {"version", "spec_bytes", "binding", "inner", "lifecycle"},
        "adapter bundle",
    )
    if (
        type(b["version"]) is not int
        or b["version"] != 5
        or b["spec_bytes"].encode() != native.encoded
    ):
        raise ValueError("bundle spec bytes changed")
    pipeline.check_binding(native, b["binding"])
    inner = spec.exact(
        b["inner"],
        {
            "version",
            "kind",
            "binding",
            "controls",
            "observations",
            "policy",
            "prior_sessions",
        },
        "inner consumer bundle",
    )
    if inner["version"] != 4 or inner["kind"] != "CONSTRUCTED":
        raise ValueError("constructed adapter proof only")
    pipeline.check_binding(native, inner["binding"])
    expected_policy = pipeline.runtime_policy(native, native.descriptor["inventory"])
    if inner["policy"] != expected_policy:
        raise ValueError("full frozen runtime inventory differs")
    pipeline.validate_policy(native, inner["policy"], store)
    if (
        inner["controls"] != native.value["controls"]
        or inner["prior_sessions"] != native.value["prior_sessions"]
    ):
        raise ValueError("bundle inputs differ")
    spec.exact(
        inner["observations"],
        {c["case_id"] for c in native.value["controls"]},
        "opening coverage",
    )
    validate_cleanup(b["lifecycle"], store)
    handoff = store.json(b["lifecycle"]["driver_handoff_sha256"], "driver records")
    pipeline.check_binding(native, handoff["binding"])
    expected_observations = {}
    for record in handoff["records"]:
        pipeline.check_binding(native, record["binding"])
        observed = copy.deepcopy(record["observed"])
        if observed["cleanup"] or observed["owned_processes"]:
            raise ValueError("child self-attested cleanup")
        observed["cleanup"] = b["lifecycle"]["cleanup"]
        observed["owned_processes"] = b["lifecycle"]["cleanup"]
        expected_observations[record["case_id"]] = observed
    if inner["observations"] != expected_observations:
        raise ValueError("bundle observations changed after driver exit")
    prior = set(native.value["prior_sessions"])
    for c in native.value["controls"]:
        observed = inner["observations"][c["case_id"]]
        if observed["cleanup"] != b["lifecycle"]["cleanup"]:
            raise ValueError("observation cleanup differs from external finalizer")
        consumer.opening(c, observed, inner["policy"], prior, store, native)
        prior.add(observed["session_id"])
    return dict(
        structural_pass=True,
        fresh_build="actual offline compilation",
        runtime_facts="CONSTRUCTED",
        native_requests=0,
        game_openings=0,
        control_admission="Unknown",
        export_qualification="Unknown",
    )


def validate_cleanup(receipt, store):
    births = spec.exact(receipt["births"], lifecycle.ROLES, "five birth roles")
    spec.exact(receipt["cleanup"], lifecycle.ROLES, "five cleanup roles")
    spec.exact(receipt["exit_codes"], lifecycle.ROLES, "five exit codes")
    spec.exact(receipt["after_exit_identities"], lifecycle.ROLES, "five absence reads")
    if (
        receipt["stage"] != "AfterDriverExit"
        or len({b["pid"] for b in births.values()}) != 5
    ):
        raise ValueError("distinct five-role post-exit coverage required")
    supervisor = receipt["supervisor"]
    if (
        supervisor["pid"] in {b["pid"] for b in births.values()}
        or receipt["external_finalizer_pid"] != supervisor["pid"]
    ):
        raise ValueError("self attestation")
    handoff = store.json(receipt["driver_handoff_sha256"], "actual driver handoff")
    if handoff["births"] != births or handoff["driver_pid"] != births["driver"]["pid"]:
        raise ValueError("driver birth/handoff differs")
    for role, birth in births.items():
        if (
            receipt["cleanup"][role] != dict(birth, gone=True)
            or receipt["exit_codes"][role] != 0
        ):
            raise ValueError("unclean exit")
        if receipt["after_exit_identities"][role] == birth:
            raise ValueError("original PID/start still present")


def exercise(frozen, store, directory, authority, transport):
    native, binding, policy = preflight(frozen, store, authority, transport)
    cleanup = supervise(native, store, directory, transport)
    handoff = store.json(cleanup["driver_handoff_sha256"], "driver observations")
    records = handoff["records"]
    for record in records:
        record["observed"]["owned_processes"] = copy.deepcopy(cleanup["cleanup"])
        record["observed"]["cleanup"] = copy.deepcopy(cleanup["cleanup"])
    result = bundle(native, binding, records, policy, cleanup, store)
    return result, gate(result, frozen, store)
