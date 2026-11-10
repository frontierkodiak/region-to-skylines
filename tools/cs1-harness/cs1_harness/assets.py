"""Asset Editor mode (PL-880): build a .crp from an import set, then check it in a fresh game.

`build` opens the Asset Editor on a new asset, imports `<name>.fbx` (with `<name>_lod.fbx` and
the `_d/_s/_i/_c/_n/_a` maps beside it) onto a building template, sets the lot, and saves
through the game's own save panel. `check` starts a different game process with only the
.crp installed, starts a New Game on a map, places the building completed, and takes close,
distant and night views, then saves the city, reloads it and checks the building is still
there. Everything copied into the game's data is removed at `down`.
"""

from __future__ import annotations

import json
import math
import pathlib
import shutil
import time

from .client import HarnessError
from .session import Session, sha256

IMPORT_SUFFIXES = ("", "_lod")
MAP_SUFFIXES = ("_d", "_n", "_s", "_a", "_c", "_i")


def import_set(src: pathlib.Path, name: str) -> list[pathlib.Path]:
    """The files the game's importer reads for mesh `name`: the FBX, its LOD and their maps."""
    files = []
    for lod in IMPORT_SUFFIXES:
        fbx = src / f"{name}{lod}.fbx"
        if fbx.exists():
            files.append(fbx)
        for m in MAP_SUFFIXES:
            png = src / f"{name}{lod}{m}.png"
            if png.exists():
                files.append(png)
    if not (src / f"{name}.fbx").exists():
        raise HarnessError(f"no {name}.fbx in {src}")
    return files


class Driver:
    def __init__(self, session: Session, out: pathlib.Path, log=print):
        self.s = session
        self.c = session.client
        self.out = out
        self.log = log
        self.shots: list[dict] = []
        self.timeline = open(out / "timeline.jsonl", "a")

    def record(self, kind: str, data: dict):
        self.timeline.write(json.dumps({"kind": kind, "wall": time.time(), **data}, default=str) + "\n")
        self.timeline.flush()

    def job(self, reply: dict, timeout: float, what: str) -> dict:
        """Poll the mod's job until it ends; raise with its log if it failed."""
        deadline = time.monotonic() + timeout
        last_step = None
        while time.monotonic() < deadline:
            self.s.alive()
            st = self.c.call("job")
            if st.get("job") != reply.get("job"):
                raise HarnessError(f"{what}: expected job {reply.get('job')}, mod reports {st.get('job')}")
            if st["step"] != last_step:
                self.log(f"{what}: {st['step']}")
                last_step = st["step"]
            if st["state"] == "done":
                self.record("job", st)
                return st["result"]
            if st["state"] == "failed":
                self.record("job", st)
                raise HarnessError(f"{what} failed: {st['error']}")
            time.sleep(1)
        raise HarnessError(f"{what}: no result after {timeout:.0f} s")

    def wait_level(self, key: str, timeout: float, what: str) -> dict:
        return self.c.wait(lambda st: st.get(key) and not st.get("loading"), timeout, what, alive=self.s.alive)

    def shot(self, label: str, ui: bool = False, settle: float = 4) -> str:
        if not ui:
            self.c.call("ui", visible=False)
        try:
            time.sleep(settle)
            staged = self.s.stage / "shots" / f"{label}.png"
            self.c.call("screenshot", path=str(staged))
            for _ in range(60):
                if staged.exists() and staged.stat().st_size > 0:
                    break
                time.sleep(0.5)
            else:
                raise HarnessError(f"screenshot {staged.name} was not written")
            time.sleep(0.5)
        finally:
            if not ui:
                self.c.call("ui", visible=True)
        self.shots.append({"label": label, "file": f"shots/{staged.name}"})
        self.record("screenshot", self.shots[-1])
        return staged.name

    # -- build -------------------------------------------------------------

    def build(
        self,
        src: pathlib.Path,
        name: str,
        template: str,
        cells: tuple[int, int] | None,
        scale: float,
        expect_size: list[float] | None,
        asset_name: str,
        save_name: str,
        theme: str,
        load_timeout: float,
    ) -> dict:
        cfg = self.s.cfg
        assets_dir = cfg.data_dir / "Addons" / "Assets"
        crp = assets_dir / f"{save_name}.crp"
        if crp.exists():
            raise HarnessError(f"{crp} already exists; it isn't the harness's to replace (pick another --save-name)")
        files = [self.s.install_file(f, cfg.data_dir / "Addons" / "Import") for f in import_set(src, name)]
        self.record("import_set", {"files": [f.name for f in files]})
        menu = self.s.launch(["--noWorkshop"])
        self.log(f"opening the Asset Editor ({theme})")
        self.c.call("asset_editor", theme=theme)
        self.wait_level("in_asset_editor", load_timeout, "the Asset Editor to load")
        self.s.track(crp)  # the job writes it; it leaves the game's data at `down`
        templates = self.c.call("templates", service="Residential", sub_service="ResidentialLow", limit=200)[
            "templates"
        ]
        self.record("templates", {"templates": templates})
        if template == "auto":
            # Low-density residential, level 1, on the same lot if one exists: a growable house.
            fits = [t for t in templates if t["level"] == 1 and (not cells or t["cells"] == list(cells))]
            fits = fits or [t for t in templates if t["level"] == 1]
            if not fits:
                raise HarnessError("no low-density residential level-1 template in this game")
            template = sorted(fits, key=lambda t: t["name"])[0]["name"]
            self.log(f"template: {template}")
        args = {"name": name, "template": template, "scale": scale, "asset_name": asset_name, "save_name": save_name}
        if cells:
            args["cells"] = list(cells)
        if expect_size:
            args["expect_size"] = expect_size
        result = self.job(self.c.call("asset_build", **args), 900, "asset_build")
        self.c.call("camera", position=[0, 0], size=40, yaw=200, pitch=25)
        self.shot("editor", ui=True)
        self.c.call("camera", release=True)
        written = pathlib.Path(result["crp"])
        if written.resolve() != crp.resolve():
            raise HarnessError(f"the game saved to {written}, not {crp}")
        shutil.copy2(crp, self.out / crp.name)
        status = self.c.call("status")
        return {
            "menu_status": {k: menu.get(k) for k in ("gpu", "screen", "unity", "plugins", "enabled_mod_count")},
            "templates_seen": len(templates),
            "build": result,
            "crp": crp.name,
            "crp_sha256": sha256(self.out / crp.name),
            "errors": status.get("errors"),
            "error_count": status.get("error_count"),
            "shots": self.shots,
        }

    # -- check -------------------------------------------------------------

    def pick_spot(self, centre: tuple[float, float], radius: float) -> tuple[float, float, dict]:
        """A dry, gentle spot near centre: least relief across the lot among a grid of candidates."""
        cands = []
        step = radius / 4
        for i in range(-4, 5):
            for j in range(-4, 5):
                cands.append((centre[0] + i * step, centre[1] + j * step))
        offs = [(0, 0), (-12, 0), (12, 0), (0, -12), (0, 12)]
        pts = [[x + dx, z + dz] for x, z in cands for dx, dz in offs]
        samples = self.c.call("water", points=pts)["samples"]
        best = None
        for k, (x, z) in enumerate(cands):
            s = samples[k * 5 : k * 5 + 5]
            if any(p["wet"] for p in s):
                continue
            relief = max(p["terrain"] for p in s) - min(p["terrain"] for p in s)
            score = relief + math.hypot(x - centre[0], z - centre[1]) / 1000
            if best is None or score < best[0]:
                best = (score, x, z, {"relief_m": relief, "terrain_m": s[0]["terrain"]})
        if best is None:
            raise HarnessError(f"no dry spot within {radius:.0f} m of {centre}; pass --at")
        return best[1], best[2], best[3]

    def views(self, label: str, x: float, z: float, y: float, far: float, yaw: float):
        """Close, distant (past the LOD switch) and a high view, in daylight."""
        for name, size, pitch in (("close", 45, 25), ("distant", far, 40), ("high", 120, 65)):
            self.c.call("camera", position=[x, y + 3, z], size=size, yaw=yaw, pitch=pitch)
            self.shot(f"{label}-{name}")

    def check(
        self,
        crp: pathlib.Path,
        map_crp: pathlib.Path,
        at: tuple[float, float] | None,
        angle: float,
        load_timeout: float,
    ) -> dict:
        cfg = self.s.cfg
        installed_crp = self.s.install_file(crp, cfg.data_dir / "Addons" / "Assets")
        installed_map = self.s.install_map(map_crp)
        menu = self.s.launch(["--noWorkshop"])
        assets = self.c.call("custom_assets", contains=crp.stem)
        self.record("custom_assets", assets)
        ours = [b for b in assets["buildings"] if b["name"].startswith(crp.stem + ".")]
        if len(ours) != 1:
            raise HarnessError(f"the game loaded {len(ours)} buildings from {crp.name}: {[b['name'] for b in ours]}")
        info = ours[0]
        self.log(f"loaded {info['name']}: {info.get('mesh', {}).get('triangles')} triangles, LOD {info.get('lod')}")
        self.c.call("new_game", path=str(installed_map))
        status = self.wait_level("in_game", load_timeout, "the city to load")
        self.c.call("run", paused=True)
        if at is None:
            x, z, spot = self.pick_spot((0.0, 0.0), 1200)
        else:
            (x, z), spot = at, {}
        placed = self.job(self.c.call("place_building", name=info["name"], position=[x, z], angle=angle), 60, "place")
        bid = placed["id"]
        y = placed["position"][1]
        far = max(400.0, float(placed["lod_distance"][1]) * 1.4)
        self.log(f"placed building {bid} at ({x:.0f}, {z:.0f}); LOD from {placed['lod_distance']} m")
        # The camera yaw that looks at the building's front: its front faces +Z rotated by the angle.
        yaw = 180 + angle
        self.c.call("time_of_day", hour=12)
        self.views("day", x, z, y, far, yaw)
        self.c.call("time_of_day", hour=22)
        self.c.call("camera", position=[x, y + 3, z], size=45, yaw=yaw, pitch=25)
        self.shot("night-close", settle=6)
        self.c.call("camera", position=[x, y + 3, z], size=far, yaw=yaw, pitch=40)
        self.shot("night-distant", settle=6)
        self.c.call("time_of_day", hour=12)

        save = f"cs1-harness-{crp.stem}-{time.strftime('%Y%m%d-%H%M%S')}"
        saved = self.job(self.c.call("save_game", name=save), 300, "save_game")
        self.s.track(pathlib.Path(saved["path"]))
        self.log(f"saved {saved['path']} ({saved['bytes']} bytes); reloading")
        self.c.call("load_game", name=save)
        time.sleep(5)
        self.wait_level("in_game", load_timeout, "the saved city to reload")
        self.c.call("run", paused=True)
        after = self.c.call("building", id=bid)
        if not after.get("exists") or after.get("name") != info["name"]:
            raise HarnessError(f"after reload, building {bid} is {after}")
        self.c.call("time_of_day", hour=12)
        self.c.call("camera", position=[x, y + 3, z], size=45, yaw=yaw, pitch=25)
        self.shot("reloaded-close")
        final = self.c.call("status")
        self.c.call("camera", release=True)
        return {
            "menu_status": {k: menu.get(k) for k in ("gpu", "screen", "unity", "plugins", "enabled_mod_count")},
            "asset": info,
            "packages": [
                p
                for p in assets["packages"]
                if p["path"] and pathlib.Path(p["path"]).resolve() == installed_crp.resolve()
            ],
            "map": installed_map.name,
            "city_frame": status.get("frame"),
            "spot": {"x": x, "z": z, **spot},
            "placed": placed,
            "after_reload": after,
            "save": saved,
            "shots": self.shots,
            "error_count": final.get("error_count"),
            "errors": final.get("errors"),
        }
