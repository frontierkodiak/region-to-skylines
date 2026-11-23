"""Input-only holdout plans and fresh-control admission; no historical scoring."""

import copy

import accepted_api as api
from wire import Unknown


def holdout_cases(native, inputs, store, retain=True):
    groups = {}
    for row in inputs["holdout"]:
        case = groups.setdefault(row["case_id"], [])
        case.append(row)
    if len(groups) > 3:
        raise Unknown("holdout opening budget exceeded")
    result = []
    sources = native.value["sources"]["readiness_helpers"]
    protocol = store.json(native.value["inputs"]["protocol"], "protocol")
    put = api.spec.put_json if retain else lambda s, v: api.spec.digest(v)
    for case_id, rows in groups.items():
        hashed, locator = rows[0]["package_sha256"], rows[0]["package_locator"]
        if any(
            r["package_sha256"] != hashed or r["package_locator"] != locator
            for r in rows
        ):
            raise Unknown("holdout case combines packages")
        plans = [
            dict(
                query_id=r["query_id"],
                mode=r["mode"],
                kind="holdout",
                max_length=r["max_length"],
                request=copy.deepcopy(r["request"]),
            )
            for r in rows
        ]
        for plan in plans:
            if (
                plan["max_length"] != 100000
                or plan["request"]["capability"] != plan["mode"]
            ):
                raise Unknown("holdout literal plan differs")
            api.consumer.Request(
                plan["mode"],
                api.consumer.position(plan["request"]["from"]),
                api.consumer.position(plan["request"]["to"]),
                100000,
                0,
            )
        predictions = {r["query_id"]: r["prediction"] for r in rows}
        case = dict(
            case_id=case_id,
            artifact_sha256=hashed,
            source_files=sources["files"],
            source_sha256=sources["sha256"],
            requests=plans,
            request_sha256=put(store, plans),
            predictions=predictions,
            prediction_sha256=put(store, predictions),
            protocol_sha256=native.value["inputs"]["protocol"],
            exact_graph_sha256=inputs["input_graphs"][hashed],
        )
        case["consumed_fields"] = api.spec.consumed(
            store, case, protocol, retain=retain
        )
        result.append(case)
    if sum(len(c["requests"]) for c in result) > 18:
        raise Unknown("holdout request budget exceeded")
    return result


def controls_gate(native, records, policy, cleanup, store):
    """Apply the unchanged control consumer after external process finalization."""
    if len(records) != 2 or [r["case_id"] for r in records] != [
        c["case_id"] for c in native.value["controls"]
    ]:
        raise Unknown("fresh control coverage missing")
    prior = set(native.value["prior_sessions"])
    for control, record in zip(native.value["controls"], records, strict=True):
        observed = copy.deepcopy(record["observed"])
        observed["cleanup"] = cleanup[control["case_id"]]
        observed["owned_processes"] = cleanup[control["case_id"]]
        api.consumer.opening(control, observed, policy, prior, store, native)
        prior.add(observed["session_id"])
    return dict(structural_pass=True, real_admission=False, control_admission="Unknown")


def constructed_case_gate(native, case, records, policy, cleanup, store):
    if (
        len(records) != 1
        or records[0]["case_id"] != case["case_id"]
        or records[0]["kind"] != "CONSTRUCTED"
    ):
        raise Unknown("constructed case coverage/provenance differs")
    observed = copy.deepcopy(records[0]["observed"])
    observed["cleanup"], observed["owned_processes"] = cleanup, cleanup
    if case["case_id"] in {c["case_id"] for c in native.value["controls"]}:
        api.consumer.opening(
            case, observed, policy, set(native.value["prior_sessions"]), store, native
        )
    else:
        if (
            not observed["completed"]
            or observed["error"]
            or observed["opening_graph"] != case["exact_graph_sha256"]
            or observed["post_graph"] != case["exact_graph_sha256"]
        ):
            raise Unknown("holdout case incomplete/drifted")
        if [r["plan"] for r in observed["paths"]] != case["requests"]:
            raise Unknown("holdout request order/coverage differs")
        for row in observed["paths"]:
            plan = row["plan"]
            req = api.consumer.Request(
                plan["mode"],
                api.consumer.position(plan["request"]["from"]),
                api.consumer.position(plan["request"]["to"]),
                100000,
                row["pre_build_index"],
            )
            decision = api.consumer.decide(row["effective"], row["result"], req)
            if (
                decision.literal_label.value not in {"success", "no_path"}
                or decision.literal_label.value != row["literal_label"]
            ):
                raise Unknown("holdout literal result invalid")
    return dict(
        structural_pass=True,
        control_admission="Unknown",
        export_qualification="Unknown",
        runtime_facts="CONSTRUCTED",
        native_requests=0,
        game_openings=0,
        fresh_build=False,
    )
