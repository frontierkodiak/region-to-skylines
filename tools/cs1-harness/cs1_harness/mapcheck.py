"""A timed New Game run on one map: screenshots, water, population, errors, GPU."""

from __future__ import annotations

import json
import pathlib
import shutil
import time

from . import observe
from .client import HarnessError
from .session import Session

DEFAULT_VIEWS = [{"name": "overview", "x": 0, "z": 0, "size": 4000, "yaw": 0, "pitch": 70}]


def load_probe_file(path: pathlib.Path | None) -> tuple[list[dict], list[dict]]:
    """Points and views. A file is a JSON object with "points" and/or "views",
    or a bare list of points. A point is {"name", "x", "z"} or [x, z]."""
    if path is None:
        return [], DEFAULT_VIEWS
    data = json.loads(path.read_text())
    if isinstance(data, list):
        data = {"points": data}
    points = []
    for i, p in enumerate(data.get("points", [])):
        if isinstance(p, dict):
            points.append({"name": p.get("name", f"p{i}"), "x": float(p["x"]), "z": float(p["z"])})
        else:
            points.append({"name": f"p{i}", "x": float(p[0]), "z": float(p[-1])})
    return points, data.get("views") or DEFAULT_VIEWS


class MapCheck:
    def __init__(self, session: Session, out: pathlib.Path, points, views, log=print):
        self.s = session
        self.c = session.client
        self.out = out
        self.points = points
        self.views = views
        self.log = log
        self.timeline = open(out / "timeline.jsonl", "w")
        self.shots: list[dict] = []

    def record(self, kind: str, data: dict):
        self.timeline.write(json.dumps({"kind": kind, "wall": time.time(), **data}) + "\n")
        self.timeline.flush()

    def sample(self, label: str) -> dict:
        stats = self.c.call("stats")
        water = self.c.call("water", points=[[p["x"], p["z"]] for p in self.points])
        for p, sample in zip(self.points, water["samples"]):
            sample["name"] = p["name"]
        row = {"label": label, "stats": stats, "water": water}
        self.record("sample", row)
        if self.points:
            wet = sum(1 for s in water["samples"] if s["wet"])
            summary = f"wet probes {wet}/{len(self.points)}, volume {water['volume_m3'] / 1e6:.2f} M m3"
        else:
            summary = f"volume {water['volume_m3'] / 1e6:.2f} M m3"
        observe.write_context(self.s.cfg, water=summary)
        return row

    def dump(self, label: str, terrain: bool = False) -> dict:
        d = self.c.call("dump", dir=str(self.s.stage / "grids"), prefix=label, terrain=terrain)
        self.record("dump", {"label": label, **d})
        return d

    def screenshots(self, label: str):
        paused = self.c.call("stats")["paused"]
        self.c.call("run", paused=True)
        self.c.call("ui", visible=False)
        try:
            for v in self.views:
                self.c.call(
                    "camera",
                    position=[v["x"], v["z"]],
                    size=v.get("size", 2000),
                    yaw=v.get("yaw", 0),
                    pitch=v.get("pitch", 60),
                )
                time.sleep(v.get("settle", 4))
                staged = self.s.stage / "shots" / f"{label}-{v['name']}.png"
                self.c.call("screenshot", path=str(staged))
                for _ in range(60):
                    if staged.exists() and staged.stat().st_size > 0:
                        break
                    time.sleep(0.5)
                else:
                    raise HarnessError(f"screenshot {staged.name} was not written")
                time.sleep(0.5)
                self.shots.append({"label": label, "view": v["name"], "file": f"shots/{staged.name}"})
                self.record("screenshot", self.shots[-1])
        finally:
            self.c.call("camera", release=True)
            self.c.call("ui", visible=True)
            self.c.call("run", paused=paused)

    def execute(
        self,
        crp: pathlib.Path,
        game_minutes: float,
        speed: int,
        sample_every: float,
        shot_every: float,
        dump_every: float,
        load_timeout: float,
    ) -> dict:
        s = self.s
        installed = s.install_map(crp)
        menu = s.launch(["--noWorkshop"])
        maps = self.c.call("maps")["maps"]
        # The game may name the file through an alias (Flatpak's data -> .local/share link).
        entry = next(
            (
                m
                for m in maps
                if m["path"] and pathlib.Path(m["path"]).exists() and pathlib.Path(m["path"]).samefile(installed)
            ),
            None,
        )
        self.record("maps", {"maps": maps})
        if entry is None:
            raise HarnessError(f"the game does not list {installed.name} as a map")
        self.log(f"starting New Game on {entry['map_name']} (listed in New Game: {entry['published']})")
        observe.write_context(s.cfg, map=entry["map_name"])
        self.c.call("new_game", path=entry["path"])
        status = self.c.wait(
            lambda st: st.get("in_game") and not st.get("loading"), load_timeout, "the city to load", alive=s.alive
        )
        self.c.call("run", paused=True, speed=speed)
        fdt = status["fixed_delta_time"]
        frames_per_minute = 60.0 / fdt
        start_frame = status["frame"]
        target = start_frame + int(game_minutes * frames_per_minute)
        self.log(
            f"city loaded at frame {start_frame}; {frames_per_minute:.0f} frames per game-minute; "
            f"running to frame {target}"
        )
        self.dump("t000", terrain=True)
        self.sample("t000")
        self.screenshots("t000")

        def minute(frame):
            return (frame - start_frame) / frames_per_minute

        next_sample = sample_every
        next_shot = shot_every
        next_dump = dump_every
        self.c.call("run", paused=False, speed=speed)
        wall_start = time.monotonic()
        last_progress = (wall_start, start_frame)
        while True:
            s.alive()
            stats = self.c.call("stats")
            m = minute(stats["frame"])
            observe.write_context(s.cfg, minute=m, of_minutes=game_minutes)
            if stats["frame"] != last_progress[1]:
                last_progress = (time.monotonic(), stats["frame"])
            elif time.monotonic() - last_progress[0] > 300:
                raise HarnessError("simulation made no progress for 5 minutes")
            if m >= game_minutes:
                break
            tag = f"t{int(m):03d}"
            if m >= next_sample:
                self.sample(tag)
                next_sample += sample_every
            if m >= next_dump:
                self.dump(tag)
                next_dump += dump_every
            if m >= next_shot:
                self.screenshots(tag)
                next_shot += shot_every
            time.sleep(2)
        self.c.call("run", paused=True)
        wall = time.monotonic() - wall_start
        end = f"t{int(round(game_minutes)):03d}"
        self.dump(end)
        final = self.sample(end)
        self.screenshots(end)
        status = self.c.call("status")
        self.timeline.close()
        return {
            "map": entry,
            "menu_status": {
                k: menu.get(k) for k in ("gpu", "gpu_memory_mb", "screen", "unity", "plugins", "enabled_mod_count")
            },
            "fixed_delta_time": fdt,
            "frames_per_game_minute": frames_per_minute,
            "start_frame": start_frame,
            "end_frame": final["stats"]["frame"],
            "game_minutes": minute(final["stats"]["frame"]),
            "speed": speed,
            "wall_seconds": wall,
            "first_dump": "t000",
            "last_dump": end,
            "shots": self.shots,
            "final_status": {k: status.get(k) for k in ("error_count", "errors", "population", "game_time")},
        }


def collect(stage: pathlib.Path, out: pathlib.Path):
    """Move what the game wrote (sandbox-visible staging) into the output directory."""
    for item in stage.iterdir():
        dest = out / item.name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(item), str(dest))
    stage.rmdir()
