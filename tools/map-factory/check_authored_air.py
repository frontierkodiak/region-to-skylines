"""Write plane entries into the three prior missing-air packages and check the editor."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from paint import paint
from plane_entries import ensure_plane_entries
from crp import read_package
import netcodec as nc
from network_writer import section_start, OUTSIDE


def main():
    p = argparse.ArgumentParser()
    p.add_argument("retained", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--editor", action="store_true")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    ledger = json.loads((root / "capabilities.json").read_text())
    slugs = sorted(
        r["square"]
        for r in ledger["connection_agreement"]["editor_rows"]
        if not r["observed"]["air"]
    )
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    # Non-game work first; source selection is all previous air disagreements.
    for slug in slugs:
        source = args.retained / slug
        target = args.output / slug
        shutil.copytree(source, target, dirs_exist_ok=True)
        hydro = json.loads((target / "hydrology.json").read_text())
        geometry = json.loads((target / "geometry.json").read_text())
        original_plan = (target / "plan.npz").read_bytes()
        paint(target, None, target, plan=target / "plan.npz")
        (target / "plan.npz").write_bytes(original_plan)
        crp = target / (hydro["map_id"] + ".crp")
        result = ensure_plane_entries(crp, geometry, target)
        assert result["entries"] == 2
        _, assets = read_package(crp.read_bytes())
        native = next(a["payload"] for a in assets if a["kind"] == 52)
        net = nc.NetSection(native, section_start(native, "NetManager"))
        buildings = nc.BuildingSection(native, section_start(native, "BuildingManager"))
        assert (
            sum(
                "Airplane" in net.prefabs.names[net.node_prefab[i]]
                and bool(int(net.node_flags[i - 1]) & OUTSIDE)
                for i in net.nodes
            )
            == 2
        )
        assert (
            sum(buildings.prefab(i) == "Airplane Connection" for i in buildings.ids)
            == 2
        )
        for name in ["terrain.u16", "water.u16", "plan.npz"]:
            assert (target / name).read_bytes() == (source / name).read_bytes()
        rows.append({"square": slug, "package": str(crp), "written_plane_entries": 2})
        print("written", slug, flush=True)
    (args.output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    if args.editor:
        from cs1_harness.cli import slot, staging
        from cs1_harness.config import Config

        cfg = Config.for_host("blade")
        for row in rows:
            path = Path(row["package"])
            with slot(
                cfg,
                staging(cfg, args.output / (row["square"] + "-session")),
                2,
                {
                    "issue": "PL-1119",
                    "command": "plane-entry-editor-check",
                    "label": row["square"],
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
                client.wait(
                    lambda s: s.get("mode") == "MapEditor"
                    and s.get("loading_complete")
                    and not s.get("loading"),
                    180,
                    "map editor",
                    alive=session.alive,
                )
                client.call("run", paused=True)
                graph = client.call("networks")
                ends = set()
                for segment in graph["segments"]:
                    prefab = (segment.get("prefab") or "").lower()
                    if "airplane" not in prefab and "aircraft" not in prefab:
                        continue
                    for side in ["start", "end"]:
                        if "Outside" in segment.get(side + "_flags", ""):
                            ends.add(segment[side])
                row["editor_plane_entries"] = len(ends)
                assert len(ends) == 2
                print(json.dumps(row), flush=True)
            (args.output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    (args.output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
