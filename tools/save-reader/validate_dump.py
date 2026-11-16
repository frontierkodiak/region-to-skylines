"""Compare the offline save reader with the game's own view of the same save.

    uv run python validate_dump.py SAVE.crp RUN_DIR [--json OUT.json]

RUN_DIR is a `cs1-harness dump-save` output directory (city-dump.json, prefabs.json).
Items are matched by buffer id. The harness runs without Workshop content or mods, so
the game drops items whose prefab it doesn't have; those are counted as explained, as are
nodes left with no segment once their segments were dropped. Everything else is a
mismatch. The check passes when, per category, unexplained mismatches stay within
`--max-unexplained` (a fraction) and position errors within `--max-position-error` metres.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get("CS1SAVE_PATH", str(HERE)))
from cs1save.save import read_save  # noqa: E402

TREE_SCALE = np.float32(0.26367188)


def columns(table):
    return {k: np.asarray(v) if k not in ("prefab",) else list(v) for k, v in table.items()}


def summarize(name, save_ids, game_ids, explained_ids, extra=None):
    save_ids, game_ids = set(map(int, save_ids)), set(map(int, game_ids))
    only_save = save_ids - game_ids
    explained = only_save & set(map(int, explained_ids))
    out = {
        "save": len(save_ids),
        "game": len(game_ids),
        "both": len(save_ids & game_ids),
        "only_in_save": len(only_save),
        "only_in_save_explained": len(explained),
        "only_in_save_unexplained": sorted(only_save - explained)[:50],
        "only_in_game": sorted(game_ids - save_ids)[:50],
        "unexplained": len(only_save - explained) + len(game_ids - save_ids),
    }
    out.update(extra or {})
    return out


def agree(a, b):
    a, b = list(a), list(b)
    return {"compared": len(a), "agree": sum(1 for x, y in zip(a, b) if x == y)}


def compare(save, dump, prefabs):
    loaded = {
        "nets": {p["name"] for p in prefabs["nets"]},
        "buildings": {p["name"] for p in prefabs["buildings"]},
        "trees": {p["name"] for p in prefabs["trees"]},
    }
    report = {"save_frame": save.simulation["frame_index"], "game_frame": dump["frame"], "paused": dump["paused"]}
    net = save.data["NetManager"]

    # Segments
    gs = columns(dump["segments"])
    s_ids = net["segment_ids"]
    s_prefab = dict(zip(map(int, s_ids), net["segment_prefab"]))
    dropped_segments = {i for i, p in s_prefab.items() if p not in loaded["nets"]}
    g_index = {int(i): k for k, i in enumerate(gs["id"])}
    common = [int(i) for i in s_ids if int(i) in g_index]
    pos = {int(i): k for k, i in enumerate(s_ids)}
    report["segments"] = summarize(
        "segments",
        s_ids,
        gs["id"],
        dropped_segments,
        {
            "prefab": agree((s_prefab[i] for i in common), (gs["prefab"][g_index[i]] for i in common)),
            "start_node": agree(
                (int(net["segment_start_node"][pos[i]]) for i in common),
                (int(gs["start_node"][g_index[i]]) for i in common),
            ),
            "end_node": agree(
                (int(net["segment_end_node"][pos[i]]) for i in common),
                (int(gs["end_node"][g_index[i]]) for i in common),
            ),
            "flags": agree(
                (int(net["segment_flags"][pos[i]]) for i in common), (int(gs["flags"][g_index[i]]) for i in common)
            ),
            "dropped_prefabs": sorted({s_prefab[i] for i in dropped_segments}),
        },
    )

    # Nodes: dropped with a missing prefab, or orphaned once their segments were released.
    gn = columns(dump["nodes"])
    n_ids = net["node_ids"]
    n_prefab = dict(zip(map(int, n_ids), net["node_prefab"]))
    kept_segments = set(map(int, s_ids)) - dropped_segments
    orphaned = set()
    for k, i in enumerate(map(int, n_ids)):
        segs = [x for x in net["node_segments"][k] if x]
        if segs and not any(x in kept_segments for x in segs):
            orphaned.add(i)
    dropped_nodes = {i for i, p in n_prefab.items() if p not in loaded["nets"]} | orphaned
    g_index = {int(i): k for k, i in enumerate(gn["id"])}
    pos = {int(i): k for k, i in enumerate(n_ids)}
    common = [int(i) for i in n_ids if int(i) in g_index]
    if common:
        a = net["node_position"][[pos[i] for i in common]].astype(np.float64)
        b = np.stack([gn[c][[g_index[i] for i in common]] for c in ("x", "y", "z")], axis=1).astype(np.float64)
        err = float(np.abs(a - b).max())
    else:
        err = None
    report["nodes"] = summarize(
        "nodes",
        n_ids,
        gn["id"],
        dropped_nodes,
        {
            "position_max_abs_error_m": err,
            "prefab": agree((n_prefab[i] for i in common), (gn["prefab"][g_index[i]] for i in common)),
            "flags": agree(
                (int(net["node_flags"][pos[i]]) for i in common), (int(gn["flags"][g_index[i]]) for i in common)
            ),
        },
    )

    # Buildings
    bd = save.data["BuildingManager"]
    gb = columns(dump["buildings"])
    b_ids = bd["ids"]
    b_prefab = dict(zip(map(int, b_ids), bd["prefab"]))
    dropped_buildings = {i for i, p in b_prefab.items() if p not in loaded["buildings"]}
    g_index = {int(i): k for k, i in enumerate(gb["id"])}
    pos = {int(i): k for k, i in enumerate(b_ids)}
    common = [int(i) for i in b_ids if int(i) in g_index]
    extra = {"prefab": agree((b_prefab[i] for i in common), (gb["prefab"][g_index[i]] for i in common))}
    if common:
        a = bd["position"][[pos[i] for i in common]].astype(np.float64)
        b = np.stack([gb[c][[g_index[i] for i in common]] for c in ("x", "y", "z")], axis=1).astype(np.float64)
        extra["position_max_abs_error_m"] = float(np.abs(a - b).max())
        da = np.abs(
            bd["angle"][[pos[i] for i in common]].astype(np.float64) - gb["angle"][[g_index[i] for i in common]]
        )
        extra["angle_max_abs_error_rad"] = float(np.minimum(da, 2 * np.pi - da).max())
    for field in ("level", "width", "length"):
        if field in bd:
            extra[field] = agree((int(bd[field][pos[i]]) for i in common), (int(gb[field][g_index[i]]) for i in common))
    extra["dropped_prefabs"] = sorted({b_prefab[i] for i in dropped_buildings})
    report["buildings"] = summarize("buildings", b_ids, gb["id"], dropped_buildings, extra)

    # Zone blocks
    zd = save.data["ZoneManager"]
    gz = dump["zone_blocks"]
    z_ids = zd["block_ids"]
    g_index = {int(i): k for k, i in enumerate(gz["id"])}
    pos = {int(i): k for k, i in enumerate(z_ids)}
    common = [int(i) for i in z_ids if int(i) in g_index]
    blocks = zd["blocks"]
    extra = {}
    for field in ("valid", "zone1", "zone2"):
        extra[field] = agree((int(blocks[field][pos[i]]) for i in common), (int(gz[field][g_index[i]]) for i in common))
    if common:
        a = blocks["position"][[pos[i] for i in common]].astype(np.float64)
        b = np.array([[gz[c][g_index[i]] for c in ("x", "y", "z")] for i in common], dtype=np.float64)
        extra["position_max_abs_error_m"] = float(np.abs(a - b).max())
    report["zone_blocks"] = summarize("zone_blocks", z_ids, gz["id"], set(), extra)

    # Trees: compare the stored position shorts after the game's scale.
    td = save.data["TreeManager"]
    gt = columns(dump["trees"])
    t_ids = td["ids"]
    t_prefab = [td["prefab_names"][i] for i in td["prefab_index"]]
    dropped_trees = {int(i) for i, p in zip(t_ids, t_prefab) if p not in loaded["trees"]}
    g_index = {int(i): k for k, i in enumerate(gt["id"])}
    pos = {int(i): k for k, i in enumerate(t_ids)}
    common = [int(i) for i in t_ids if int(i) in g_index]
    extra = {"prefab": agree((t_prefab[pos[i]] for i in common), (gt["prefab"][g_index[i]] for i in common))}
    if common:
        gi = np.array([g_index[i] for i in common])
        si = np.array([pos[i] for i in common])
        gx = gt["pos_x"][gi].astype(np.float32) * TREE_SCALE
        gz_ = gt["pos_z"][gi].astype(np.float32) * TREE_SCALE
        extra["position_max_abs_error_m"] = float(max(np.abs(td["x"][si] - gx).max(), np.abs(td["z"][si] - gz_).max()))
    report["trees"] = summarize("trees", t_ids, gt["id"], dropped_trees, extra)

    meta_pop = save.metadata.get("population")
    report["population"] = {
        "save_metadata": meta_pop,
        "game": dump["population"],
        "agree": meta_pop is not None and int(str(meta_pop).replace(",", "")) == int(dump["population"]),
    }
    report["cash"] = {"save_metadata": save.metadata.get("cash"), "game_last_cash": dump["cash"]}
    return report


def verdict(report, max_unexplained, max_position_error):
    failures = []
    for cat in ("nodes", "segments", "buildings", "zone_blocks", "trees"):
        r = report[cat]
        if r["unexplained"] > max_unexplained * max(r["save"], 1):
            failures.append(f"{cat}: {r['unexplained']} unexplained of {r['save']}")
        err = r.get("position_max_abs_error_m")
        if err is not None and err > max_position_error:
            failures.append(f"{cat}: position error {err:.4f} m")
        for field in ("prefab", "start_node", "end_node", "valid", "zone1", "zone2", "level", "width", "length"):
            if field in r and r[field]["compared"] and r[field]["agree"] < (1 - max_unexplained) * r[field]["compared"]:
                failures.append(f"{cat}.{field}: {r[field]['agree']}/{r[field]['compared']} agree")
    return failures


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("save", type=Path)
    p.add_argument("run", type=Path, help="dump-save output directory")
    p.add_argument("--json", type=Path, help="write the full report here")
    p.add_argument("--max-unexplained", type=float, default=0.001)
    p.add_argument("--max-position-error", type=float, default=0.01)
    a = p.parse_args()
    save = read_save(a.save)
    dump = json.loads((a.run / "city-dump.json").read_text())
    prefabs = json.loads((a.run / "prefabs.json").read_text())
    report = compare(save, dump, prefabs)
    report["failures"] = verdict(report, a.max_unexplained, a.max_position_error)
    report["pass"] = not report["failures"]
    if a.json:
        a.json.write_text(json.dumps(report, indent=2, default=str))
    for cat in ("nodes", "segments", "buildings", "zone_blocks", "trees"):
        r = report[cat]
        print(
            f"{cat:12} save {r['save']:7} game {r['game']:7} both {r['both']:7} "
            f"dropped(explained) {r['only_in_save_explained']:5} unexplained {r['unexplained']:4} "
            f"pos err {r.get('position_max_abs_error_m')}"
        )
    print("population", report["population"], "frames", report["save_frame"], report["game_frame"])
    print("PASS" if report["pass"] else "FAIL: " + "; ".join(report["failures"]))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
