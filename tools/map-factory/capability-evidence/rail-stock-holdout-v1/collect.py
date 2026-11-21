"""Foreground one-opening collector; fresh fair-slot and identity each time."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import time

import study
from cs1_harness import rail_study
from cs1_harness.cli import slot, staging
from cs1_harness.config import Config
from cs1_harness.runtime_identity import bind_runtime


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
    # Bind through each process namespace where plugin paths are namespace-local.
    identity["file_inventory"] = {
        str(p): {"bytes": p.stat().st_size, "sha256": study.sha(p)}
        for p in sorted(files)
    }
    identity["inventory_roots"] = {str(p): p.is_dir() for p in roots}
    return identity


def controls_valid(frozen, raw):
    results = []
    for case in frozen["controls"]:
        path = raw / case["slug"] / "observation.json"
        if not path.exists():
            return False
        obs = study.read(path)
        qpath = path.parent / "query-freeze.json"
        if not qpath.exists():
            return False
        q = study.read(qpath)
        if (
            obs.get("freeze_sha256") != study.sha(study.HERE / "freeze.json")
            or obs.get("protocol") != study.PROTOCOL
            or obs.get("query_freeze_sha256") != study.sha(qpath)
            or q["requests"] != case["requests"]
            or q["build_sha256"] != study.sha(study.HERE / "metadata-build.json")
        ):
            raise ValueError("control freeze/protocol/build differs")
        if (
            obs.get("artifact_sha256") != case["sha256"]
            or not obs.get("completed")
            or not rail_study.context_valid(obs)
        ):
            return False
        rows = obs["paths"]
        if any(
            not r.get("submitted_at")
            or r["submitted_at"] < q["frozen_at"]
            or r["submitted_at"] < frozen["frozen_at"]
            for r in rows
        ):
            raise ValueError("control query predates freeze")
        if [r["request"] for r in rows] != case["requests"]:
            raise ValueError("control requests changed")
        invalid = [
            r for r in rows if r["request"]["name"] == "invalid-train-to-car-lane"
        ]
        if len(invalid) != 1 or study.label(invalid[0]) != "no_path":
            return False
        results.append(
            any(
                not r["request"]["diagnostic"] and study.label(r) == "success"
                for r in rows
            )
        )
    return any(results)


def collect(case, requests, frozen, raw):
    cfg = Config.for_host()
    package = Path(case.get("preserved_locator", case["locator"]))
    out = raw / case["slug"]
    out.mkdir(parents=True, exist_ok=False)
    stage = staging(cfg, out)
    observation = {
        "schema": 1,
        "observed_at": study.now(),
        "package": case["locator"],
        "artifact_sha256": study.sha(package),
        "freeze_sha256": study.sha(study.HERE / "freeze.json"),
        "protocol": study.PROTOCOL,
        "paths": [],
        "completed": False,
    }
    session = None
    if observation["artifact_sha256"] != case["sha256"]:
        raise ValueError("selected CRP bytes changed")
    try:
        with slot(
            cfg,
            stage,
            0,
            {"command": "connections", "issue": "PL-1239", "label": case["slug"]},
        ) as session:
            observation["build_receipt"] = study.read(
                cfg.build_dir / "build-receipt.json"
            )
            if (
                observation["build_receipt"]
                != study.read(study.HERE / "metadata-build.json")["build_receipt"]
            ):
                raise ValueError("metadata build no longer matches freeze")
            session.require_offline = True
            session.record = False
            session.live = False
            installed = session.install_map(package)
            if session.receipt["map"]["sha256"] != case["sha256"]:
                raise ValueError("installed package bytes changed")
            session.launch(["--noWorkshop"])
            c = session.client
            observation["launch_runtime_identity"] = identity_with_files(
                session, observation["build_receipt"]
            )
            entry = next(
                m
                for m in c.call("maps")["maps"]
                if m.get("path") and Path(m["path"]).samefile(installed)
            )
            observation["listed"] = entry
            observation["new_game_protocol"] = c.call("new_game", path=entry["path"])
            observation["loaded"] = c.wait(
                lambda st: st.get("in_game") and not st.get("loading"),
                600,
                "New Game",
                alive=session.alive,
            )
            stats = c.call("stats")
            observation["native_context"] = {
                "observed_at": study.now(),
                "update_mode": stats["update_mode"],
                "invert_traffic": stats["invert_traffic"],
                "frame": stats["frame"],
                "no_workshop": "--noWorkshop" in session.receipt["launch_args"],
                "mods_enabled": session.receipt["control"]
                and "--disableMods" not in session.receipt["launch_args"],
            }
            observation["runtime_identity"] = identity_with_files(
                session, observation["build_receipt"]
            )
            if not rail_study.context_valid(observation):
                raise ValueError(
                    "new opening lacks launch-bound runtime/context identity"
                )
            c.call("run", paused=True)
            networks = c.call("networks")
            metadata = c.call("rail_metadata")
            dump(out / "networks.json", networks)
            dump(out / "metadata.json", metadata)
            observation["query_freeze_sha256"] = study.freeze(
                out / "query-freeze.json",
                {
                    "frozen_at": study.now(),
                    "freeze_sha256": observation["freeze_sha256"],
                    "build_sha256": study.sha(study.HERE / "metadata-build.json"),
                    "networks_sha256": study.sha(out / "networks.json"),
                    "metadata_sha256": study.sha(out / "metadata.json"),
                    "runtime_identity": observation["runtime_identity"],
                    "requests": requests,
                },
            )
            c.call("run", paused=False, speed=1)
            for request in requests:
                session.check_offline()
                row = {
                    "request": request,
                    "mode": "train",
                    "submitted_at": study.now(),
                    "pre_graph": c.call("rail_metadata", digest_only=True),
                }
                try:
                    started = c.call(
                        "path_start",
                        **{
                            "from": request["from"],
                            "to": request["to"],
                            "mode": "train",
                        },
                    )
                    row["native_request_id"] = started["id"]
                    deadline = time.monotonic() + 30
                    while True:
                        session.alive()
                        reply = c.call("path_result", id=started["id"])
                        if reply["complete"] or time.monotonic() >= deadline:
                            break
                        time.sleep(0.1)
                    row["result"] = reply
                    row["completed_at"] = study.now()
                    row["post_graph"] = c.call("rail_metadata", digest_only=True)
                    if not reply["complete"]:
                        raise RuntimeError(
                            "path incomplete; abort session and retain request Unknown"
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
            dump(out / "metadata-post.json", c.call("rail_metadata"))
            observation["post_runtime_identity"] = identity_with_files(
                session, observation["build_receipt"]
            )
            observation["completed"] = True
    except Exception as error:
        observation["error"] = f"{type(error).__name__}: {error}"
    finally:
        observation["finished_at"] = study.now()
        if session is not None:
            observation["session"] = session.receipt
        dump(out / "observation.json", observation)
        for name in ["game.log", "gpu.csv"]:
            if (stage / name).exists():
                shutil.copyfile(stage / name, out / name)
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    frozen = study.read(study.HERE / "freeze.json")
    study.validate_artifacts(frozen)
    cases = {c["slug"]: c for c in frozen["controls"] + frozen["selected"]}
    case = cases[args.slug]
    if args.slug.startswith("holdout") and not controls_valid(frozen, args.raw):
        raise ValueError("controls have not passed; holdout requests forbidden")
    result = collect(
        case, case.get("requests", case.get("selected_requests", [])), frozen, args.raw
    )
    print(
        json.dumps(
            {
                "slug": args.slug,
                "completed": result["completed"],
                "error": result.get("error"),
            }
        )
    )


if __name__ == "__main__":
    main()
