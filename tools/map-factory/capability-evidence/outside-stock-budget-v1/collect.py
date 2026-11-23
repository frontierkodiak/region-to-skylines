"""One guarded foreground opening; no retries or substitutions after outcomes."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import time

import study
from cs1_harness.cli import slot, staging
from cs1_harness.config import Config
from cs1_harness.runtime_identity import bind_runtime
from cs1_harness.session import game_pids


def process_identity(pid):
    path = Path("/proc") / str(pid)
    try:
        fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": fields[19], "state": fields[0]}
    except FileNotFoundError:
        return None


def still_running(identity):
    current = process_identity(identity["pid"])
    return bool(
        current
        and current["start_ticks"] == identity["start_ticks"]
        and current["state"] != "Z"
    )


def dump(path, value):
    path.write_bytes(study.encoded(value))


def identity_with_files(session, build):
    identity = bind_runtime(session, build)
    cfg = session.cfg
    roots = [
        cfg.game_dir / "Cities_Data/Managed",
        cfg.game_dir / "Cities_Data/Mono",
        cfg.game_dir / "Files/Mods",
        cfg.data_dir / "Addons/Mods",
    ]
    proc_root = Path("/proc") / str(identity["host_pid"]) / "root"
    roots.extend(
        proc_root / Path(p["path"]).relative_to("/")
        for p in identity["status"]["plugins"]
        if p.get("path") and Path(p["path"]).is_absolute()
    )
    files = {cfg.game_dir / "Cities.x64"}
    for root in roots:
        if root.is_dir():
            files.update(p for p in root.rglob("*") if p.is_file())
    identity["file_inventory"] = {
        str(p): {"bytes": p.stat().st_size, "sha256": study.sha(p)}
        for p in sorted(files)
    }
    identity["inventory_roots"] = {str(p): p.is_dir() for p in roots}
    return identity


def graph(networks):
    # Includes positions/chords, flags, lane eligibility/directions, full keys.
    return study.digest(
        {m: study.model_fields(study.native_package(networks), m) for m in study.MODES}
    )


def requests_for(case, kind):
    if kind == "control":
        return case["requests"]
    if kind == "holdout":
        return [
            dict(q, mode=m, max_length=100000)
            for m, values in case["modes"].items()
            for q in values["selected"]
        ]
    rows = []
    for row in case["rows"]:
        for budget in study.BUDGETS:
            rows.append(
                {
                    "query_id": f"intervention/{row['canonical_request_sha256']}/{budget}",
                    "request": row["request"],
                    "mode": "road",
                    "max_length": budget,
                    "old_query_id": row["old_query_id"],
                }
            )
    return rows


def entry_valid(context):
    return (
        context["invert_traffic"] == "False"
        and context["update_mode"] == "NewGameFromMap"
        and context["no_workshop"] is True
        and context["mods_enabled"] is True
    )


def collect(case, kind, raw):
    study.check()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=study.ROOT, text=True
    ).strip()
    committed = subprocess.check_output(
        [
            "git",
            "show",
            f"{commit}:{(study.HERE / 'freeze.json').relative_to(study.ROOT)}",
        ],
        cwd=study.ROOT,
    )
    if committed != (study.HERE / "freeze.json").read_bytes():
        raise ValueError("freeze is not published in the pre-query commit")
    cfg = Config.for_host()
    out = raw / case["case_id"]
    out.mkdir(parents=True, exist_ok=False)
    stage = staging(cfg, out)
    requests = requests_for(case, kind)
    observation = {
        "schema": 1,
        "case_id": case["case_id"],
        "kind": kind,
        "started_at": study.now(),
        "artifact_sha256": study.sha(case["locator"]),
        "freeze_sha256": study.sha(study.HERE / "freeze.json"),
        "protocol": study.PROTOCOL,
        "paths": [],
        "completed": False,
        "observed_game_processes": [],
        "collector": process_identity(os.getpid()),
    }
    if observation["artifact_sha256"] != case["sha256"]:
        raise ValueError("package bytes changed")
    session = None
    seen = {}
    try:
        with slot(
            cfg,
            stage,
            0,
            {"command": "connections", "issue": "PL-1294", "label": case["case_id"]},
        ) as session:
            try:
                build = study.read(study.HERE / "build.json")["build_receipt"]
                if study.read(cfg.build_dir / "build-receipt.json") != build:
                    raise ValueError("staged build differs")
                observation["build_receipt"] = build
                session.require_offline = True
                session.record = False
                session.live = False
                installed = session.install_map(Path(case["locator"]))
                session.launch(["--noWorkshop"])
                for pid in game_pids(cfg.display):
                    p = process_identity(pid)
                    if p:
                        seen[(pid, p["start_ticks"])] = p
                c = session.client
                observation["launch_runtime_identity"] = identity_with_files(
                    session, build
                )
                entry = next(
                    m
                    for m in c.call("maps")["maps"]
                    if m.get("path") and Path(m["path"]).samefile(installed)
                )
                observation["listed"] = entry
                observation["new_game_protocol"] = c.call(
                    "new_game", path=entry["path"]
                )
                observation["loaded"] = c.wait(
                    lambda st: st.get("in_game") and not st.get("loading"),
                    600,
                    "New Game",
                    alive=session.alive,
                )
                stats = c.call("stats")
                observation["native_context"] = {
                    k: stats[k] for k in ["update_mode", "invert_traffic", "frame"]
                }
                observation["native_context"].update(
                    no_workshop="--noWorkshop" in session.receipt["launch_args"],
                    mods_enabled=session.receipt["control"]
                    and "--disableMods" not in session.receipt["launch_args"],
                )
                if not entry_valid(observation["native_context"]):
                    raise ValueError("unexpected entry protocol")
                observation["runtime_identity"] = identity_with_files(session, build)
                c.call("run", paused=True)
                networks = c.call("networks")
                dump(out / "networks.json", networks)
                study.freeze(
                    out / "query-freeze.json",
                    {
                        "frozen_at": study.now(),
                        "requests": requests,
                        "freeze_sha256": observation["freeze_sha256"],
                        "build_sha256": study.sha(study.HERE / "build.json"),
                        "opening_graph": graph(networks),
                        "pre_query_commit": commit,
                        "networks_sha256": study.sha(out / "networks.json"),
                    },
                )
                observation["query_freeze_sha256"] = study.sha(
                    out / "query-freeze.json"
                )
                c.call("run", paused=False, speed=1)
                for request in requests:
                    session.check_offline()
                    row = {
                        "plan": request,
                        "submitted_at": study.now(),
                        "pre_graph": graph(c.call("networks")),
                        "pre_context": c.call("stats"),
                    }
                    try:
                        started = c.call(
                            "path_start",
                            **{
                                "from": request["request"]["from"],
                                "to": request["request"]["to"],
                                "mode": study.MODES[request["mode"]],
                                "max_length": request["max_length"],
                            },
                        )
                        row["effective"] = started
                        if started["max_length"] != request["max_length"]:
                            raise ValueError("budget unsupported or clamped at entry")
                        deadline = time.monotonic() + 30
                        while True:
                            session.alive()
                            reply = c.call("path_result", id=started["id"])
                            if reply["complete"] or time.monotonic() >= deadline:
                                break
                            time.sleep(0.1)
                        row["result"] = reply
                        row["completed_at"] = study.now()
                        row["post_graph"] = graph(c.call("networks"))
                        row["post_context"] = c.call("stats")
                        if not reply["complete"]:
                            raise RuntimeError(
                                "incomplete path; terminate owned session, retain unknown"
                            )
                    except Exception as error:
                        row["error"] = str(error)
                        observation["paths"].append(row)
                        dump(out / "observation.json", observation)
                        raise
                    observation["paths"].append(row)
                    dump(out / "observation.json", observation)
                c.call("run", paused=True)
                dump(out / "networks-post.json", c.call("networks"))
                observation["post_runtime_identity"] = identity_with_files(
                    session, build
                )
                observation["completed"] = True
            finally:
                for pid in game_pids(cfg.display):
                    p = process_identity(pid)
                    if p:
                        seen[(pid, p["start_ticks"])] = p
                observation["observed_game_processes"] = list(seen.values())
    except Exception as error:
        observation["error"] = f"{type(error).__name__}: {error}"
    finally:
        observation["finished_at"] = study.now()
        if session is not None:
            observation["session"] = session.receipt
        observation["game_cleanup_coverage"] = [
            {**p, "still_running": still_running(p)} for p in seen.values()
        ]
        dump(out / "observation.json", observation)
        for name in ["game.log", "gpu.csv"]:
            if (stage / name).exists():
                shutil.copyfile(stage / name, out / name)
    return observation


def cases(frozen):
    result = [(c, "control") for c in frozen["controls"]] + [
        (c, "holdout") for c in frozen["selected"]
    ]
    by_package = {}
    for row in frozen["intervention"]:
        by_package.setdefault(row["artifact_sha256"], []).append(row)
    for i, (package, rows) in enumerate(sorted(by_package.items()), 1):
        result.append(
            (
                {
                    "case_id": f"budget-{i:02d}",
                    "sha256": package,
                    "locator": rows[0]["locator"],
                    "rows": rows,
                },
                "intervention",
            )
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    study.configure()
    case, kind = next(
        (c, k)
        for c, k in cases(study.read(study.HERE / "freeze.json"))
        if c["case_id"] == args.case_id
    )
    result = collect(case, kind, args.raw)
    print(
        study.encoded(
            {"completed": result["completed"], "error": result.get("error")}
        ).decode()
    )
    raise SystemExit(0 if result["completed"] else 1)
