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
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time

from . import build as build_mod
from . import notify as notify_mod
from . import registry
from . import report as report_mod
from . import setup as setup_mod
from . import triage as triage_mod
from . import verdict as verdict_mod
from .client import Client, HarnessError
from .config import Config
from .mapcheck import MapCheck, collect, load_probe_file
from .session import EX_TEMPFAIL, Blocked, Session


def log(msg: str):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


SLOT_POLL_SECONDS = 2


@contextlib.contextmanager
def slot(cfg, stage, wait_minutes: float, meta: dict | None = None):
    """A Session, waiting up to `wait_minutes` while another user holds the host's harness slot.

    Waiters take turns oldest first: a waiter tries the lock only when no older
    waiter (registered in the slot's waiting/ directory) is still alive. Runs from
    checkouts older than this rule don't register, so they can still take a gap.
    It never ends or takes over the other session. Waits, acquisitions and
    releases go to the contention log, and `cs1-harness queue` shows this process.
    """
    from . import slots

    meta = meta or {}
    t0 = time.monotonic()
    deadline = t0 + wait_minutes * 60
    last = None
    try:
        while True:
            ahead = slots.older_waiters(cfg) if last else []
            if ahead:
                if time.monotonic() >= deadline:
                    slots.mark_gave_up(cfg, meta, time.monotonic() - t0, f"{len(ahead)} older waiters")
                    raise Blocked(f"{len(ahead)} older waiters are ahead in the slot queue", EX_TEMPFAIL, busy=True)
                time.sleep(SLOT_POLL_SECONDS)
                continue
            with contextlib.ExitStack() as stack:
                try:
                    s = stack.enter_context(Session(cfg, stage, log=log))
                except Blocked as b:
                    if not b.busy or time.monotonic() >= deadline:
                        if last:
                            slots.mark_gave_up(cfg, meta, time.monotonic() - t0, str(b))
                        raise
                    if str(b) != last:
                        log(f"waiting for the harness slot: {b}")
                        if last is None:
                            slots.mark_waiting(cfg, meta, str(b))
                        last = str(b)
                    time.sleep(SLOT_POLL_SECONDS)
                    continue
                if last:
                    log("harness slot acquired")
                slots.mark_acquired(cfg, meta, time.monotonic() - t0)
                held = time.monotonic()
                try:
                    yield s
                finally:
                    slots.mark_released(cfg, meta, time.monotonic() - held, detached=s.detached)
                return
    finally:
        slots.unmark_waiting(cfg)


def staging(cfg, out: pathlib.Path) -> pathlib.Path:
    """This process's own staging directory. Two runs whose --out share a name
    (…/a/asheville, …/b/asheville) must not share one: a run blocked on the slot
    collects its staging, and would otherwise take the active run's files."""
    return cfg.harness_home / "runs" / f"{out.name}-{os.getpid()}"


def cmd_build(cfg, a):
    print(json.dumps(build_mod.build(cfg), indent=2))


def cmd_setup(cfg, a):
    print(json.dumps(setup_mod.undo(cfg) if a.undo else setup_mod.setup(cfg), indent=2))


def cmd_doctor(cfg, a):
    """Check the GPU path without starting Steam: VirtualGL on the harness display, pinned by PCI bus."""
    with slot(cfg, cfg.harness_home / "runs" / "doctor", a.wait_minutes) as s:
        print(json.dumps({"host": cfg.host, "steam": cfg.steam, **s.pin_gpu()}, indent=2))
    shutil.rmtree(cfg.harness_home / "runs" / "doctor", ignore_errors=True)
    with contextlib.suppress(OSError):
        (cfg.harness_home / "runs").rmdir()


def cmd_up(cfg, a):
    """Start a session and leave it running: display, bus, Steam, game at the main menu."""
    stage = cfg.harness_home / "runs" / (a.name or time.strftime("session-%Y%m%d-%H%M%S"))
    with slot(cfg, stage, a.wait_minutes, {"command": "up", "label": a.label or a.name}) as s:
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
    stage = staging(cfg, out)
    with slot(cfg, stage, a.wait_minutes, {"command": "bench-observe", "out": str(out)}) as s:
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
    from . import slots

    s = Session.attach(cfg, log=log)
    started = json.loads(cfg.state_file.read_text()).get("started")
    s.stop()
    slots.holder_file(cfg).unlink(missing_ok=True)
    slots.log_event("release", held_s=round(time.time() - started, 1) if started else None, command="down")
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
    if a.probes:
        # Freeze what the verdict reads, so editing the source later can't change it.
        shutil.copyfile(a.probes, out / "probes.json")
        ref = json.loads(a.probes.read_text())
        if isinstance(ref, dict) and ref.get("reference_water"):
            shutil.copyfile(a.probes.parent / ref["reference_water"], out / "reference-water.u16")
    harness = verdict_mod.harness_commit()
    stage = staging(cfg, out)
    attempt = 0
    while True:
        attempt += 1
        try:
            meta = {
                "command": "run",
                "label": a.label or f"map check: {a.map.name}",
                "issue": a.issue,
                "out": str(out),
                "game_minutes": a.game_minutes,
            }
            with slot(cfg, stage, a.wait_minutes, meta) as s:
                observers(s, a, default_label=f"map check: {a.map.name}")
                probe_data = json.loads(a.probes.read_text()) if a.probes else {}
                paths = probe_data.get("paths", []) if isinstance(probe_data, dict) else []
                r = MapCheck(s, out, points, views, log=log, paths=paths)
                result = r.execute(
                    a.map.resolve(),
                    a.game_minutes,
                    a.speed,
                    a.sample_every,
                    a.screenshot_every,
                    a.dump_every,
                    a.load_timeout,
                )
                result["probes"] = str(a.probes.resolve()) if a.probes else None
                result["requested_game_minutes"] = a.game_minutes
                result["harness"] = harness
                result["issue"] = a.issue
                result["label"] = s.label
                result["clef"] = a.clef
                result["gpu_processes"] = s.gpu_processes()
            collect(stage, out)
            report = report_mod.build(
                out, {**result, "session": json.loads((out / "session-receipt.json").read_text())}
            )
            print((out / "report.md").read_text())
            v = verdict_mod.judge(out)
            log(verdict_mod.summary(v))
            t = triage_mod.attach(out, cfg)
            if t:
                log(f"triage: {t['class']} ({t['why']})")
            registry.add(out)
            announce(out, a)
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
            finish_error(cfg, out, a, f"blocked: {b}", b.code)
            return b.code
        except HarnessError as e:
            if stage.exists():
                collect(stage, out)
            log(f"failed: {e}")
            finish_error(cfg, out, a, f"failed: {e}", 1)
            return 1
        except Exception:  # a harness bug: judge, triage and report it like any other failure
            import traceback

            if stage.exists():
                collect(stage, out)
            tb = traceback.format_exc()
            log(f"harness error:\n{tb}")
            (out / "traceback.txt").write_text(tb)
            finish_error(cfg, out, a, "Traceback: " + tb.strip().splitlines()[-1], 70)
            return 70


def finish_error(cfg, out: pathlib.Path, a, reason: str, code: int):
    verdict_mod.error_verdict(out, "map-soak", reason, code, issue=a.issue, label=a.label)
    t = triage_mod.attach(out, cfg)
    if t:
        log(f"triage: {t['class']} ({t['why']})")
    registry.add(out)
    announce(out, a)


def announce(out: pathlib.Path, a):
    """With --notify, comment the verdict on the run's issue. Never fails the run."""
    if not getattr(a, "notify", False):
        return
    issue = a.issue or registry.issue_of(out, {"label": a.label})
    if not issue:
        log("--notify: no issue (give --issue); not posted")
        return
    try:
        r = notify_mod.post(out, issue, wake=a.wake)
    except Exception as e:  # noqa: BLE001 - the run's result stands; posting is best effort
        log(f"--notify: could not post on {issue}: {e!r}")
        return
    log(f"posted the verdict on {issue}" if r["posted"] else f"--notify: posting on {issue} failed: {r.get('error')}")


def cmd_notify(cfg, a):
    """Post a finished run's verdict on an issue (what `run --notify` does at the end)."""
    r = notify_mod.post(a.dir, a.issue, wake=a.wake, dry_run=a.dry_run)
    print(r["body"] if a.dry_run else json.dumps(r, indent=2))
    if a.dry_run:
        print("attachments:", *r["attachments"], sep="\n  ")
    return 0 if a.dry_run or r["posted"] else 1


def cmd_submit(cfg, a):
    """Start a `run` detached from this shell, so the agent that asked can end its turn.

    The job waits for the slot, runs, and comments its verdict on --issue,
    @mentioning the issue's agent assignee (that starts the agent's next run).
    """
    args = list(a.run_args)
    if args and args[0] == "--":
        args = args[1:]
    # The job runs in the harness checkout; make every path absolute against the submitter's cwd.
    for i, arg in enumerate(args[:-1]):
        if arg in ("--map", "--probes", "--out", "--from-save"):
            args[i + 1] = str(pathlib.Path(args[i + 1]).expanduser().resolve())
    if not args or args[0] != "run":
        raise SystemExit("usage: cs1-harness submit --issue PL-NNN -- run --map … --out … [run options]")
    if "--out" not in args:
        raise SystemExit("submit needs run's --out")
    out = pathlib.Path(args[args.index("--out") + 1]).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    args = [*args, "--issue", a.issue, "--notify"] + (["--wake"] if not a.no_wake else [])
    if "--wait-minutes" not in args:
        args += ["--wait-minutes", str(a.wait_minutes)]
    if "--retry-minutes" not in args:
        args += ["--retry-minutes", "30", "--max-attempts", "8"]
    tool = pathlib.Path(__file__).resolve().parents[1]
    unit = f"cs1-harness-job-{a.issue.lower()}-{time.strftime('%H%M%S')}"
    cmd = [
        "systemd-run",
        "--user",
        f"--unit={unit}",
        "--collect",
        "--quiet",
        f"--working-directory={tool}",
        f"--setenv=PATH={os.environ.get('PATH', '')}",
        f"--setenv=HOME={pathlib.Path.home()}",
        # `systemctl stop` must let the run tear the game down (quit waits up to 60 s, Steam 90 s):
        # SIGTERM to uv, which forwards it to the harness, then up to 5 min before anything is killed.
        "--property=KillMode=mixed",
        "--property=TimeoutStopSec=300",
        f"--property=StandardOutput=append:{out / 'submit.log'}",
        f"--property=StandardError=append:{out / 'submit.log'}",
        "uv",
        "run",
        "cs1-harness",
        *args,
    ]
    subprocess.run(cmd, check=True)
    print(
        json.dumps(
            {
                "unit": unit,
                "issue": a.issue,
                "out": str(out),
                "log": str(out / "submit.log"),
                "stop": f"systemctl --user stop {unit}",
                "args": args,
            },
            indent=2,
        )
    )
    return 0


def cmd_queue(cfg, a):
    """Who holds the slot, the issue and ETA, and who is waiting; --stats sums contention."""
    from . import slots

    if a.stats:
        print(json.dumps(slots.stats(a.hours), indent=2))
        return 0
    st = slots.status(cfg)
    if a.json:
        print(json.dumps(st, indent=2, default=str))
        return 0
    h = st["holder"]
    if not h:
        print("slot free")
    else:
        eta = f", about {h['remaining_minutes']} min left" if h.get("remaining_minutes") is not None else ""
        print(
            f"held by {h.get('command')} pid {h.get('pid')} · {h.get('issue') or '-'} · {h.get('label') or '-'} · "
            f"{h.get('held_minutes')} min so far{eta}"
        )
    for i, w in enumerate(st["waiting"], 1):
        print(
            f"  {i}. {w.get('command')} pid {w['pid']} · {w.get('issue') or '-'} · {w.get('label') or '-'} · "
            f"waiting {w.get('waiting_minutes')} min"
        )
    return 0


def cmd_verdict(cfg, a):
    """Judge finished run directories; exit 1 if any fails or can't be judged."""
    worst, judged = 0, []
    for d in a.dirs:
        try:
            v = verdict_mod.judge(d)
        except FileNotFoundError as e:
            log(str(e))
            worst = 1
            continue
        t = triage_mod.attach(d)
        if t:
            v["triage"] = t
        judged.append({"dir": str(d), **v})
        if not a.json:
            print(f"{d}: {verdict_mod.summary(v)}" + (f" · triage {t['class']}: {t['why']}" if t else ""))
        worst = max(worst, 0 if v["verdict"] == "pass" else 1)
    if a.json:
        print(json.dumps(judged, indent=2, default=str))
    return worst


def cmd_mcp(cfg, a):
    """Serve the harness over MCP (stdio)."""
    from . import mcp_server

    mcp_server.main()


def cmd_runs(cfg, a):
    """List registered runs, or add run directories to the registry."""
    if a.index:
        dirs = registry.scan(a.index)
        known = {r["path"] for r in registry.load()}
        for d in dirs:
            if str(d) in known and not a.rejudge:
                continue
            try:
                e = registry.add(d)
            except (FileNotFoundError, KeyError, ValueError) as err:
                log(f"skipped {d}: {err!r}")
                continue
            log(f"indexed {e['id']}: {e['verdict']}")
        return 0
    rows = registry.find(
        registry.load(),
        issue=a.issue,
        check_type=a.check_type,
        verdict=a.verdict,
        map=a.map,
        map_sha256=a.map_sha,
        harness_commit=a.commit,
    )
    if a.json:
        print(json.dumps(rows, indent=2))
        return 0
    for r in rows:
        m = r["metrics"]
        probes = f"{m['probes_wet_end']}/{m['probes_required']}" if m.get("probes_required") else "-"
        print(
            f"{(r['finished'] or '')[:16]:16}  {r['verdict'] or '?':5}  {r['issue'] or '-':7}  "
            f"{(r['map'] or '-')[:22]:22}  {(r['map_sha256'] or '-')[:8]:8}  {(r['harness_commit'] or '-')[:7]:7}  "
            f"probes {probes:7}  flood {m.get('flood_km2') if m.get('flood_km2') is not None else '-'}  {r['path']}"
        )
    return 0


def cmd_compare(cfg, a):
    """Overlay water, wet probes and population over time for two or more map runs."""
    result = registry.compare(a.runs, a.out.resolve())
    for s in result["runs"]:
        last = s["samples"][-1] if s["samples"] else {}
        print(
            f"{s['label']}: {s['verdict']}; end {last.get('minute')} min, volume {last.get('volume_m3')}, "
            f"wet {last.get('wet_required')}/{last.get('required')}, population {last.get('population')}"
        )
    print(f"checks that differ: {', '.join(result['differs']) or 'none'}")
    print(result["png"])
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="cs1-harness", description=__doc__)
    p.add_argument("--host", help="host profile (blade, worm); default: this machine's hostname")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="compile the harness mod against the installed game")
    s = sub.add_parser("setup", help="user-level host setup (VirtualGL, Steam launch wrapper)")
    s.add_argument("--undo", action="store_true", help="remove everything setup added")
    doctor = sub.add_parser("doctor", help="check GPU rendering on the harness display without Steam")
    doctor.add_argument("--wait-minutes", type=float, default=0, help="wait for the shared harness slot")
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
    r.add_argument("--issue", help="the issue this run is for (e.g. PL-857); default: from --label or --out")
    r.add_argument("--notify", action="store_true", help="comment the verdict, frames and timelapse on the issue")
    r.add_argument("--wake", action="store_true", help="with --notify, @mention the issue's agent assignee")
    r.add_argument("--no-record", action="store_true", help="skip the timelapse recording")
    r.add_argument("--no-live", action="store_true", help="skip the live frame page")
    r.add_argument("--max-attempts", type=int, default=0, help="retry limit with --retry-minutes (0: no limit)")
    r.add_argument(
        "--wait-minutes",
        type=float,
        default=0,
        help="if another agent or person holds this host's harness, wait up to this long for it (0: exit 75)",
    )
    q = sub.add_parser("runs", help="list registered runs (filters AND together), or --index run directories")
    q.add_argument("--issue")
    q.add_argument("--check-type", choices=("map-soak", "asset-check"))
    q.add_argument("--verdict", choices=("pass", "fail", "error"))
    q.add_argument("--map", help="map name as the game lists it")
    q.add_argument("--map-sha", help="map sha256 prefix")
    q.add_argument("--commit", help="harness commit prefix")
    q.add_argument("--json", action="store_true")
    q.add_argument("--index", nargs="+", type=pathlib.Path, metavar="DIR", help="register runs found under these")
    q.add_argument("--rejudge", action="store_true", help="with --index, re-add runs already registered")
    k = sub.add_parser("compare", help="overlay two or more map runs over time (compare.png, compare.json)")
    k.add_argument("runs", nargs="+", help="run directories or registry ids")
    k.add_argument("--out", type=pathlib.Path, required=True)
    qq = sub.add_parser("queue", help="who holds the harness slot (issue, ETA) and who is waiting")
    qq.add_argument("--json", action="store_true")
    qq.add_argument("--stats", action="store_true", help="contention summary from the slot log")
    qq.add_argument("--hours", type=float, default=24, help="with --stats, the window (default 24 h)")
    n = sub.add_parser("notify", help="comment a finished run's verdict on an issue")
    n.add_argument("dir", type=pathlib.Path)
    n.add_argument("--issue", required=True)
    n.add_argument("--wake", action="store_true", help="@mention the issue's agent assignee")
    n.add_argument("--dry-run", action="store_true", help="print the comment and attachments; post nothing")
    m = sub.add_parser("submit", help="start a run detached; its verdict is commented on --issue when it ends")
    m.add_argument("--issue", required=True, help="where the verdict goes (e.g. PL-857)")
    m.add_argument("--no-wake", action="store_true", help="comment without @mentioning the assignee")
    m.add_argument("--wait-minutes", type=float, default=240, help="how long the job waits for the slot")
    m.add_argument("run_args", nargs=argparse.REMAINDER, help="-- run --map … --out … [options]")
    sub.add_parser("mcp", help="serve these commands over MCP (stdio), for agents that prefer tools")
    j = sub.add_parser("verdict", help="(re)judge finished run directories and write verdict.json")
    j.add_argument("dirs", nargs="+", type=pathlib.Path)
    j.add_argument("--json", action="store_true", help="print the full verdict")
    a = p.parse_args(argv)
    cfg = Config.for_host(a.host)

    # `timeout` and job control send SIGTERM/SIGHUP. Turn them into SystemExit so
    # every open session's __exit__ runs and stops the game, Steam and units.
    def terminate(signum, _frame):
        raise SystemExit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, terminate)
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
            "verdict": cmd_verdict,
            "mcp": cmd_mcp,
            "runs": cmd_runs,
            "notify": cmd_notify,
            "queue": cmd_queue,
            "submit": cmd_submit,
            "compare": cmd_compare,
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
