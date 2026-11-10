"""cs1-harness: run Cities: Skylines 1 headless on a GPU, control it, and check maps and assets.

Two layers. `up` / `call` / `down` hold a game session that any tool can drive
through the mod's ops (`call ops` lists them). `run` (a timed map check) and
`asset build` / `asset check` (Asset Editor mode) are tools built on it.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import pathlib
import shutil
import subprocess
import sys
import time

from . import build as build_mod
from . import report as report_mod
from . import setup as setup_mod
from .client import Client, HarnessError
from .config import Config
from .assets import Driver as AssetDriver
from .mapcheck import MapCheck, collect, load_probe_file
from .session import EX_TEMPFAIL, Blocked, Session


def log(msg: str):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


SLOT_POLL_SECONDS = 2


@contextlib.contextmanager
def slot(cfg, stage, wait_minutes: float):
    """A Session, waiting up to `wait_minutes` while another user holds the host's harness slot.

    It polls every few seconds rather than queueing, so it takes the slot in the
    gap between another agent's commands. It never ends or takes over the
    other session.
    """
    deadline = time.monotonic() + wait_minutes * 60
    last = None
    while True:
        with contextlib.ExitStack() as stack:
            try:
                s = stack.enter_context(Session(cfg, stage, log=log))
            except Blocked as b:
                if not b.busy or time.monotonic() >= deadline:
                    raise
                if str(b) != last:
                    log(f"waiting for the harness slot: {b}")
                    last = str(b)
                time.sleep(SLOT_POLL_SECONDS)
                continue
            if last:
                log("harness slot acquired")
            yield s
            return


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
    with slot(cfg, stage, a.wait_minutes) as s:
        observers(s, a)
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


def observers(s, a, default_label=None):
    s.label = a.label or default_label
    s.record = not a.no_record
    s.live = not a.no_live


def cmd_watch(cfg, a):
    """View-only VNC of the running session's display, on localhost only."""
    from . import observe

    if a.stop:
        subprocess.run(["systemctl", "--user", "stop", cfg.vnc_unit], check=False)
        print("watch stopped")
        return 0
    # Any harness session (up or run) owns the display; watching needs only that.
    if not (pathlib.Path("/tmp/.X11-unix") / f"X{cfg.display.lstrip(':')}").exists():
        log(f"no harness display {cfg.display} is up; start a session with `cs1-harness up` or `run`")
        return 1
    s = Session(cfg, cfg.harness_home / "runs" / "watch", log=log)
    subprocess.run(["systemctl", "--user", "stop", cfg.vnc_unit], check=False, capture_output=True)
    subprocess.run(["systemctl", "--user", "reset-failed", cfg.vnc_unit], check=False, capture_output=True)
    info = observe.watch_start(s)
    print(
        f"view-only VNC of {cfg.display} on {cfg.host}, localhost:{info['port']} (password {info['password']})\n"
        f"from carbon: ssh -N -L {info['port']}:localhost:{info['port']} {cfg.host} & open vnc://localhost:{info['port']}"
        + (f"\nlive page: {cfg.live_url}" if cfg.live_url else ""),
        flush=True,
    )
    if a.hold:
        try:
            time.sleep(a.hold * 60)
        except KeyboardInterrupt:
            pass
        subprocess.run(["systemctl", "--user", "stop", cfg.vnc_unit], check=False)
        print("watch stopped")
    return 0


def cmd_bench_observe(cfg, a):
    """A/B/A: does the timelapse, live page and a VNC viewer slow the game?"""
    from . import bench

    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stage = cfg.harness_home / "runs" / out.name
    with slot(cfg, stage, a.wait_minutes) as s:
        s.record, s.live, s.label = False, False, "observer bench"
        installed = s.install_map(a.map.resolve())
        s.launch(["--noWorkshop"])
        entry = next(
            m
            for m in s.client.call("maps")["maps"]
            if m["path"] and pathlib.Path(m["path"]).exists() and pathlib.Path(m["path"]).samefile(installed)
        )
        s.client.call("new_game", path=entry["path"])
        s.client.wait(lambda st: st.get("in_game") and not st.get("loading"), 900, "the city to load", alive=s.alive)
        s.client.call("run", paused=False, speed=3)
        time.sleep(20)
        result = bench.run(s, a.seconds)
    collect(stage, out)
    (out / "bench.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


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
            with slot(cfg, stage, a.wait_minutes) as s:
                observers(s, a, default_label=f"map check: {a.map.name}")
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


def _session_tool(cfg, a, label: str, body) -> int:
    """Run body(driver) in a fresh session, collect its files into --out, write a receipt."""
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stage = cfg.harness_home / "runs" / out.name
    attempt = 0
    while True:
        attempt += 1
        result, rc = None, 0
        try:
            with Session(cfg, stage, log=log) as s:
                result = body(AssetDriver(s, out, log=log))
                result["gpu_processes"] = s.gpu_processes()
        except Blocked as b:
            log(f"blocked: {b}")
            if stage.exists():
                collect(stage, out)
            if b.code == EX_TEMPFAIL and a.retry_minutes and (a.max_attempts == 0 or attempt < a.max_attempts):
                log(f"retrying in {a.retry_minutes} minutes (attempt {attempt + 1})")
                time.sleep(a.retry_minutes * 60)
                continue
            return b.code
        except HarnessError as e:
            log(f"failed: {e}")
            result, rc = {"error": str(e)}, 1
        if stage.exists():
            collect(stage, out)
        receipt = {"tool": label, "result": result}
        session = out / "session-receipt.json"
        if session.exists():
            receipt["session"] = json.loads(session.read_text())
            if receipt["session"].get("cleanup") != {"game": [], "steam_instances": [], "units_active": []}:
                log(f"cleanup left something running: {receipt['session'].get('cleanup')}")
                rc = rc or 1
        (out / f"{label}.json").write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        print(json.dumps({"out": str(out), "ok": rc == 0, **({"error": result["error"]} if rc else {})}))
        return rc


def cmd_asset(cfg, a):
    if a.action == "build":
        bake = (
            json.loads((a.src / f"{a.name}.bake.json").read_text()) if (a.src / f"{a.name}.bake.json").exists() else {}
        )
        cells = (
            tuple(int(v) for v in a.cells.lower().split("x")) if a.cells else tuple(bake.get("lot_cells", ())) or None
        )
        expect = None
        if bake.get("size_m") and not a.no_size_check:
            sx, sy, sz = bake["size_m"]  # Blender x across, y deep, z up -> game x, y up, z deep
            expect = [sx, sz, sy]
        return _session_tool(
            cfg,
            a,
            "asset-build",
            lambda d: d.build(
                a.src.resolve(),
                a.name,
                a.template,
                cells,
                a.scale,
                expect,
                a.asset_name or a.name,
                a.save_name or a.name,
                a.theme,
                a.load_timeout,
            ),
        )
    at = tuple(float(v) for v in a.at.split(",")) if a.at else None
    return _session_tool(
        cfg, a, "asset-check", lambda d: d.check(a.crp.resolve(), a.map.resolve(), at, a.angle, a.load_timeout)
    )


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
    u.add_argument("--label", help="what the live page calls this run (e.g. 'PL-857 Asheville soak')")
    u.add_argument("--no-record", action="store_true", help="skip the timelapse recording")
    u.add_argument("--no-live", action="store_true", help="skip the live frame page")
    u.add_argument("--game-arg", action="append", default=[], help="extra game argument (repeatable)")
    u.add_argument(
        "--wait-minutes",
        type=float,
        default=0,
        help="if another agent or person holds this host's harness, wait up to this long for it (0: exit 75)",
    )
    b = sub.add_parser("bench-observe", help="measure what watching costs the game (A/B/A)")
    b.add_argument("--map", type=pathlib.Path, required=True)
    b.add_argument("--out", type=pathlib.Path, required=True)
    b.add_argument("--seconds", type=float, default=60)
    b.add_argument("--wait-minutes", type=float, default=0)
    w = sub.add_parser("watch", help="view-only VNC of the running session (localhost; reach it over ssh)")
    w.add_argument("--hold", type=float, default=0, help="keep it this many minutes, then stop (0: until down)")
    w.add_argument("--stop", action="store_true", help="stop the VNC server")
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
    r.add_argument("--label", help="what the live page calls this run (e.g. 'PL-857 Asheville soak')")
    r.add_argument("--no-record", action="store_true", help="skip the timelapse recording")
    r.add_argument("--no-live", action="store_true", help="skip the live frame page")
    r.add_argument("--max-attempts", type=int, default=0, help="retry limit with --retry-minutes (0: no limit)")
    r.add_argument(
        "--wait-minutes",
        type=float,
        default=0,
        help="if another agent or person holds this host's harness, wait up to this long for it (0: exit 75)",
    )
    ab = sub.add_parser("asset", help="Asset Editor mode: build a .crp from an import set, or check one in game")
    asub = ab.add_subparsers(dest="action", required=True)
    b = asub.add_parser("build", help="import <name>.fbx (+ _lod and maps) onto a template and save a .crp")
    b.add_argument("--src", type=pathlib.Path, required=True, help="directory with <name>.fbx, <name>_lod.fbx, maps")
    b.add_argument("--name", required=True, help="mesh base name (the FBX's file name without extension)")
    b.add_argument(
        "--template",
        required=True,
        help="building template prefab name (`call templates` lists them), or auto: low-density residential level 1 on the lot",
    )
    b.add_argument("--cells", help="lot in 8 m cells, WxL (default: the bake receipt's)")
    b.add_argument("--scale", type=float, default=1.0, help="import scale (default 1: the FBX is in metres)")
    b.add_argument("--no-size-check", action="store_true", help="skip comparing the imported size with the bake's")
    b.add_argument("--asset-name", help="asset name in game menus (default: --name)")
    b.add_argument("--save-name", help=".crp file name without extension (default: --name)")
    b.add_argument("--theme", default="Sunny", help="Asset Editor environment")
    b.add_argument("--out", type=pathlib.Path, required=True)
    k = asub.add_parser("check", help="fresh game: New Game on a map, place the asset, views, save and reload")
    k.add_argument("--crp", type=pathlib.Path, required=True, help="the asset .crp")
    k.add_argument("--map", type=pathlib.Path, required=True, help="map .crp for the New Game")
    k.add_argument("--at", help="x,z world metres to place it (default: a dry, flat spot near the centre)")
    k.add_argument("--angle", type=float, default=0, help="building angle, degrees")
    k.add_argument("--out", type=pathlib.Path, required=True)
    for x in (b, k):
        x.add_argument("--load-timeout", type=float, default=900, help="seconds to wait for a level to load")
        x.add_argument("--retry-minutes", type=float, default=0, help="if the account is in use, wait and retry")
        x.add_argument("--max-attempts", type=int, default=0, help="retry limit with --retry-minutes (0: no limit)")
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
            "watch": cmd_watch,
            "bench-observe": cmd_bench_observe,
            "see": cmd_see,
            "run": cmd_run,
            "asset": cmd_asset,
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
