"""Check the resource stage against frozen inputs and the native rules.

For each case in fixtures/resources.json: plan and write the map from the
frozen prepared region, land cover and evidence, compare its SHA-256, replay
the frozen plan (plan.npz) through the encoders alone and compare again, then
decode the package with the independent survey decoder and check:

- both rebuilt sections end exactly where the template's own tails begin;
- forest equals min(60 x trees per cell, 255) and the tree byte matches it;
- no cell has both ore and oil, or both fertility and forest;
- every tree uses an original-release prefab its map theme loads, and is
  saved fully grown;
- the New Game amounts equal the 25-tile final sums, and the tile sums equal
  the cell grids binned the way the simulation bins them.

It does not run CS1. `--freeze` rewrites the expected checksums (an authoring
step; review the maps in game first).

    uv run python verify_resources.py [--freeze]
"""

import argparse
import hashlib
import json
import struct
import sys
import tempfile
from pathlib import Path

import numpy as np

import resources as R
from paint import paint
from template import decode_array

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "survey"))
import measure_maps as M  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def section_end(data, name, arrays):
    """Walk a section with our own decoder; return the offset after its body."""
    o = M.section(data, name)
    if name == "NaturalResourceManager":
        forest = None
        for i in range(11):
            n = R.RES * R.RES
            if i == 4:
                n = int(np.count_nonzero(forest))
            elif i == 5:
                n = R.RES * R.RES - int(np.count_nonzero(forest))
            values, o = decode_array(data, n, o, 1)
            if i == 3:
                forest = values
        _, o = decode_array(data, 810, o, 4)
        return o + 8 * 4 + 2
    flags, o = decode_array(data, R.TREE_SLOTS, o, 2)
    n = int(np.count_nonzero(flags))
    _, o = decode_array(data, n, o, 2)
    count = struct.unpack_from(">H", data, o)[0]
    o += 2
    for _ in range(count):
        _, o = M.read_unique_string(data, o)
    _, o = decode_array(data, n, o, 2)
    _, o = decode_array(data, n, o, 2)
    return o + 3 + 5 * int.from_bytes(data[o : o + 3], "big")


def check(crp):
    pkg, assets = M.read_any(Path(crp).read_bytes())
    data = next(a["payload"] for a in assets if a["kind"] == 52)
    meta = M.parse_metadata(next(a["payload"] for a in assets if a["kind"] == 100))
    v = M.data_version(data)
    g, area = M.parse_resources(data, v)
    trees = M.parse_trees(data, v)
    template = (ROOT / "templates/native-corridors.crp").read_bytes()
    _, tassets = M.read_any(template)
    tdata = next(a["payload"] for a in tassets if a["kind"] == 52)
    problems = []
    for name in ["NaturalResourceManager", "TreeManager"]:
        tail = tdata[section_end(tdata, name, None) :][:64]
        if data[section_end(data, name, None) :][:64] != tail:
            problems.append(f"{name} body does not end where the template tail begins")
    c = np.clip((trees["x"] / R.CELL + 256).astype(int), 0, 511)
    r = np.clip((trees["z"] / R.CELL + 256).astype(int), 0, 511)
    counts = np.bincount(r * 512 + c, minlength=512 * 512).reshape(512, 512)
    expected = np.minimum(60 * counts, 255)
    match = float((expected == g["forest"]).mean())
    if match < 0.995:
        problems.append(f"forest matches the tree formula on only {match:.4f} of cells")
    if np.any(g["tree"] != g["forest"]):
        problems.append("tree byte differs from forest byte for grown trees")
    if np.any((g["ore"] > 0) & (g["oil"] > 0)):
        problems.append("ore and oil share a cell")
    if np.any((g["fertility"] > 0) & (g["forest"] > 0)):
        problems.append("fertility on a forest cell")
    names = [trees["names"][i] for i in np.unique(trees["prefab"])] if len(trees["prefab"]) else []
    theme = meta["environment"]
    allowed = {n for pool in R.THEMES.get(theme, {}).values() for n, _ in pool}
    if set(names) - allowed:
        problems.append(f"tree prefabs the {theme} theme doesn't load: {sorted(set(names) - allowed)}")
    if len(trees["prefab"]) and any(n is None for n in trees["names"]):
        problems.append("tree prefab table has null entries")
    if np.any(trees["flags"] != R.GROWN_TREE):
        problems.append("a tree is not saved as created and fully grown")
    if len(trees["flags"]) > 250_000:
        problems.append("more trees than the Map Editor allows (250,000)")
    tile = (np.arange(512) * 18) >> 10
    for key, field, cells in [
        ("finalOre", "oreAmount", g["ore"]),
        ("finalOil", "oilAmount", g["oil"]),
        ("finalForest", "forestAmount", g["forest"]),
        ("finalFertility", "fertileLandAmount", g["fertility"]),
    ]:
        binned = np.bincount((tile[:, None] * 9 + tile[None, :]).ravel(), weights=cells.ravel(), minlength=81)
        if np.any(binned.reshape(9, 9) != area[key]):
            problems.append(f"{key} tile sums differ from the cell grid")
        if int(area[key][2:7, 2:7].sum()) != meta[field]:
            problems.append(f"{field} is not the 25-tile sum")
    if int(area["finalWater"][2:7, 2:7].sum()) != meta["waterAmount"]:
        problems.append("waterAmount is not the 25-tile sum")
    mx = meta["maxResourceAmount"]
    return problems, {
        "trees": int(len(trees["flags"])),
        "species": {n: int((trees["prefab"] == i).sum()) for i, n in enumerate(trees["names"])},
        "forest_formula_match": round(match, 5),
        "panel_share": {
            k: round(meta[f] / mx, 4)
            for k, f in [("ore", "oreAmount"), ("oil", "oilAmount"), ("forest", "forestAmount"), ("fertile", "fertileLandAmount"), ("water", "waterAmount")]
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    manifest_path = ROOT / "fixtures/resources.json"
    manifest = json.loads(manifest_path.read_text())
    report, failed = [], False
    for case in manifest["cases"]:
        fixture = ROOT / "fixtures" / case["slug"]
        for name, digest in case["inputs_sha256"].items():
            if sha(fixture / name) != digest:
                raise SystemExit(f"{case['slug']}: frozen input {name} changed")
        knobs = R.Knobs(**case["knobs"])
        with tempfile.TemporaryDirectory() as tmp:
            planned, replayed = Path(tmp) / "plan", Path(tmp) / "replay"
            paint(fixture, fixture / "landcover.u8.gz", planned, None, fixture / "evidence.json", knobs, case["map_name"])
            crp = next(planned.glob("*.crp"))
            paint(fixture, None, replayed, knobs=knobs, map_name=case["map_name"], plan=planned / "plan.npz")
            digest, replay_digest = sha(crp), sha(next(replayed.glob("*.crp")))
            problems, facts = check(crp)
            if args.freeze:
                case["expected_crp_sha256"] = digest
            if digest != case["expected_crp_sha256"]:
                problems.append(f"planned map {digest} != expected {case['expected_crp_sha256']}")
            if replay_digest != digest:
                problems.append("replaying plan.npz through the encoders changed the bytes")
        failed |= bool(problems)
        report.append({"slug": case["slug"], "sha256": digest, "problems": problems, **facts})
    if args.freeze:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": report, "in_game_verified": False}, indent=2))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
