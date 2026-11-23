"""Future authenticated native study. Never invoked by off-game verification.

No flag grants authority. Two actual parent records must independently accept
this exact candidate and then authorize its opening budget. Missing records stop
before queue/session/install/connection effects.
"""

import argparse
import copy
from pathlib import Path
import time

import accepted_api as api
from authority import ParentAuthority, descriptor
from entry import Request, preflight
from lease import Lease
from loopback_fixture import identity
from native_context import config_from, cleanup, unit_state
from native_session import NativeSession
from wire import Deadline, Unknown, decode, encoded
from wire_study import controls_gate
from wire_supervisor import Owned, atomic


@__import__("wire_supervisor").reap_children
def case_run(frozen, store, request, authority, case, total, directory):
    cfg = config_from(frozen["native"]["configuration"])
    opening = Deadline.after(900, total)
    load_end = min(time.monotonic() + 600, opening.end - 60)
    factory = NativeSession(directory, api, [], case)
    native, _ = preflight(frozen, store, request, authority, factory)
    baseline = unit_state(cfg, Deadline.after(20, total))
    if any(
        row["identity"] or row["ActiveState"] not in {"inactive", "failed"}
        for row in baseline.values()
    ):
        raise Unknown("existing harness resources are not this study's to stop")
    work = Deadline(opening.end - 60)
    work.remaining()
    directory.mkdir(parents=True, exist_ok=False)
    atomic(directory / "freeze.json", frozen)
    owners, births, lease = {}, {"game": None}, None
    error = None
    cfg_record = dict(
        freeze=str(directory / "freeze.json"),
        store=str(store.root),
        request=descriptor(request),
        binding=native.bindings(),
        case=case,
        acceptance=authority.acceptance_comment,
        budget=authority.budget_comment,
        total_end=total.end,
        work_end=work.end,
        load_end=load_end,
        limits=frozen["limits"],
    )
    try:
        for role in ("collector", "driver", "auditor", "monitor"):
            owner = Owned.start(
                [
                    frozen["native"]["tools"]["python"]["path"],
                    str(api.HERE / "roles.py"),
                    role,
                    str(directory),
                    str(work.end),
                ],
                role,
                directory,
            )
            owners[role], births[role] = owner, owner.birth
        lease = Lease(births["collector"], cfg.lock_file)
        cfg_record["births"] = births
        atomic(directory / "config.json", cfg_record)
        while owners["collector"].process.poll() is None:
            work.remaining()
            if lease.pin():
                atomic(
                    directory / "lease-ack.json",
                    dict(
                        worker=births["collector"],
                        parent=identity(__import__("os").getpid()),
                    ),
                )
            time.sleep(min(0.01, work.remaining()))
        if owners["collector"].process.returncode != 0:
            raise Unknown("native collector failed")
        for role in ("driver", "auditor", "monitor"):
            if owners[role].wait(work) != 0:
                raise Unknown("native " + role + " failed")
    except BaseException as failure:
        error = f"{type(failure).__name__}: {failure}"
    finally:
        if (
            lease
            and lease.fd is None
            and owners.get("collector")
            and owners["collector"].process.poll() is None
        ):
            lease.pin()
        for owner in owners.values():
            owner.stop(grace=min(5, max(0.01, opening.end - time.monotonic())))
    file = directory / "collector.json"
    observed = (
        decode(file.read_bytes())
        if file.exists()
        else dict(
            records=[],
            trace=[],
            pending="unreported",
            error="collector snapshot missing",
            done=False,
        )
    )
    error = error or observed["error"]
    births = observed.get("births", births)
    game = births.get("game")
    try:
        closing = cleanup(
            cfg, directory, opening, lease_held=bool(lease and lease.fd is not None)
        )
        if not closing["clean"]:
            error = error or "native cleanup unresolved"
        if game is None or identity(game["pid"]) == game:
            error = error or "game ownership/absence unresolved"
        monitor_file = directory / "monitor.json"
        monitor = decode(monitor_file.read_bytes()) if monitor_file.exists() else {}
        if not game or not any(
            r["reported"] == game and r["actual"] == game
            for r in monitor.get("games", [])
        ):
            error = error or "independent live game identity read missing"
        cleanup_map = {
            role: dict(birth, gone=identity(birth["pid"]) != birth)
            for role, birth in births.items()
            if birth
        }
        if set(cleanup_map) != api.lifecycle.ROLES or not all(
            r["gone"] for r in cleanup_map.values()
        ):
            error = error or "owned role absence coverage unresolved"
        opening.remaining()
        result = dict(
            kind="NATIVE",
            error=error,
            records=observed["records"],
            pending=observed["pending"],
            trace=observed["trace"],
            lifecycle=dict(
                births=births,
                cleanup=cleanup_map,
                workers={r: o.receipt() for r, o in owners.items()},
                game_exit_code=None,
                game_exit_scope="non-child; absence observed, exit code not inferred",
                resources=closing,
                monitor=monitor,
            ),
        )
        atomic(directory / "case-result.json", result)
        return result
    finally:
        if lease:
            lease.close()


def run(frozen, store, authority):
    request = Request(
        api.spec.digest(frozen),
        api.spec.canonical(api.adapter_spec.validate(frozen["v5"], store).bindings()),
        frozen["native"]["session_id"],
        api.spec.canonical(frozen["limits"]),
        "NATIVE",
    )
    first = frozen["controls"][0]
    # Exact source/build/config/selection/requests/budgets and external authority
    # precede every effect, including output creation and queue entry.
    factory = NativeSession(
        Path(frozen["native"]["output"]) / first["case_id"], api, [], first
    )
    native, inputs = preflight(frozen, store, request, authority, factory)
    root = Path(frozen["native"]["output"])
    root.mkdir(
        parents=True, exist_ok=False
    )  # A consumed/failed budget is never replayed.
    total = Deadline.after(frozen["limits"]["total_seconds"])
    cases = frozen["controls"] + inputs["holdout_cases"]
    if len(cases) > 5 or sum(len(c["requests"]) for c in cases) > 30:
        raise Unknown("frozen study exceeds opening/request budget")
    plan = dict(
        kind="NATIVE",
        freeze_sha256=api.spec.digest(frozen),
        source_revision=frozen["source_revision"],
        cases=cases,
        observations=[],
        admission="Unknown",
        old_holdout_cells="Unknown",
        error=None,
    )
    atomic(root / "study.json", plan)
    controls, control_cleanup = [], {}
    try:
        for index, case in enumerate(cases):
            if index == 2:
                gate = controls_gate(
                    native,
                    controls,
                    api.pipeline.runtime_policy(native, native.descriptor["inventory"]),
                    control_cleanup,
                    store,
                )
                if (
                    not gate["structural_pass"]
                    or authority.authorize(request, frozen) is not True
                ):
                    raise Unknown("fresh control admission/external authority missing")
                # Only this authenticated native orchestration can proceed. A
                # constructed gate remains Unknown and never reaches this branch.
                plan["admission"] = "fresh native controls passed literal checks"
            result = case_run(
                frozen, store, request, authority, case, total, root / case["case_id"]
            )
            plan["observations"].append(result)
            atomic(root / "study.json", plan)
            if result["error"] or result["pending"]:
                raise Unknown(result["error"] or "unreleased handle")
            if index < 2:
                if len(result["records"]) != 1:
                    raise Unknown("control opening record coverage differs")
                controls.append(copy.deepcopy(result["records"][0]))
                control_cleanup[case["case_id"]] = result["lifecycle"]["cleanup"]
            total.remaining()
    except BaseException as failure:
        plan["error"] = f"{type(failure).__name__}: {failure}"
        plan["admission"] = "Unknown"
    finally:
        plan["planned_unobserved"] = [
            c["case_id"] for c in cases[len(plan["observations"]) :]
        ]
        plan["export_qualification"] = "Unknown"
        plan["memory_or_compiler_authentication"] = False
        plan["strict_no_mods"] = False
        plan["limits"] = [
            "dynamic assembly exclusions retained",
            "three historical DLC errors remain limitations",
            "no geographic/global/service/navigation/water/certificate claim",
        ]
        atomic(root / "study.json", plan)
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--acceptance-comment", required=True)
    p.add_argument("--budget-comment", required=True)
    a = p.parse_args()
    value = run(
        api.spec.read(a.freeze),
        api.spec.ArtifactStore(a.store),
        ParentAuthority(a.acceptance_comment, a.budget_comment),
    )
    print(
        encoded(
            dict(
                error=value["error"],
                admission=value["admission"],
                export_qualification="Unknown",
            )
        ).decode()
    )


if __name__ == "__main__":
    main()
