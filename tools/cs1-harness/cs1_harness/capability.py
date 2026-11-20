"""Foreground exact-witness oracle; never selects or repairs a starting plan.

Run as ``uv run python -m cs1_harness.capability --help``. Predictions and map
bytes must be frozen before invocation. All failures and partial steps survive.
This is a distinct DLL/oracle series, not a first-hour player requalification.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import signal
import time

from . import landmarks, new_game_panel, startup_views, verdict
from .cli import log, slot, staging
from .client import HarnessError
from .config import Config
from .mapcheck import collect
from .session import Blocked


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def prediction(path, package, model_hash):
    row = json.loads(path.read_text())
    model = row["model"]
    if model["sha256"] != model_hash or digest({k: v for k, v in model.items() if k != "sha256"}) != model_hash:
        raise ValueError("Model binding mismatch")
    if row.get("artifact_sha256") != sha(package):
        raise ValueError("Prediction does not bind the exact map bytes")
    for capability in ("start", "water"):
        value = row["capabilities"][capability]
        if value.get("witness") is not None and digest(value["witness"]) != value.get("witness_sha256"):
            raise ValueError(f"Witness binding mismatch: {capability}")
    return row


def poll_job(session, job_id, out):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        session.alive()
        row = session.client.call("job")
        (out / "witness-job.json").write_text(json.dumps(row, indent=2) + "\n")
        if row.get("job") != job_id or row.get("kind") != "capability_witness":
            raise HarnessError("Job identity mismatch")
        if row["state"] == "failed":
            raise HarnessError(f"Witness job failed: {row.get('error')}")
        if row["state"] == "done":
            return row["result"]
        time.sleep(0.25)
    raise HarnessError("Witness job timed out")


def paths(session, out):
    c = session.client
    # Fixed settling interval: network lanes update on simulation frames.
    # No growing city, search, retry, reroute or strategy adaptation.
    frame = c.call("stats")["frame"]
    c.call("run", paused=False, speed=3)
    deadline = time.monotonic() + 60
    try:
        while c.call("stats")["frame"] - frame < 256:
            session.alive()
            if time.monotonic() >= deadline:
                raise HarnessError("Fixed network settling interval timed out")
            time.sleep(0.25)
    finally:
        c.call("run", paused=True)
    row = c.call("scenario_paths", start=True)
    deadline = time.monotonic() + 60
    while not row["complete"]:
        session.alive()
        if time.monotonic() >= deadline:
            raise HarnessError("Native paths timed out")
        time.sleep(0.25)
        row = c.call("scenario_paths")
    (out / "native-paths.json").write_text(json.dumps(row, indent=2) + "\n")
    return row


def run(cfg, args):
    row = prediction(args.prediction, args.map, args.model_sha256)
    if sha(cfg.build_dir / "Cs1Harness.dll") != args.dll_sha256:
        raise ValueError("Compiled oracle DLL mismatch")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    # Freeze the validated request, not a second read of a mutable source file.
    (out / "prediction.json").write_text(json.dumps(row, indent=2) + "\n")
    shutil.copyfile(args.probes, out / "probes.json")
    stage = staging(cfg, out)
    result = {
        "schema": 1,
        "oracle": "exact_start_witness_v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "model_sha256": args.model_sha256,
        "prediction_sha256": sha(out / "prediction.json"),
        "artifact_sha256": row["artifact_sha256"],
        "oracle_dll_sha256": args.dll_sha256,
        "oracle_source": verdict.harness_commit(),
        "observed_start": None,
        "observed_native_placement": None,
        "observed_surface_service": None,
    }
    started = time.monotonic()
    try:
        meta = {
            "command": "capability-witness",
            "issue": args.issue,
            "label": f"{args.issue} exact witness {args.map.stem}",
            "out": str(out),
        }
        with slot(cfg, stage, args.wait_minutes, meta) as session:
            session.require_offline = True
            session.record, session.live = False, False
            session.label = meta["label"]
            if sha(cfg.build_dir / "Cs1Harness.dll") != args.dll_sha256:
                raise HarnessError("Oracle DLL changed while queued")
            installed = session.install_map(args.map.resolve())
            if (session.receipt.get("map") or {}).get("sha256") != row["artifact_sha256"] or sha(installed) != row[
                "artifact_sha256"
            ]:
                raise HarnessError("Installed map changed from the frozen prediction while queued")
            session.launch(["--noWorkshop"])
            if session.receipt.get("mod_sha256") != args.dll_sha256:
                raise HarnessError("Installed oracle DLL mismatch")
            c = session.client
            entries = [
                e
                for e in c.call("maps")["maps"]
                if e["path"] and Path(e["path"]).exists() and Path(e["path"]).samefile(installed)
            ]
            if len(entries) != 1:
                raise HarnessError("Map listing must uniquely match installed bytes")
            new_game_panel.capture(session, out, entries[0]["path"], new_game_panel.request(out))
            c.call("new_game", path=entries[0]["path"])
            c.wait(lambda st: st.get("in_game") and not st.get("loading"), 900, "new city", alive=session.alive)
            c.call("run", paused=True)
            landmarks.capture(session, out, landmarks.request(out))
            startup_views.capture(session, out, startup_views.request(out))
            water = row["capabilities"]["water"].get("witness")
            if water:
                measured = c.call(
                    "capability_water", points=[water[k] for k in ("intake_water_point", "outlet_water_point")]
                )
                (out / "native-water-points.json").write_text(json.dumps(measured, indent=2) + "\n")
            start = row["capabilities"]["start"]
            if start.get("witness"):
                job = c.call("capability_witness", witness=start["witness"], witness_sha256=start["witness_sha256"])
                observed = poll_job(session, job["job"], out)
                if (
                    observed.get("witness_sha256") != start["witness_sha256"]
                    or observed.get("mode") != "exact_recorded_plan_no_search"
                ):
                    raise HarnessError("Native witness binding/mode mismatch")
                result["observed_native_placement"] = observed.get("observed_native_placement")
                if result["observed_native_placement"] is True:
                    reach = paths(session, out)
                    result["observed_start"] = bool(reach["inbound"] and reach["outbound"])
                elif result["observed_native_placement"] is False:
                    result["observed_start"] = False
            # No witness is not a failed native placement or a geographic no.
            network = c.call("networks")
            (out / "networks.json").write_text(json.dumps(network, indent=2) + "\n")
    except (Blocked, HarnessError, OSError, ValueError) as error:
        result["error"] = str(error)
        # Errors outside the native structured tool rejection are unscored.
        result["observed_start"] = None
        result["observed_native_placement"] = None
        result["exit_code"] = error.code if isinstance(error, Blocked) else 1
    finally:
        if stage.exists():
            collect(stage, out)
        result["wall_seconds_including_queue"] = time.monotonic() - started
        receipt = (
            json.loads((out / "session-receipt.json").read_text()) if (out / "session-receipt.json").exists() else {}
        )
        result["cleanup"] = receipt.get("cleanup")
        if result["cleanup"] != {"game": [], "steam_instances": [], "units_active": []}:
            result["observed_start"] = None
            result["observed_native_placement"] = None
            result["cleanup_qualified"] = False
        else:
            result["cleanup_qualified"] = True
        (out / "observation.json").write_text(json.dumps(result, indent=2) + "\n")
    log(json.dumps(result))
    return result.get("exit_code", 0 if result.get("cleanup_qualified") else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("map", "prediction", "probes", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--dll-sha256", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--wait-minutes", type=float, default=45)
    args = parser.parse_args()
    if not 0 <= args.wait_minutes <= 45:
        parser.error("--wait-minutes must be finite and in [0,45]")

    def terminate(signum, _frame):
        raise SystemExit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, terminate)
    raise SystemExit(run(Config.for_host(), args))


if __name__ == "__main__":
    main()
