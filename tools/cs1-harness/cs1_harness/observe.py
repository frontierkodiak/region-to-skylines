"""Watching a run: a timelapse, a live frame page, and a view-only VNC.

- One ffmpeg grabs the harness display at 1 fps. It writes the run's timelapse
  (H.264, played back at 30 fps, so a minute of run takes 2 s) and, every few
  seconds, an atomically replaced JPEG for the live page.
- A small loop writes the live page's status.json from the mod's status and the
  run's context (label, map, game minute, water, population).
- `cs1-harness watch` starts x11vnc on the harness display: view-only, bound to
  localhost, reached through an SSH tunnel. It opens no LAN or internet port.

None of these touch the game process; they read the X server it draws into.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import os
import pathlib
import secrets
import subprocess
import sys
import time

from .client import Client
from .config import Config

PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CS1 harness: live</title>
<style>
  body {{ margin: 0; font: 15px/1.4 -apple-system, system-ui, sans-serif; background: #111; color: #ddd; }}
  header {{ padding: 10px 14px; }}
  #line {{ font-weight: 600; }}
  #sub {{ color: #999; font-size: 13px; }}
  img {{ display: block; width: 100%; height: auto; background: #000; }}
</style>
<header><div id="line">{title}</div><div id="sub">waiting for the first frame</div></header>
<img id="frame" alt="harness display" src="frame.jpg">
<script>
async function tick() {{
  try {{
    const r = await fetch("status.json?t=" + Date.now(), {{cache: "no-store"}});
    const s = await r.json();
    document.getElementById("line").textContent = s.line;
    document.getElementById("sub").textContent = s.sub;
    if (s.frame) document.getElementById("frame").src = "frame.jpg?t=" + Date.now();
  }} catch (e) {{
    document.getElementById("sub").textContent = "no status (" + e + ")";
  }}
}}
tick();
setInterval(tick, {every_ms});
</script>
"""


def atomic_write(path: pathlib.Path, text: str):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def write_context(cfg: Config, **fields):
    """Merge run context (label, map, game minute, water, population) for the live page."""
    path = cfg.runtime_dir / "context.json"
    ctx = {}
    with contextlib.suppress(FileNotFoundError, ValueError):
        ctx = json.loads(path.read_text())
    ctx.update({k: v for k, v in fields.items() if v is not None})
    ctx["updated"] = time.time()
    atomic_write(path, json.dumps(ctx))


def ffmpeg_argv(cfg: Config, stage: pathlib.Path, record: bool, live: bool) -> list[str] | None:
    """One grabber for both outputs; None when neither is wanted."""
    if not (record or live):
        return None
    argv = [
        str(cfg.ffmpeg),
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostdin",
        "-y",  # overwrite: the live page keeps its last frame.jpg between runs
        "-f",
        "x11grab",
        "-draw_mouse",
        "0",
        "-framerate",
        "1",
        "-video_size",
        f"{cfg.width}x{cfg.height}",
        "-i",
        cfg.display,
    ]
    if record:
        argv += [
            "-map",
            "0:v",
            "-vf",
            "fps=1,scale=1280:-2,setpts=N/30/TB",
            "-fps_mode",
            "passthrough",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "1",
            # Fragmented MP4 stays playable if the grabber is killed.
            "-movflags",
            "+frag_keyframe+empty_moov+default_base_moof",
            str(stage / "timelapse.mp4"),
        ]
    if live:
        cfg.live_dir.mkdir(parents=True, exist_ok=True)
        argv += [
            "-map",
            "0:v",
            "-vf",
            f"fps=1/{cfg.live_every},scale=960:-2",
            "-q:v",
            "6",
            "-f",
            "image2",
            "-update",
            "1",
            "-atomic_writing",
            "1",
            str(cfg.live_dir / "frame.jpg"),
        ]
    return argv


def start(session, record: bool = True, live: bool = True, label: str | None = None):
    """Start the grabber and the live status writer as transient units."""
    cfg = session.cfg
    argv = ffmpeg_argv(cfg, session.stage, record, live)
    if argv:
        session.unit(cfg.rec_unit, *argv, props=["-p", "Nice=10", "-p", "KillSignal=SIGINT"])
    if live:
        cfg.live_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(
            cfg.live_dir / "index.html",
            PAGE.format(title=html.escape(label or "CS1 harness"), every_ms=cfg.live_every * 1000),
        )
        write_context(cfg, label=label, host=cfg.host, stage=str(session.stage), started=time.time())
        session.unit(
            cfg.live_unit,
            sys.executable,
            "-m",
            "cs1_harness.observe",
            "live-loop",
            "--host",
            cfg.host,
            props=["-p", "Nice=10"],
        )
    session.receipt["observe"] = {
        "record": str(session.stage / "timelapse.mp4") if record else None,
        "live_dir": str(cfg.live_dir) if live else None,
        "live_url": cfg.live_url if live else None,
    }


def mark_idle(cfg: Config, why: str):
    """After a session ends, leave the live page saying so instead of a stale frame."""
    if not cfg.live_dir.exists():
        return
    atomic_write(
        cfg.live_dir / "status.json",
        json.dumps(
            {
                "line": "No harness run on " + cfg.host,
                "sub": f"{why} at {time.strftime('%H:%M %Z')}; the frame below is the last one taken",
                "frame": True,
            }
        ),
    )
    with contextlib.suppress(FileNotFoundError):
        (cfg.runtime_dir / "context.json").unlink()


def status_line(cfg: Config, st: dict | None, ctx: dict) -> dict:
    label = ctx.get("label") or "CS1 harness"
    if st is None:
        return {"line": label, "sub": f"{cfg.host}: game not answering yet (starting or loading)", "frame": True}
    parts = [label]
    if ctx.get("map"):
        parts.append(ctx["map"])
    if ctx.get("minute") is not None and ctx.get("of_minutes"):
        parts.append(f"game-minute {ctx['minute']:.1f} of {ctx['of_minutes']:g}")
    sub = []
    if st.get("in_game"):
        sub.append(f"population {st.get('population', 0)}")
        if ctx.get("water"):
            sub.append(ctx["water"])
        sub.append(f"speed {st.get('final_speed')}x" if not st.get("paused") else "paused")
    else:
        sub.append("main menu" if not st.get("loading") else "loading")
    if st.get("render_fps"):
        sub.append(f"{st['render_fps']:.0f} fps")
    sub.append(f"{cfg.host} {st.get('gpu', '')}".strip())
    return {"line": " · ".join(parts), "sub": " · ".join(sub), "frame": True, "updated": time.time()}


def live_loop(cfg: Config):
    client = Client(cfg.port, timeout=10)
    while True:
        ctx = {}
        with contextlib.suppress(FileNotFoundError, ValueError):
            ctx = json.loads((cfg.runtime_dir / "context.json").read_text())
        st = client.try_status()
        atomic_write(cfg.live_dir / "status.json", json.dumps(status_line(cfg, st, ctx)))
        time.sleep(cfg.live_every)


# -- watch: view-only VNC ---------------------------------------------------


def vnc_password(cfg: Config) -> tuple[str, pathlib.Path]:
    """A per-host VNC password (8 characters, the VNC limit), stored mode 600."""
    d = pathlib.Path.home() / ".config" / "cs1-harness"
    d.mkdir(parents=True, exist_ok=True)
    plain, stored = d / "vnc.pass.txt", d / "vnc.passwd"
    if not plain.exists() or not stored.exists():
        pw = secrets.token_urlsafe(6)[:8]
        old = os.umask(0o077)
        try:
            plain.write_text(pw + "\n")
            subprocess.run([*x11vnc_cmd(cfg), "-storepasswd", pw, str(stored)], check=True, capture_output=True)
        finally:
            os.umask(old)
    return plain.read_text().strip(), stored


def x11vnc_cmd(cfg: Config) -> list[str]:
    return ["/usr/bin/env", f"LD_LIBRARY_PATH={cfg.x11vnc}/usr/lib/x86_64-linux-gnu", f"{cfg.x11vnc}/usr/bin/x11vnc"]


def watch_start(session) -> dict:
    cfg = session.cfg
    pw, stored = vnc_password(cfg)
    session.unit(
        cfg.vnc_unit,
        *x11vnc_cmd(cfg),
        "-display",
        cfg.display,
        "-viewonly",
        "-localhost",
        "-rfbport",
        str(cfg.vnc_port),
        "-rfbauth",
        str(stored),
        "-shared",
        "-forever",
        "-noxdamage",
        "-nopw",
        "-quiet",
        props=["-p", "Nice=10"],
    )
    return {"port": cfg.vnc_port, "password": pw}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m cs1_harness.observe")
    p.add_argument("cmd", choices=["live-loop"])
    p.add_argument("--host")
    a = p.parse_args(argv)
    live_loop(Config.for_host(a.host))


if __name__ == "__main__":
    main()
