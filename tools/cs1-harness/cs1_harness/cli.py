"""cs1-harness: run Cities: Skylines 1 headless on a GPU, control it, and check maps.

Two layers. `up` / `call` / `down` hold a game session that any tool can drive
through the mod's ops (`call ops` lists them). `run` is one tool built on it: a
timed map check with a report.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import pathlib
import shutil
import sys
import time

from . import build as build_mod
from . import report as report_mod
from . import setup as setup_mod
from .client import Client, HarnessError
from .config import Config
from .mapcheck import MapCheck, collect, load_probe_file
from .session import EX_TEMPFAIL, Blocked, Session


def log(msg: str):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def cmd_build(cfg, a):
    print(json.dumps(build_mod.build(cfg), indent=2))


def cmd_setup(cfg, a):
    print(json.dumps(setup_mod.undo(cfg) if a.undo else setup_mod.setup(cfg), indent=2))


def cmd_doctor(cfg, a):
    """Check the GPU path without starting Steam: VirtualGL on the harness display, pinned by PCI bus."""
    with Session(cfg, cfg.harness_home / "runs" / "doctor", log=log) as s:
        print(json.dumps({"host": cfg.host, "steam": cfg.steam, **s.pin_gpu()}, indent=2))
    shutil.rmtree(cfg.harness_home / "runs" / "doctor", ignore_errors=True)
    with contextlib.suppress(OSError):
        (cfg.harness_home / "runs").rmdir()


def cmd_up(cfg, a):
    """Start a session and leave it running: display, bus, Steam, game at the main menu."""
    stage = cfg.harness_home / "runs" / (a.name or time.strftime("session-%Y%m%d-%H%M%S"))
    with Session(cfg, stage, log=log) as s:
        if a.map:
            s.install_map(a.map.resolve())
        if a.display_only:
            s.pin_gpu()
            status = None
        else:
            status = s.launch(["--noWorkshop", *a.game_arg])
        s.detach()
    print(
        json.dumps(
            {
                "host": cfg.host,
                "stage": str(stage),
                "display": cfg.display,
                "port": cfg.port,
                "gpu": s.receipt.get("gpu"),
                "status": status,
            },
            indent=2,
        )
    )


def cmd_see(cfg, a):
    """Score screenshots with Clef-Flash (advisory)."""
    from . import vision

    for path in a.images:
        print(json.dumps({"image": str(path), **vision.summarize(vision.ask(path))}))


def cmd_call(cfg, a):
    args = json.loads(a.json) if a.json else {}
    print(json.dumps(Client(cfg.port).call(a.op, **args), indent=2))


def cmd_down(cfg, a):
    if not cfg.state_file.exists():
        log("no harness session is up")
        return 0
    s = Session.attach(cfg, log=log)
    s.stop()
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        collect(s.stage, a.out.resolve())
    print(json.dumps(s.receipt.get("cleanup"), indent=2))
    return 0 if s.receipt.get("cleanup") == {"game": [], "steam_instances": [], "units_active": []} else 1


def cmd_run(cfg, a):
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    points, views = load_probe_file(a.probes)
    if not a.map.exists():
        raise SystemExit(f"no such map: {a.map}")
    stage = cfg.harness_home / "runs" / out.name
    attempt = 0
    while True:
        attempt += 1
        try:
            with Session(cfg, stage, log=log) as s:
                r = MapCheck(s, out, points, views, log=log)
                result = r.execute(
                    a.map.resolve(),
                    a.game_minutes,
                    a.speed,
                    a.sample_every,
                    a.screenshot_every,
                    a.dump_every,
                    a.load_timeout,
                )
                result["probes"] = str(a.probes) if a.probes else None
                result["clef"] = a.clef
                result["gpu_processes"] = s.gpu_processes()
            collect(stage, out)
            report = report_mod.build(
                out, {**result, "session": json.loads((out / "session-receipt.json").read_text())}
            )
            print((out / "report.md").read_text())
            if report["session"]["cleanup"] != {"game": [], "steam_instances": [], "units_active": []}:
                log(f"cleanup left something running: {report['session']['cleanup']}")
                return 1
            return 0
        except Blocked as b:
            if stage.exists():
                collect(stage, out)
            log(f"blocked: {b}")
            if b.code == EX_TEMPFAIL and a.retry_minutes and (a.max_attempts == 0 or attempt < a.max_attempts):
                log(f"retrying in {a.retry_minutes} minutes (attempt {attempt + 1})")
                time.sleep(a.retry_minutes * 60)
                continue
            return b.code
        except HarnessError as e:
            if stage.exists():
                collect(stage, out)
            log(f"failed: {e}")
            return 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="cs1-harness", description=__doc__)
    p.add_argument("--host", help="host profile (blade, worm); default: this machine's hostname")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="compile the harness mod against the installed game")
    s = sub.add_parser("setup", help="user-level host setup (VirtualGL, Steam launch wrapper)")
    s.add_argument("--undo", action="store_true", help="remove everything setup added")
    sub.add_parser("doctor", help="check GPU rendering on the harness display without Steam")
    u = sub.add_parser("up", help="start a session and leave it running (ends with `down`)")
    u.add_argument("--map", type=pathlib.Path, help="install this .crp into Maps/ for the session")
    u.add_argument("--name", help="staging directory name")
    u.add_argument("--display-only", action="store_true", help="display and bus only; no Steam or game")
    u.add_argument("--game-arg", action="append", default=[], help="extra game argument (repeatable)")
    c = sub.add_parser("call", help="send one op to the running game (`call ops` lists them)")
    c.add_argument("op")
    c.add_argument("json", nargs="?", help="op arguments as a JSON object")
    v = sub.add_parser("see", help="score screenshots with Clef-Flash (advisory)")
    v.add_argument("images", nargs="+", type=pathlib.Path)
    d = sub.add_parser("down", help="quit the game and stop everything `up` started")
    d.add_argument("--out", type=pathlib.Path, help="move the session's files (log, GPU samples, shots) here")
    r = sub.add_parser("run", help="New Game on a map, simulate, report")
    r.add_argument("--map", type=pathlib.Path, required=True, help="the .crp map file")
    r.add_argument(
        "--game-minutes", type=float, default=60, help="simulated minutes, counted as play at 1x speed (default 60)"
    )
    r.add_argument("--out", type=pathlib.Path, required=True, help="output directory")
    r.add_argument("--probes", type=pathlib.Path, help="JSON with water probe points and camera views")
    r.add_argument("--speed", type=int, default=3, choices=(1, 2, 3), help="game speed button (3 is 4x)")
    r.add_argument("--sample-every", type=float, default=5, help="game-minutes between water/stat samples")
    r.add_argument("--screenshot-every", type=float, default=15, help="game-minutes between screenshot sets")
    r.add_argument("--dump-every", type=float, default=15, help="game-minutes between full water-grid dumps")
    r.add_argument("--load-timeout", type=float, default=900, help="seconds to wait for the city to load")
    r.add_argument(
        "--retry-minutes",
        type=float,
        default=0,
        help="if Steam says the account is in use, wait this long and retry (0: exit 75)",
    )
    r.add_argument(
        "--clef",
        action="store_true",
        help="also score every screenshot with blade's Clef-Flash (advisory: frame kind, garbling)",
    )
    r.add_argument("--max-attempts", type=int, default=0, help="retry limit with --retry-minutes (0: no limit)")
    a = p.parse_args(argv)
    cfg = Config.for_host(a.host)
    try:
        rc = {
            "build": cmd_build,
            "setup": cmd_setup,
            "doctor": cmd_doctor,
            "up": cmd_up,
            "call": cmd_call,
            "down": cmd_down,
            "see": cmd_see,
            "run": cmd_run,
        }[a.cmd](cfg, a)
    except Blocked as b:
        log(f"blocked: {b}")
        rc = b.code
    except HarnessError as e:
        log(f"failed: {e}")
        rc = 1
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
