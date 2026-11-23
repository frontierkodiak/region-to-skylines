"""One guarded foreground opening of the frozen v2 cohort; no retry or substitution.

This collector writes measurement facts only.  It never scores, never selects,
never edits the freeze and never reads an old outcome.  The driver later joins
the auditor and monitor identities into `opening.json`, which is the bundle
input.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import time
import uuid

import stock_v2 as study
from cs1_harness.cli import slot, staging
from cs1_harness.config import Config
from cs1_harness.runtime_identity import bind_runtime
from cs1_harness.session import game_pids

DEADLINE_PER_QUERY = study.STOP_POLICY["seconds_per_query"]
DEADLINE_PER_OPENING = study.STOP_POLICY["seconds_per_opening"]


def identity(pid):
    path = Path("/proc") / str(pid)
    try:
        fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": int(fields[19]), "state": fields[0]}
    except (FileNotFoundError, IndexError, ValueError):
        return None


def still_running(record):
    current = identity(record["pid"])
    return bool(
        current
        and current["start_ticks"] == record["start_ticks"]
        and current["state"] != "Z"
    )


def dump(path, value):
    return study.write(path, value)


def entry_context(stats, receipt):
    return {
        "frame": stats["frame"],
        "update_mode": stats["update_mode"],
        "invert_traffic": stats["invert_traffic"],
        "no_workshop": "--noWorkshop" in receipt["launch_args"],
        "mods_enabled": "--disableMods" not in receipt["launch_args"],
    }


def graph_value(networks):
    return {
        mode: study.old.model_fields(study.old.native_package(networks), mode)
        for mode in study.MODE_ORDER
    }


def hash_file(path):
    return study.sha(Path(path))


def walk(root):
    root = Path(root)
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []


def runtime_inventory(session, build_receipt, bindings):
    """Full file/root/plugin/assembly inventory for one phase of this opening."""
    bound = bind_runtime(session, build_receipt)
    exe = Path(bound["executable"]["path"])
    game_root = exe.parent
    plugins = {}
    for plugin in bound["status"]["plugins"]:
        plugins[plugin["name"]] = {
            "path": str(plugin["path"]),
            "enabled": bool(plugin["enabled"]),
            "builtin": bool(plugin["builtin"]),
        }
    roots = {
        "managed": game_root / "Cities_Data" / "Managed",
        "mono": game_root / "Cities_Data" / "Mono",
        "builtin_mods": game_root / "Files" / "Mods",
    }
    user_roots = {
        Path(p["path"]).parent for p in plugins.values() if not p["builtin"]
    }
    if len(user_roots) != 1:
        raise ValueError("cannot resolve one user Mods root from plugins")
    roots["user_mods"] = user_roots.pop()
    for name, plugin in plugins.items():
        roots["plugin:" + name] = Path(plugin["path"])
    files = {str(exe): {"bytes": exe.stat().st_size, "sha256": hash_file(exe)}}
    for root in roots.values():
        for path in walk(root):
            if str(path) not in files:
                files[str(path)] = {
                    "bytes": path.stat().st_size,
                    "sha256": hash_file(path),
                }
    file_hashes = {name: row["sha256"] for name, row in sorted(files.items())}
    root_rows = {
        name: {
            "path": str(root),
            "files": sorted(p for p in file_hashes if Path(p).is_relative_to(root)),
        }
        for name, root in roots.items()
    }
    assemblies = {
        row["name"]: {
            "path": row["path"],
            "sha256": row["sha256"],
            "mvid": row["loaded_module_mvid"],
        }
        for row in bound["assemblies"]
    }
    dll_path = assemblies["Cs1Harness"]["path"]
    if dll_path not in file_hashes:
        raise ValueError("harness assembly path is absent from the file inventory")
    plugin_root = Path(plugins["Cs1Harness"]["path"])
    if not Path(dll_path).is_relative_to(plugin_root):
        raise ValueError("harness assembly path is outside its plugin root")
    return {
        "pid": int(bound["host_pid"]),
        "start_ticks": int(bound["process_start_ticks"]),
        "files": file_hashes,
        "roots": root_rows,
        "plugins": plugins,
        "assemblies": assemblies,
        "unresolved": list(bound["unresolved_loaded_assemblies"]),
        "excluded_dynamic": list(bound["excluded_dynamic_assemblies"]),
        "source_sha256": bindings["source_sha256"],
        "dll_sha256": bindings["dll_sha256"],
        "protocol_sha256": bindings["protocol_sha256"],
        "executable_path": str(exe),
        "dll_path": dll_path,
    }


def build_binding(freeze, cfg):
    """Require the built DLL and staged sources to be exactly the frozen build."""
    frozen = freeze["build"]
    dll = cfg.build_dir / "Cs1Harness.dll"
    if hash_file(dll) != frozen["dll"]["sha256"]:
        raise ValueError("built DLL differs from the frozen build")
    stage = Path(frozen["source_stage"])
    actual = {p.name: hash_file(p) for p in sorted(stage.glob("*.cs"))}
    if actual != frozen["staged_sources"]:
        raise ValueError("staged study sources differ from the frozen build")
    return frozen


def plans_for(freeze, case_id, kind):
    if kind == "control":
        case = next(c for c in freeze["controls"] if c["case_id"] == case_id)
        return [
            {k: row[k] for k in ("query_id", "mode", "kind", "max_length", "request")}
            for row in case["requests"]
        ]
    return [
        {
            "query_id": row["query_id"],
            "mode": row["mode"],
            "kind": row["class"],
            "max_length": row["max_length"],
            "request": row["request"],
        }
        for row in freeze["holdout"]
        if row["case_id"] == case_id
    ]


def collect(case_id, kind, raw):
    freeze = study.read(study.HERE / "freeze.json")
    study.preflight()
    cfg = Config.for_host()
    build_receipt = build_binding(freeze, cfg)
    out = raw / case_id
    out.mkdir(parents=True, exist_ok=False)
    stage = staging(cfg, out)
    plans = plans_for(freeze, case_id, kind)
    if not plans:
        raise ValueError("no frozen request for this case")
    source_files = freeze["source_files"]
    predictions = study.read(study.HERE / "predictions.json")
    protocol = freeze["protocol"]
    observation = {
        "schema": 2,
        "study": "PL-1313",
        "case_id": case_id,
        "kind": kind,
        "started_at": study.now(),
        "finished_at": None,
        "freeze_sha256": hash_file(study.HERE / "freeze.json"),
        "build_sha256": hash_file(cfg.build_dir / "study-build-receipt.json"),
        "protocol": protocol,
        "protocol_sha256": study.digest(protocol),
        "source_files": source_files,
        "source_sha256": study.digest(source_files),
        "plans": plans,
        "request_sha256": study.digest(plans),
        "predictions": {p["query_id"]: predictions[p["query_id"]] for p in plans},
        "prediction_sha256": study.digest(
            {p["query_id"]: predictions[p["query_id"]] for p in plans}
        ),
        "session_id": f"PL-1313/{case_id}/{uuid.uuid4()}",
        "paths": [],
        "completed": False,
        "error": None,
        "observed_game_processes": [],
        "collector": identity(os.getpid()),
        "runtime": {},
        "opening_graph_sha256": None,
        "post_graph_sha256": None,
    }
    package = next(
        (c for c in freeze["controls"] if c["case_id"] == case_id), None
    )
    if package is not None:
        observation["artifact_sha256"] = package["sha256"]
        if hash_file(package["locator"]) != package["sha256"]:
            raise ValueError("control package bytes changed")
    else:
        row = next(r for r in freeze["holdout"] if r["case_id"] == case_id)
        observation["artifact_sha256"] = row["package_sha256"]
        if hash_file(row["package_locator"]) != row["package_sha256"]:
            raise ValueError("holdout package bytes changed")
    locator = (
        package["locator"]
        if package is not None
        else next(r for r in freeze["holdout"] if r["case_id"] == case_id)["package_locator"]
    )
    seen = {}
    session = None
    deadline = None
    try:
        with slot(
            cfg,
            stage,
            0,
            {"command": "connections", "issue": "PL-1313", "label": case_id},
        ) as session:
            deadline = time.monotonic() + DEADLINE_PER_OPENING
            try:
                session.require_offline = True
                session.record = False
                session.live = False
                installed = session.install_map(Path(locator))
                session.launch(["--noWorkshop"])
                for pid in game_pids(cfg.display):
                    record = identity(pid)
                    if record:
                        seen[(pid, record["start_ticks"])] = record
                bindings = {
                    "source_sha256": study.digest(source_files),
                    "dll_sha256": build_receipt["dll"]["sha256"],
                    "protocol_sha256": study.digest(protocol),
                }
                observation["bindings"] = bindings
                observation["policy"] = runtime_inventory(session, build_receipt, bindings)
                observation["runtime"]["launch"] = observation["policy"]
                client = session.client
                entry = next(
                    m
                    for m in client.call("maps")["maps"]
                    if m.get("path") and Path(m["path"]).samefile(installed)
                )
                observation["listed"] = entry
                observation["new_game_protocol"] = client.call(
                    "new_game", path=entry["path"]
                )
                observation["loaded"] = client.wait(
                    lambda state: state.get("in_game") and not state.get("loading"),
                    study.STOP_POLICY["seconds_load"],
                    "New Game",
                    alive=session.alive,
                )
                observation["native_context"] = entry_context(
                    client.call("stats"), session.receipt
                )
                client.call("run", paused=True)
                networks = client.call("networks")
                opening_graph = graph_value(networks)
                opening_hash = dump(out / "graph-opening.json", opening_graph)
                dump(out / "networks-opening.json", networks)
                observation["opening_graph_sha256"] = opening_hash
                observation["runtime"]["pre"] = runtime_inventory(
                    session, build_receipt, observation["bindings"]
                )
                client.call("run", paused=False, speed=1)
                for plan in plans:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("opening deadline exceeded")
                    row = {
                        "plan": plan,
                        "submitted_at": study.now(),
                        "pre_context": entry_context(client.call("stats"), session.receipt),
                        "pre_build_index": client.call("study_build_index")["build_index"],
                        "pre_graph": dump(out / f"graph-pre-{plan['query_id'].replace('/', '_')}.json", graph_value(client.call("networks"))),
                    }
                    try:
                        started = client.call(
                            "path_start",
                            **{
                                "from": plan["request"]["from"],
                                "to": plan["request"]["to"],
                                "mode": study.MODES[plan["mode"]],
                                "max_length": plan["max_length"],
                            },
                        )
                        row["effective"] = started
                        if started.get("max_length") != plan["max_length"]:
                            raise ValueError("budget unsupported or clamped at entry")
                        query_deadline = time.monotonic() + DEADLINE_PER_QUERY
                        while True:
                            session.alive()
                            reply = client.call("path_result", id=started["id"])
                            if reply.get("complete") or time.monotonic() >= query_deadline:
                                break
                            time.sleep(0.1)
                        row["result"] = reply
                        row["post_context"] = entry_context(
                            client.call("stats"), session.receipt
                        )
                        row["post_graph"] = dump(
                            out / f"graph-post-{plan['query_id'].replace('/', '_')}.json",
                            graph_value(client.call("networks")),
                        )
                        if not reply.get("complete"):
                            raise RuntimeError(
                                f"incomplete path for {plan['query_id']}; retain Unknown"
                            )
                    except Exception as error:  # noqa: BLE001 - retained verbatim
                        row["error"] = f"{type(error).__name__}: {error}"
                        row["submitted_at"] = row.get("submitted_at") or study.now()
                        observation["paths"].append(row)
                        raise
                    observation["paths"].append(row)
                    dump(out / "observation.json", observation)
                client.call("run", paused=True)
                post_networks = client.call("networks")
                dump(out / "networks-post.json", post_networks)
                observation["post_graph_sha256"] = dump(
                    out / "graph-post.json", graph_value(post_networks)
                )
                observation["runtime"]["post"] = runtime_inventory(
                    session, build_receipt, observation["bindings"]
                )
                observation["completed"] = True
            finally:
                for pid in game_pids(cfg.display):
                    record = identity(pid)
                    if record:
                        seen[(pid, record["start_ticks"])] = record
                observation["observed_game_processes"] = list(seen.values())
    except Exception as error:  # noqa: BLE001 - retained verbatim
        observation["error"] = f"{type(error).__name__}: {error}"
    finally:
        observation["finished_at"] = study.now()
        if session is not None:
            observation["session"] = session.receipt
        observation["game_cleanup_coverage"] = [
            {**record, "still_running": still_running(record)}
            for record in seen.values()
        ]
        dump(out / "observation.json", observation)
        for name in ("game.log", "gpu.csv"):
            if (stage / name).exists():
                shutil.copyfile(stage / name, out / name)
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    freeze = study.read(study.HERE / "freeze.json")
    kind = (
        "control"
        if any(c["case_id"] == args.case_id for c in freeze["controls"])
        else "holdout"
    )
    result = collect(args.case_id, kind, args.raw)
    print(
        study.encoded(
            {"completed": result["completed"], "error": result.get("error")}
        ).decode()
    )
    raise SystemExit(0 if result["completed"] else 1)


if __name__ == "__main__":
    main()
