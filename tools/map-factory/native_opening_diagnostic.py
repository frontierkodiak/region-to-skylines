"""Bounded, foreground opening/Areas diagnostic using the normal harness slot.

Run with the cs1-harness uv project. --interactive permits JSON screen-point
requests on stdin while the game is paused, then {"continue":true}. A timeout,
EOF, account/slot/audio error or exception exits through normal session cleanup.
This does not qualify a map or launch a detached job.
"""

import argparse
import json
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

from cs1_harness import landmarks, startup_views
from cs1_harness.cli import slot, staging
from cs1_harness.config import Config
from cs1_harness.mapcheck import collect
from cs1_harness.session import sha256


def write(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


def capture_views(session, prefix):
    stage = session.stage
    result = {"phase": prefix, "views": {}}
    result["guide_dismissals"] = session.client.call("dismiss_guides", apply=True)
    try:
        for name in ["opening", "area_zoom"]:
            session.alive()
            if name == "area_zoom":
                session.client.call("area_zoom", enabled=True)
            view = startup_views.capture_view(session, name, 20)
            target = stage / f"{prefix}-{name}.png"
            (stage / view["screenshot"]).rename(target)
            view["screenshot"] = target.name
            result["views"][name] = view
    finally:
        session.client.call("area_zoom", enabled=False)
        startup_views.settle(session, False, 20)
        write(stage / f"{prefix}-views.json", result)
    return result


def water_points():
    return [[x, z] for x in [-1280, -1200] for z in [3600, 3616, 3632, 3648, 3664]]


def run(source, output, interactive, minutes, requests_file=None):
    cfg = Config.for_host()
    if cfg.host != "blade" or cfg.display != ":57":
        raise ValueError("This release authorizes only Blade's private :57 session")
    receipt = json.loads((source / "generation.json").read_text())
    hydro = json.loads((source / "hydrology.json").read_text())
    crp = source / (hydro["map_id"] + ".crp")
    assert sha256(crp) == receipt["package"]["sha256"]
    output.mkdir(parents=True, exist_ok=False)
    package = output / f"PL912-{source.name}-{output.name}.crp"
    shutil.copyfile(crp, package)
    stage = staging(cfg, output)
    report = {
        "native_qualification": False,
        "requested_minutes": minutes,
        "tested_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "crp_sha256": sha256(package),
        "source": str(source),
        "source_sha256": {
            name: sha256(source / name)
            for name in [
                "terrain.u16",
                "water.u16",
                "hydrology.json",
                "geometry.json",
                "plan.npz",
            ]
        },
    }
    requests = json.loads(requests_file.read_text()) if requests_file else {}
    screen_requests = requests.get("screen_points", [])
    world_requests = requests.get("world_points", [])
    samples = []
    try:
        with slot(
            cfg,
            stage,
            0,
            {
                "command": "PL-912 bounded opening diagnostic",
                "issue": "PL-912",
                "label": output.name,
            },
        ) as session:
            session.label = "PL-912 " + output.name
            session.live = False
            installed = session.install_map(package)
            session.launch(["--noWorkshop"])
            session.check_audio()
            write(stage / "audio-menu.json", session.receipt["audio_processes"])
            maps = session.client.call("maps")["maps"]
            entry = next(
                m
                for m in maps
                if m["path"]
                and Path(m["path"]).exists()
                and Path(m["path"]).samefile(installed)
            )
            write(stage / "listed-map.json", entry)
            session.client.call("new_game", path=entry["path"])
            session.client.wait(
                lambda s: s.get("in_game") and not s.get("loading"),
                300,
                "city load",
                alive=session.alive,
            )
            session.client.call("run", paused=True, day_night=False)
            landmarks.capture(session, stage, None)
            report["zero_views"] = capture_views(session, "t000")
            session.client.call(
                "dump", dir=str(stage / "grids"), prefix="t000", terrain=True
            )
            for name in ["terrain", "water"]:
                actual = sha256(stage / f"grids/t000-{name}.u16")
                report[f"initial_{name}_sha256"] = actual
                assert actual == report["source_sha256"][name + ".u16"], (
                    f"initial {name} differs from candidate"
                )
            write(
                stage / "t000-sections.json",
                session.client.call("water", points=water_points()),
            )
            write(stage / "audio-t000.json", session.receipt["audio_processes"])
            write(stage / "measurement-requests.json", requests)
            if screen_requests:
                observed = session.client.call(
                    "world_observe", screen_points=screen_requests
                )
                samples.append(observed)
                write(stage / "t000-screen-hits.json", samples)
            if world_requests:
                write(
                    stage / "t000-world-water.json",
                    session.client.call("water", points=world_requests),
                )
            write(stage / "diagnostic.json", report)
            print(
                json.dumps(
                    {
                        "ready": str(stage),
                        "output": str(output),
                        "interactive": interactive,
                    }
                ),
                flush=True,
            )
            if interactive:
                deadline = time.monotonic() + 300
                while True:
                    session.alive()
                    if time.monotonic() >= deadline:
                        raise TimeoutError("screen-point command deadline expired")
                    if not select.select([sys.stdin], [], [], 1)[0]:
                        continue
                    line = sys.stdin.readline()
                    if not line:
                        raise EOFError("diagnostic stdin closed")
                    command = json.loads(line)
                    if command.get("continue"):
                        break
                    request = command["screen_points"]
                    observed = session.client.call(
                        "world_observe", screen_points=request
                    )
                    for point in observed["screen_points"]:
                        if point["hit"]:
                            p = point["projected_screen_bottom_left"]
                            screen = point["screen_top_left"]
                            error = [
                                abs(p[0] - screen[0]),
                                abs(
                                    p[1]
                                    - (observed["camera"]["screen_height"] - screen[1])
                                ),
                            ]
                            # A screenshot samples whole pixels. Keep raw hits and
                            # reject only the individual binding outside half a pixel.
                            point["pixel_roundtrip_error"] = error
                            point["binding_within_half_pixel"] = max(error) <= 0.5
                    screen_requests.extend(request)
                    samples.append(observed)
                    write(stage / "t000-screen-hits.json", samples)
                    print(
                        json.dumps(
                            {
                                "samples": str(stage / "t000-screen-hits.json"),
                                "requests": len(screen_requests),
                            }
                        ),
                        flush=True,
                    )
            # Fixed delta belongs to CoreOps.status, not CityOps.stats.
            start = session.client.call("status")
            start_frame = start["frame"]
            frames = 60 / start["fixed_delta_time"]
            session.client.call("run", paused=False, speed=3, day_night=False)
            last_log = 0
            deadline = time.monotonic() + 1200
            while True:
                session.alive()
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "five-minute diagnostic exceeded foreground wall bound"
                    )
                stats = session.client.call("stats")
                elapsed = (stats["frame"] - start_frame) / frames
                if elapsed >= minutes:
                    break
                if elapsed - last_log >= 1:
                    print(f"game minutes {elapsed:.2f}/{minutes}", flush=True)
                    last_log = elapsed
                time.sleep(2)
            session.client.call("run", paused=True)
            session.client.call(
                "dump", dir=str(stage / "grids"), prefix="t005", terrain=True
            )
            report["elapsed_game_minutes"] = elapsed
            report["five_views"] = capture_views(session, "t005")
            write(
                stage / "t005-sections.json",
                session.client.call("water", points=water_points()),
            )
            write(
                stage / "t005-screen-hits.json",
                session.client.call("world_observe", screen_points=screen_requests),
            )
            if world_requests:
                write(
                    stage / "t005-world-water.json",
                    session.client.call("water", points=world_requests),
                )
            session.check_audio()
            write(stage / "audio-t005.json", session.receipt["audio_processes"])
            report["final_grid_sha256"] = {
                name: sha256(stage / f"grids/t005-{name}.u16")
                for name in ["terrain", "water"]
            }
            write(stage / "diagnostic.json", report)
    finally:
        if stage.exists():
            collect(stage, output)
    cleanup = json.loads((output / "session-receipt.json").read_text())["cleanup"]
    assert cleanup == {"game": [], "steam_instances": [], "units_active": []}, cleanup
    print(json.dumps({"complete": str(output), "cleanup": cleanup}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--minutes", type=float, default=5)
    parser.add_argument(
        "--requests",
        type=Path,
        help="Fixed screen_points and world_points for matched arms",
    )
    args = parser.parse_args()
    if not 0 < args.minutes <= 5:
        parser.error("this release is bounded to at most five game minutes")
    run(
        args.source.resolve(),
        args.output.resolve(),
        args.interactive,
        args.minutes,
        args.requests,
    )
