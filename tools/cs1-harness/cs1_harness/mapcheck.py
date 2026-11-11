"""A timed New Game run on one map: screenshots, water, population, errors, GPU."""

from __future__ import annotations

import json
import math
import pathlib
import shutil
import time

from . import landmarks, new_game_panel, observe, startup_views
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
    def __init__(self, session: Session, out: pathlib.Path, points, views, log=print, paths=()):
        self.s = session
        self.c = session.client
        self.out = out
        self.points = points
        self.views = views
        self.paths = paths
        self.panel_expectations = new_game_panel.request(out)
        self.landmark_expectations = landmarks.request(out)
        self.startup_view_expectations = startup_views.request(out)
        self.log = log
        self.timeline = open(out / "timeline.jsonl", "w")
        self.shots: list[dict] = []
        self.render_fps = 0  # cap drawing between screenshot sets (0: unlimited); see `bench-speed`

    def path_checks(self, label):
        """Use native pathfinding, retaining every returned position and missing segment."""
        checks = []
        if self.paths:
            (self.out / f"networks-{label}.json").write_text(json.dumps(self.c.call("networks"), indent=2) + "\n")
        for test in self.paths:
            request = {k: test[k] for k in ("from", "to", "rail")}
            path = self.c.call("path_start", **request)
            deadline = time.monotonic() + 60
            while True:
                result = self.c.call("path_result", id=path["id"])
                if result["complete"]:
                    break
                if time.monotonic() >= deadline:
                    raise HarnessError(f"native path {test['name']} did not finish in 60 seconds")
                time.sleep(0.1)
            visited = {p[0] for p in result["positions"]}
            result.update(
                name=test["name"],
                missing_segments=sorted(set(test.get("expected_segments", ())) - visited),
            )
            checks.append(result)
        self.record("paths", {"label": label, "checks": checks})
        return checks

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

    def render(self, fps: int):
        """Cap drawing; a mod build without the `render` op just keeps drawing at full rate."""
        if not self.render_fps:
            return
        try:
            self.c.call("render", fps=fps, camera=True)
        except HarnessError as e:
            self.log(f"render cap unavailable ({e}); drawing at full rate")
            self.render_fps = 0

    def player_path(self) -> dict | None:
        """Legacy player-path shots: current view with UI, then maximum camera size.

        This is not GameAreaTool/AreasVisible evidence. Actual startup/Areas
        capture runs earlier, before this method or scenario construction.
        The historical player-area-zoom filename is retained for consumers."""
        try:
            cam = self.c.call("camera_state")
        except HarnessError as e:
            self.log(f"camera_state unavailable ({e}); no player's-path shots")
            return None
        # Facing from the camera's own forward vector (independent of how yaw is counted).
        fx, _, fz = cam.get("forward") or [0, 0, 1]
        bearing = (math.degrees(math.atan2(fx, fz)) + 360) % 360 if (fx or fz) else cam["heading_deg"]
        cam["heading_deg"] = round(bearing, 1)
        cam["facing"] = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][
            int(((bearing + 22.5) % 360) // 45)
        ]
        self.record("opening_camera", cam)
        paused = self.c.call("stats")["paused"]
        self.c.call("run", paused=True)
        try:
            for name, size in (("opening", None), ("area-zoom", cam.get("max_size"))):
                if size:
                    self.c.call(
                        "camera",
                        position=cam["position"],
                        size=size,
                        yaw=cam["yaw"],
                        pitch=cam["pitch"],
                    )
                time.sleep(5)
                staged = self.s.stage / "shots" / f"player-{name}.png"
                self.c.call("screenshot", path=str(staged))
                for _ in range(60):
                    if staged.exists() and staged.stat().st_size > 0:
                        break
                    time.sleep(0.5)
                time.sleep(0.5)
                self.shots.append({"label": "player", "view": name, "file": f"shots/{staged.name}"})
                self.record("screenshot", self.shots[-1])
        finally:
            self.c.call("camera", release=True)
            self.c.call("run", paused=paused)
        return cam

    def world_heights(self, n: int = 40):
        """Terrain heights from the game's own world-coordinate sampler on an n x n grid.

        The ground-truth check uses these, so it doesn't depend on how we read the dump."""
        step = 17280 / n
        pts = [[-8640 + step * (i + 0.5), -8640 + step * (j + 0.5)] for j in range(n) for i in range(n)]
        heights = []
        for k in range(0, len(pts), 400):
            heights += [p["terrain"] for p in self.c.call("water", points=pts[k : k + 400])["samples"]]
        grids = self.s.stage / "grids"
        grids.mkdir(parents=True, exist_ok=True)
        (grids / "t000-terrain-points.json").write_text(
            json.dumps(
                {"source": "TerrainManager.SampleRawHeightSmooth via the mod", "points": pts, "heights": heights}
            )
        )

    def screenshots(self, label: str):
        paused = self.c.call("stats")["paused"]
        self.c.call("run", paused=True)
        self.c.call("ui", visible=False)
        self.render(0)
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
            self.render(self.render_fps)
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
        scenario: str | None = None,
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
                if m["path"]
                and pathlib.Path(m["path"]).exists()
                and any(pathlib.Path(m["path"]).samefile(p) for p in (installed, crp))
            ),
            None,
        )
        self.record("maps", {"maps": maps})
        if entry is None:
            raise HarnessError(f"the game does not list {installed.name} as a map")
        self.log(f"starting New Game on {entry['map_name']} (listed in New Game: {entry['published']})")
        observe.write_context(s.cfg, map=entry["map_name"])
        if self.panel_expectations is not None:
            new_game_panel.capture(s, self.out, entry["path"], self.panel_expectations)
        self.c.call("new_game", path=entry["path"])
        status = self.c.wait(
            lambda st: st.get("in_game") and not st.get("loading"), load_timeout, "the city to load", alive=s.alive
        )
        startup_world = landmarks.capture(s, self.out, self.landmark_expectations)
        if self.startup_view_expectations is not None:
            startup_views.capture(s, self.out, self.startup_view_expectations)
        self.c.call("run", paused=True, speed=speed, day_night=False)
        fixture = None
        if scenario:
            from . import scenario as scenario_mod

            fixture = scenario_mod.build(s, self.out, log=self.log)
            self.record("scenario", fixture)
            x, _, z = fixture["result"]["center"]
            self.views = [*self.views, {"name": "test-city", "x": x, "z": z, "size": 650, "pitch": 60}]
        fdt = status["fixed_delta_time"]
        frames_per_minute = 60.0 / fdt
        start_frame = status["frame"]
        target = start_frame + int(game_minutes * frames_per_minute)
        self.log(
            f"city loaded at frame {start_frame}; {frames_per_minute:.0f} frames per game-minute; "
            f"running to frame {target}"
        )
        opening = self.player_path()
        self.dump("t000", terrain=True)
        self.world_heights()
        self.sample("t000")
        paths_start = self.path_checks("t000")
        self.screenshots("t000")

        def minute(frame):
            return (frame - start_frame) / frames_per_minute

        next_sample = sample_every
        next_shot = shot_every
        next_dump = dump_every
        population_observations = [{"minute": 0.0, "population": self.c.call("stats")["population"]}]
        self.render(self.render_fps)
        self.c.call("run", paused=False, speed=speed)
        wall_start = time.monotonic()
        last_progress = (wall_start, start_frame)
        while True:
            s.alive()
            stats = self.c.call("stats")
            m = minute(stats["frame"])
            if stats["population"] != population_observations[-1]["population"]:
                population_observations.append({"minute": round(m, 3), "population": stats["population"]})
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
        if scenario:
            fixture = {
                **fixture,
                "final": self.c.call("scenario_status"),
                "reachability": scenario_mod.reachability(s),
            }
            self.record("scenario_end", fixture)
            (self.out / "scenario.json").write_text(json.dumps(fixture, indent=2) + "\n")
        paths_end = self.path_checks(end)
        self.screenshots(end)
        status = self.c.call("status")
        self.timeline.close()
        return {
            "map": entry,
            "startup_world": startup_world,
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
            "scenario": fixture,
            "requested_scenario": scenario,
            "population_observations": population_observations,
            "opening_camera": opening,
            "paths_start": paths_start,
            "paths_end": paths_end,
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
