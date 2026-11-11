"""Supplement the fixed native comparison with explicitly forced native LOD views.

No assets are edited/saved. Runtime distances are restored after each capture.
Normal comparisons and judge images remain the original matched-city captures.
"""

import argparse
import hashlib
from pathlib import Path
import subprocess

from cs1_harness.cli import _session_tool
from cs1_harness.config import Config


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("game", type=Path)
    p.add_argument("map", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument(
        "--vanilla-only", action="store_true", help="same map and completed fixture, no candidate CRPs installed"
    )
    a = p.parse_args()
    a.wait_minutes, a.retry_minutes, a.max_attempts, a.issue = 15, 0, 1, "PL-881"
    cfg = Config.for_host()
    names = [f"{arm}-{target}" for target in ("bungalow", "storefront", "apartment") for arm in "ABC"]
    if a.vanilla_only:
        names = []
    plan = {
        "source": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "script_sha256": digest(Path(__file__)),
        "mod_sha256": digest(cfg.build_dir / "Cs1Harness.dll"),
        "map_sha256": digest(a.map),
        "crps": {name: digest(a.game / "build" / name / f"{name}.crp") for name in names},
        "vanilla_only": a.vanilla_only,
        "inspection_only": "LOD distances forced to zero in a fresh paused city; never a gameplay-distance or performance measurement",
    }

    def body(d):
        s, c = d.s, d.c
        for name in names:
            s.install_file(a.game / "build" / name / f"{name}.crp", cfg.data_dir / "Addons" / "Assets")
        map_path = s.install_map(a.map)
        menu = s.launch(["--noWorkshop"])
        maps = c.call("maps")["maps"]
        entry = next(m for m in maps if m["path"] and Path(m["path"]).resolve() == map_path.resolve())
        c.call("new_game", path=entry["path"])
        d.wait_level("in_game", 600, "probe city")
        c.call("run", paused=True)
        placed = {}
        for index, name in enumerate(names):
            x, z = (index % 3 - 1) * 120, 300 + (index // 3) * 120
            wet = c.call("water", points=[[x, z]])["samples"][0]
            if wet["wet"]:
                raise RuntimeError(f"probe grid point is wet: {name}, {wet}")
            b = d.job(c.call("place_building", name=name + "." + name + "_Data", position=[x, z]), 60, name)
            placed[name] = b
            y = b["position"][1]
            c.call("time_of_day", hour=12)
            c.call("camera", position=[x, y + 3, z], size=45, yaw=180, pitch=25)
            d.shot(name + "-main")
            enabled = c.call("asset_lod_preview", name=b["name"], enabled=True)
            d.record("forced_lod", enabled)
            try:
                d.shot(name + "-forced-lod")
                c.call("time_of_day", hour=22)
                d.shot(name + "-forced-lod-night", settle=6)
            finally:
                d.record("restore_lod", c.call("asset_lod_preview", name=b["name"], enabled=False))
        vanilla = d.job(c.call("place_building", name="L1 2x3 Detached03", position=[0, 180]), 60, "vanilla control")
        x, y, z = vanilla["position"]
        c.call("camera", position=[x, y + 3, z], size=45, yaw=180, pitch=25)
        for hour in (12, 22, 1, 4):
            c.call("time_of_day", hour=hour)
            d.shot(f"vanilla-hour-{hour}", settle=6)
        c.call("camera", release=True)
        status = c.call("status")
        return {
            "plan": plan,
            "menu_status": menu,
            "placed": placed,
            "vanilla": vanilla,
            "shots": d.shots,
            "errors": status.get("errors"),
            "custom_assets": c.call("custom_assets"),
        }

    raise SystemExit(_session_tool(cfg, a, "render-probes", body))


if __name__ == "__main__":
    main()
