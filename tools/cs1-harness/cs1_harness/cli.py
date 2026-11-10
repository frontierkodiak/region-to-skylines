"""cs1-harness: run Cities: Skylines 1 headless on a GPU and check a map."""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import time

from . import build as build_mod
from . import report as report_mod
from . import setup as setup_mod
from .client import HarnessError
from .config import FLATPAK_ID, Config
from .run import Run, collect, load_probe_file
from .session import EX_TEMPFAIL, Blocked, Session


def log(msg: str):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def cmd_build(cfg, a):
    print(json.dumps(build_mod.build(cfg), indent=2))


def cmd_setup(cfg, a):
    print(json.dumps(setup_mod.undo(cfg) if a.undo else setup_mod.setup(cfg), indent=2))


def cmd_doctor(cfg, a):
    """Check the GPU path without starting Steam: VirtualGL in the sandbox on the harness display."""
    with Session(cfg, cfg.harness_home / "runs" / "doctor", log=log) as s:
        env, opts = s.flatpak_env()
        vgl = cfg.virtualgl
        script = (
            f"export PATH={vgl}/opt/VirtualGL/bin:$PATH LD_LIBRARY_PATH={vgl}/usr/lib; "
            f"vglrun -d {cfg.egl_device} glxinfo -B 2>/dev/null | grep -E 'renderer|direct rendering'"
        )
        r = subprocess.run(
            ["flatpak", "run", *opts, "--command=sh", FLATPAK_ID, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(r.stdout.strip() or r.stderr.strip()[-2000:])


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
                r = Run(s, out, points, views, log=log)
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
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="compile the harness mod against the installed game")
    s = sub.add_parser("setup", help="user-level host setup (VirtualGL, Steam launch wrapper)")
    s.add_argument("--undo", action="store_true", help="remove everything setup added")
    sub.add_parser("doctor", help="check GPU rendering on the harness display without Steam")
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
    r.add_argument("--max-attempts", type=int, default=0, help="retry limit with --retry-minutes (0: no limit)")
    a = p.parse_args(argv)
    cfg = Config()
    try:
        rc = {"build": cmd_build, "setup": cmd_setup, "doctor": cmd_doctor, "run": cmd_run}[a.cmd](cfg, a)
    except Blocked as b:
        log(f"blocked: {b}")
        rc = b.code
    except HarnessError as e:
        log(f"failed: {e}")
        rc = 1
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
