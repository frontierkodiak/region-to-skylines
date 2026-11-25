"""Foreground, FIFO-owned tree import and fresh-city comparison on blade only."""

import argparse
import hashlib
import json
import pathlib
import shutil
import sys
import time

from comparisons import load_plan, resolve_plan

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "cs1-harness"))

from cs1_harness.assets import Driver
from cs1_harness.cli import slot
from cs1_harness.config import Config


def write(path, data):
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("inputs", type=pathlib.Path)
    p.add_argument("out", type=pathlib.Path)
    p.add_argument("--template", default="Tree2")
    p.add_argument(
        "--map",
        default="Grand River",
        help="exact installed map name; winter map for snow witnesses",
    )
    p.add_argument(
        "--skip-frames",
        action="store_true",
        help="specimen screening before a winner is selected",
    )
    p.add_argument(
        "--comparisons", type=pathlib.Path, help="JSON specimen reference plan"
    )
    p.add_argument(
        "--reference-asset",
        type=pathlib.Path,
        action="append",
        default=[],
        help="local reference CRP to stage for this city only; never redistributed",
    )
    p.add_argument("--build-only", action="store_true")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--wait-minutes", type=float, default=60)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--frames", type=int, default=120)
    p.add_argument(
        "--candidate",
        action="append",
        help="limit timing to this package stem; repeatable",
    )
    p.add_argument("--skip-specimens", action="store_true")
    a = p.parse_args()
    if a.repeats < 1 or not 60 <= a.frames <= 3000:
        p.error("repeats must be positive; frames must be 60..3000")
    names = [
        json.loads(r.read_text())["name"]
        for r in sorted(a.inputs.glob("*/receipt.json"))
    ]
    if not names or len(set(names)) != len(names):
        p.error("Expected a nonempty, unique input package set")
    plan = load_plan(names, a.template, a.comparisons)
    references = []
    for reference in a.reference_asset:
        if reference.suffix.lower() != ".crp" or not reference.is_file():
            p.error(f"Reference asset must be an existing CRP: {reference}")
        references.append(
            {
                "file": reference.name,
                "sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
            }
        )
    if len({r["file"] for r in references}) != len(references) or any(
        r["file"] in {name + ".crp" for name in names} for r in references
    ):
        p.error(
            "Reference package filenames must be unique and distinct from candidates"
        )
    cfg = Config.for_host("blade")
    a.out.mkdir(parents=True, exist_ok=True)
    if not a.check_only:
        stage = cfg.harness_home / "runs" / ("PL1328-editor-" + a.out.name)
        started = time.monotonic()
        try:
            with slot(
                cfg,
                stage,
                a.wait_minutes,
                {"issue": "PL-1328", "label": "tree import batch"},
            ) as session:
                first = True
                for receipt in sorted(a.inputs.glob("*/receipt.json")):
                    r = json.loads(receipt.read_text())
                    name = r["name"]
                    out = a.out / ("build-" + name)
                    if (out / (name + ".crp")).exists():
                        continue
                    out.mkdir(exist_ok=False)
                    d = Driver(session, out, log=lambda t: print(t, flush=True))
                    asset_started = time.monotonic()
                    result = d.build(
                        receipt.parent,
                        name,
                        a.template,
                        None,
                        100,
                        [r["size_xyz_z_up_m"][i] for i in (0, 2, 1)],
                        name,
                        name,
                        "Sunny",
                        300,
                        kind="tree",
                        launch=first,
                    )
                    first = False
                    write(out / "result.json", result)
                    write(
                        out / "timing.json",
                        {"wall_seconds": time.monotonic() - asset_started},
                    )
        finally:
            if stage.exists():
                shutil.copytree(stage, a.out / "editor-session", dirs_exist_ok=True)
            write(
                a.out / "editor-timing.json",
                {"batch_wall_seconds": time.monotonic() - started},
            )
    if a.build_only:
        return
    out = a.out / "fresh-city"
    out.mkdir(exist_ok=False)
    stage = cfg.harness_home / "runs" / ("PL1328-city-" + a.out.name)
    try:
        with slot(
            cfg, stage, a.wait_minutes, {"issue": "PL-1328", "label": "fresh tree city"}
        ) as s:
            packages = sorted(a.out.glob("build-*/*.crp"))
            expected = {
                json.loads(p.read_text())["name"]
                for p in a.inputs.glob("*/receipt.json")
            }
            if not expected or {p.stem for p in packages} != expected:
                raise RuntimeError(
                    "Fresh-city check requires the complete, exact input package set"
                )
            for crp in packages:
                s.install_file(crp, cfg.data_dir / "Addons" / "Assets")
            for reference, record in zip(a.reference_asset, references):
                installed = s.install_file(
                    reference, cfg.data_dir / "Addons" / "Assets"
                )
                if (
                    hashlib.sha256(installed.read_bytes()).hexdigest()
                    != record["sha256"]
                ):
                    raise RuntimeError(
                        f"Reference package changed while queued: {reference.name}"
                    )
            write(out / "reference-packages.json", references)
            s.launch(["--noWorkshop"])
            c = s.client
            maps = c.call("maps")["maps"]
            write(out / "maps.json", maps)
            entry = next(m for m in maps if m["name"] == a.map)
            write(out / "map.json", entry)
            c.call("new_game", path=entry["path"])
            d = Driver(s, out, log=lambda t: print(t, flush=True))
            d.wait_level("in_game", 600, "fresh city")
            c.call("run", paused=True)
            c.call("time_of_day", hour=12)
            catalog = c.call("vegetation_catalog")
            write(out / "catalog.json", catalog)
            resolved = resolve_plan(plan, catalog["trees"])
            write(out / "comparison-plan.json", resolved)
            ours = [t for t in catalog["trees"] if t["name"].split(".")[0] in expected]
            if {t["name"].split(".")[0] for t in ours} != expected:
                raise RuntimeError(
                    "The complete imported tree set did not load in the fresh city"
                )
            candidates = (
                ours
                if not a.candidate
                else [t for t in ours if t["name"].split(".")[0] in a.candidate]
            )
            if a.candidate and {t["name"].split(".")[0] for t in candidates} != set(
                a.candidate
            ):
                raise RuntimeError("A requested timing candidate did not load")
            control = a.template
            write(
                out / "control.json",
                next(t for t in catalog["trees"] if t["name"] == control),
            )
            x, z = catalog["forest_patch"]
            # Preserve the same 139k stock instance positions for the cost comparison.
            frames = []
            for size in () if a.skip_frames else (180, 500):
                c.call("camera", position=[x, z], size=size, pitch=40, yaw=0)
                c.call("ui", visible=False)
                for t in candidates:
                    for rep in range(a.repeats):
                        for arm, target in zip(
                            ("a1", "b", "a2"), (control, t["name"], control)
                        ):
                            c.call("ui", visible=False)
                            count = d.job(
                                c.call("vegetation_retarget", name=target),
                                90,
                                "retarget",
                            )
                            sample = d.job(
                                c.call("vegetation_frames", frames=a.frames),
                                90,
                                "frames",
                            )
                            frames.append(
                                {
                                    "size": size,
                                    "candidate": t["name"],
                                    "target": target,
                                    "repeat": rep,
                                    "count": count,
                                    "timing_ui_visible": False,
                                    **sample,
                                }
                            )
                            # Outside the timed window; the next arm gets its own warmup.
                            d.shot(
                                f"forest-{t['name'].split('.')[0]}-{size}-{rep}-{arm}",
                                settle=0.5,
                            )
                    write(out / "frames.json", frames)
            c.call("ui", visible=True)
            specimens = []
            for t in [] if a.skip_specimens else ours:
                comparison = resolved[t["name"].split(".")[0]]
                placed = d.job(
                    c.call(
                        "vegetation_pair",
                        left=t["name"],
                        right=comparison["prefab"],
                        x=0,
                        z=300,
                        gap=25,
                    ),
                    60,
                    "pair",
                )
                placed["comparison_basis"] = comparison["basis"]
                placed["comparison_evidence"] = comparison["evidence"]
                specimens.append(placed)
                y = max(s["position"][1] for s in placed["specimens"])
                for label, size in (
                    ("close", 52),
                    ("gameplay", 140),
                    ("billboard", 550),
                ):
                    c.call(
                        "camera",
                        position=[0, y + 8, 300],
                        size=size,
                        pitch=20 if label == "close" else 40,
                        yaw=0,
                    )
                    d.shot(t["name"].split(".")[0] + "-" + label)
            write(out / "specimens.json", specimens)
            if not a.skip_specimens:
                remaining = c.call("vegetation_catalog")["instances"]
                write(out / "post-specimen-count.json", {"instances": remaining})
                if remaining != 2:
                    raise RuntimeError(
                        f"Expected only the specimen pair, got {remaining} trees"
                    )
            write(out / "status.json", c.call("status"))
            c.call("camera", release=True)
    finally:
        if stage.exists():
            shutil.copytree(stage, out / "session", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
