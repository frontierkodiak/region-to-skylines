"""Read outside entries in the editor for the fixed nine retained geographic maps."""

import hashlib
import json
from pathlib import Path
import sys
import time

from cs1_harness.cli import slot, staging
from cs1_harness.config import Config


def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg = Config.for_host("blade")
    root = Path.home() / "experiments/PL-1121-outside-oracle"
    cases = sorted((root / "reproduction/maps").glob("*/*.crp"))
    cases += list((root / "boston/maps").glob("*/*.crp"))
    cases.sort(key=lambda p: p.parent.name)
    assert len(cases) == 9
    rows = []
    for path in cases:
        name = path.parent.name
        print("editor", name, flush=True)
        row = dict(
            square=name, observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        try:
            with slot(
                cfg,
                staging(cfg, out / name),
                2,
                {
                    "issue": "PL-1119",
                    "command": "geometry-editor-spotcheck",
                    "label": name,
                },
            ) as session:
                session.live = False
                session.record = False
                installed = session.install_map(path)
                session.launch(["--noWorkshop"])
                client = session.client
                client.call(
                    "template_open",
                    path=str(installed),
                    source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                status = client.wait(
                    lambda s: s.get("mode") == "MapEditor"
                    and s.get("loading_complete")
                    and not s.get("loading"),
                    180,
                    "map editor",
                    alive=session.alive,
                )
                client.call("run", paused=True)
                graph = client.call("networks")
                ends = {k: set() for k in ("road", "rail", "ship", "air")}
                for segment in graph["segments"]:
                    prefab = (segment.get("prefab") or "").lower()
                    kind = (
                        "ship"
                        if "ship" in prefab
                        else "air"
                        if "airplane" in prefab or "aircraft" in prefab
                        else "rail"
                        if "train" in prefab or "rail" in prefab
                        else "road"
                        if "highway" in prefab
                        else None
                    )
                    if kind:
                        for side in ("start", "end"):
                            if "Outside" in segment.get(side + "_flags", ""):
                                ends[kind].add(segment[side])
                row.update(
                    mode=status["mode"],
                    entries={k: len(v) for k, v in ends.items()},
                    observed={k: bool(v) for k, v in ends.items()},
                )
                if name in ("asheville", "boston"):
                    client.call("camera", position=[0, 0], size=11000, pitch=60, yaw=0)
                    client.call("screenshot", path=str(out / (name + "-editor.png")))
        except Exception as error:
            row["error"] = str(error)
        rows.append(row)
        (out / "editor-checks.json").write_text(json.dumps(rows, indent=2) + "\n")
        print(json.dumps(row), flush=True)
        if "error" in row:
            break


if __name__ == "__main__":
    main()
