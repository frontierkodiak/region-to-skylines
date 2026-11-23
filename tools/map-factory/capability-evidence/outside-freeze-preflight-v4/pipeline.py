"""Spec-driven collector/bundle boundary and explicitly constructed consumer run.

No launch/queue operation exists here. Collection binds before a runtime fact is
accepted. Bundle construction checks that binding, never projects a source map.
"""

from __future__ import annotations

import copy
from pathlib import Path

import spec as contract
from spec import schema, ProtocolError, exact
import consumer

KINDS = frozenset({"CONSTRUCTED"})


def collector_binding(spec):
    return spec.bindings()


def runtime_policy(spec, inventory):
    """At collection entry, bind independently captured inventory to this spec."""
    keys = schema.POLICY - {"source_sha256", "protocol_sha256", "dll_sha256"}
    exact(inventory, keys, "unbound runtime inventory")
    result = copy.deepcopy(inventory)
    result.update({k: v for k, v in spec.bindings().items() if k in schema.POLICY})
    return result


def validate_policy(spec, policy, store):
    import build_v2

    schema.runtime_inventory(policy, store, "runtime policy", phase=False)
    expected = spec.value["expected_policy"]
    if sorted(policy["process_roles"]) != sorted(expected["process_roles"]):
        raise ProtocolError("exact runtime process role coverage differs")
    if Path(policy["executable_path"]).name != expected["executable_name"]:
        raise ProtocolError("runtime executable name differs")
    if policy["excluded_dynamic"] != expected["excluded_dynamic"]:
        raise ProtocolError("runtime dynamic exclusions differ")
    for key in ("source_sha256", "protocol_sha256", "dll_sha256"):
        if policy[key] != spec.bindings()[key]:
            raise ProtocolError("runtime policy role binding differs")
    for name, assembly in policy["assemblies"].items():
        actual = build_v2.module_version_id(store.root / assembly["sha256"])
        if actual != assembly["mvid"]:
            raise ProtocolError(
                "runtime assembly MVID differs from retained bytes: " + name
            )


def check_binding(spec, binding):
    exact(binding, set(spec.bindings()), "collector binding")
    if binding != spec.bindings():
        raise ProtocolError("collector/spec role binding differs")


def bundle(spec, records, policy, store):
    """No remapping here: the same preflight spec controls every edge."""
    contract.validate(spec.value, store)
    validate_policy(spec, policy, store)
    if type(records) is not list:
        raise ProtocolError("collector records require list")
    ids = [c["case_id"] for c in spec.value["controls"]]
    if len(records) != len(ids) or [r.get("case_id") for r in records] != ids:
        raise ProtocolError("collector opening set differs")
    observations = {}
    for record in records:
        exact(record, {"case_id", "kind", "binding", "observed"}, "collector record")
        if record["kind"] not in KINDS:
            raise ProtocolError(
                "real collection unsupported: separate authorization/adapter required"
            )
        check_binding(spec, record["binding"])
        exact(record["observed"], schema.OBSERVED, "collector observation")
        observations[record["case_id"]] = record["observed"]
    return {
        "version": 4,
        "kind": "CONSTRUCTED",
        "binding": spec.bindings(),
        "controls": spec.value["controls"],
        "observations": observations,
        "policy": policy,
        "prior_sessions": spec.value["prior_sessions"],
    }


def gate(value, frozen, store):
    spec = contract.validate(frozen, store)
    b = exact(
        value,
        {
            "version",
            "kind",
            "binding",
            "controls",
            "observations",
            "policy",
            "prior_sessions",
        },
        "v4 bundle",
    )
    if type(b["version"]) is not int or b["version"] != 4 or b["kind"] != "CONSTRUCTED":
        raise ProtocolError("unsupported/non-constructed bundle")
    check_binding(spec, b["binding"])
    if (
        b["controls"] != spec.value["controls"]
        or b["prior_sessions"] != spec.value["prior_sessions"]
    ):
        raise ProtocolError("bundle differs from validated spec")
    validate_policy(spec, b["policy"], store)
    ids = {c["case_id"] for c in b["controls"]}
    exact(b["observations"], ids, "control observation set")
    sessions = set(b["prior_sessions"])
    for control in b["controls"]:
        o = b["observations"][control["case_id"]]
        consumer.opening(control, o, b["policy"], sessions, store, spec)
        sessions.add(o["session_id"])
    return {
        "stage": "ConstructedConsumerExercise",
        "structural_consumer_pass": True,
        "control_admission": "unknown",
        "pre_export_qualification": "unknown",
        "real_certificate": False,
        "native_observations": 0,
        "reason": "CONSTRUCTED facts cannot admit real controls",
    }


def constructed(spec, store, cleanup):
    """Generate results from literal plans, never replay old measured outcomes."""
    # Only old inventory/policy bytes are reused, as an explicitly CONSTRUCTED
    # runtime. No historical effective args, results or labels are read here.
    old_policy = contract.read(contract.OLD / "bundle.json")["policy"]
    inventory = {
        k: v
        for k, v in old_policy.items()
        if k not in {"source_sha256", "protocol_sha256", "dll_sha256"}
    }
    policy = runtime_policy(spec, inventory)
    schema.runtime_inventory(policy, store, "CONSTRUCTED policy", phase=False)
    records = []
    context = {
        "update_mode": "NewGameFromMap",
        "frame": 1,
        "mods_enabled": True,
        "no_workshop": True,
        "invert_traffic": False,
    }
    for c in spec.value["controls"]:
        phase = {k: copy.deepcopy(v) for k, v in policy.items() if k != "process_roles"}
        phase.update(cleanup["births"]["game"], unresolved=[])
        o = {k: copy.deepcopy(c[k]) for k in schema.HASHES | {"consumed_fields"}}
        o.update(
            completed=True,
            error=None,
            session_id="CONSTRUCTED-v4/" + c["case_id"],
            native_context=context,
            opening_graph=c["exact_graph_sha256"],
            post_graph=c["exact_graph_sha256"],
            runtime={n: copy.deepcopy(phase) for n in ("launch", "pre", "post")},
            owned_processes=cleanup["cleanup"],
            cleanup=cleanup["cleanup"],
            paths=[],
        )
        for index, plan in enumerate(c["requests"], 1):
            mode = plan["mode"]
            ok = plan["kind"] == "positive"
            effective = {
                "ok": True,
                "id": index,
                "mode": {"road": "car", "ship": "ship", "air": "plane"}[mode],
                "from": plan["request"]["from"],
                "to": plan["request"]["to"],
                "max_length": 100000,
                "build_index": index,
                "seed": 857,
                "vehicle": {"road": "Car", "ship": "Ship", "air": "Plane"}[mode],
                "category": "PassengerCar" if mode == "road" else "All",
                "lane_types": "Vehicle"
                if mode == "road"
                else "Vehicle, TransportVehicle, CargoVehicle",
            }
            o["paths"].append(
                {
                    "plan": plan,
                    "pre_build_index": index,
                    "pre_graph": c["exact_graph_sha256"],
                    "post_graph": c["exact_graph_sha256"],
                    "pre_context": dict(context, frame=2),
                    "post_context": dict(context, frame=2),
                    "effective": effective,
                    "result": {
                        "ok": True,
                        "id": index,
                        "complete": True,
                        "released": True,
                        "success": ok,
                        "length": 1 if ok else 0,
                        "flags": 4 if ok else 8,
                        "positions": [plan["request"]["from"], plan["request"]["to"]]
                        if ok
                        else [],
                    },
                    "error": None,
                }
            )
        records.append(
            {
                "case_id": c["case_id"],
                "kind": "CONSTRUCTED",
                "binding": collector_binding(spec),
                "observed": o,
            }
        )
    return records, policy
