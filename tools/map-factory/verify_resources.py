"""Check the resource stage against frozen inputs and the native rules.

For each resource-bearing case in fixtures/manifest.json, plan and write the
map from frozen terrain, land cover and evidence, compare its SHA-256, replay
the frozen plan (plan.npz) through the encoders alone and compare again, then
decode the package with the independent survey decoder and check:

- both rebuilt sections end exactly where the template's own tails begin;
- forest equals min(60 x trees per cell, 255) and the tree byte matches it;
- no cell has both ore and oil; invented ore and oil stay out of the start
  tile;
- every tree uses an original-release prefab its map environment loads, and
  is saved fully grown, within the planting budget;
- the New Game amounts equal the 25-tile final sums, and the tile sums equal
  the cell grids binned the way the simulation bins them.

It does not run CS1 or rewrite checksums. Author references with
freeze_fixtures.py after reviewing exact-package native findings.

    uv run python verify_resources.py [--fixtures DIRECTORY]
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


def check(crp, evidence=None):
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
    # Only real deposits may put ore or oil in the start tile.
    tile = (np.arange(512) * 18) >> 10
    start_index = M.parse_start_tile(data, v)[1]
    in_start = (tile[:, None] == start_index // 5 + 2) & (
        tile[None, :] == start_index % 5 + 2
    )
    centres = (np.arange(512) + 0.5) * R.CELL - R.HALF
    near_real = np.zeros((512, 512), bool)
    for e in evidence or []:
        reach = 1500 if e["kind"] == "well" else 700  # well fields are a density
        near_real |= (
            np.hypot(centres[None, :] - e["x"], centres[:, None] - e["z"]) < reach
        )
    if np.any(((g["ore"] > 0) | (g["oil"] > 0)) & in_start & ~near_real):
        problems.append("invented ore or oil inside the start tile")
    names = (
        [trees["names"][i] for i in np.unique(trees["prefab"])]
        if len(trees["prefab"])
        else []
    )
    environment = meta["environment"]
    if environment not in R.VANILLA_TREES:
        problems.append(f"unknown map environment: {environment}")
    elif set(names) - set(R.VANILLA_TREES[environment]):
        problems.append(
            f"tree prefabs the {environment} environment doesn't load: "
            f"{sorted(set(names) - set(R.VANILLA_TREES[environment]))}"
        )
    planted = len(trees["prefab"])
    if planted > R.Knobs.trees:
        problems.append(f"{planted} trees planted, above the {R.Knobs.trees} budget")
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
        binned = np.bincount(
            (tile[:, None] * 9 + tile[None, :]).ravel(),
            weights=cells.ravel(),
            minlength=81,
        )
        if np.any(binned.reshape(9, 9) != area[key]):
            problems.append(f"{key} tile sums differ from the cell grid")
        if int(area[key][2:7, 2:7].sum()) != meta[field]:
            problems.append(f"{field} is not the 25-tile sum")
    if int(area["finalWater"][2:7, 2:7].sum()) != meta["waterAmount"]:
        problems.append("waterAmount is not the 25-tile sum")
    mx = meta["maxResourceAmount"]
    return problems, {
        "trees": int(len(trees["flags"])),
        "species": {
            n: int((trees["prefab"] == i).sum()) for i, n in enumerate(trees["names"])
        },
        "forest_formula_match": round(match, 5),
        "panel_share": {
            k: round(meta[f] / mx, 4)
            for k, f in [
                ("ore", "oreAmount"),
                ("oil", "oilAmount"),
                ("forest", "forestAmount"),
                ("fertile", "fertileLandAmount"),
                ("water", "waterAmount"),
            ]
        },
    }


def current_cases(fixtures):
    """The current contract's cases, with files resolved through fixture_files."""
    doc = json.loads((fixtures / "current.json").read_text())
    for case in doc["cases"]:
        reference = case["reference"]
        if "presentation_delta" not in reference:
            raise SystemExit(f"{case['slug']}: current contract is not PL-989 shaped")
        mapped = case.get("fixture_files", {})
        base = fixtures / case["slug"]
        paths = {name: fixtures / mapped.get(name, f"{case['slug']}/{name}") for name in case["files_sha256"]}
        yield {
            "slug": case["slug"],
            "prepared": (fixtures / mapped["terrain.u16.gz"]).parent,
            "geometry": base / "geometry.json.gz",
            "landcover": base / "landcover.u8.gz",
            "evidence": base / "evidence.json",
            "knobs": reference["resource_knobs"],
            "plan": fixtures / mapped["plan.npz"],
            "expected_crp_sha256": reference["expected_crp_sha256"],
            "files_sha256": case["files_sha256"],
            "paths": paths,
            "tree_positions_sha256": reference["presentation_delta"]["tree_positions_sha256"],
            "base_plan": fixtures / reference["presentation_delta"]["base_plan"],
            "tree_species_changed": reference["presentation_delta"]["tree_species_changed"],
        }


def historical_cases(fixtures):
    manifest = json.loads((fixtures / "manifest.json").read_text())
    for case in manifest["cases"]:
        if not case.get("resource_plan"):
            raise SystemExit(f"{case['slug']}: reference has no frozen resource plan")
        base = fixtures / case["slug"]
        yield {
            "slug": case["slug"],
            "prepared": base,
            "geometry": base / "geometry.json",
            "landcover": base / "landcover.u8.gz",
            "evidence": base / "evidence.json",
            "knobs": case["resource_knobs"],
            "plan": base / case["resource_plan"],
            "expected_crp_sha256": case["expected_crp_sha256"],
            "files_sha256": case["files_sha256"],
            "paths": {name: base / name for name in case["files_sha256"]},
            "tree_positions_sha256": None,
            "base_plan": None,
            "tree_species_changed": None,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "fixtures")
    parser.add_argument(
        "--historical",
        action="store_true",
        help="check the preserved PL-918 fixture manifest instead of the current contract",
    )
    args = parser.parse_args()
    cases = historical_cases(args.fixtures) if args.historical else current_cases(args.fixtures)
    report, failed = [], False
    for case in cases:
        fixture = case["prepared"]
        for name, digest in case["files_sha256"].items():
            path = case["paths"][name]
            if sha(path) != digest:
                raise SystemExit(f"{case['slug']}: frozen input {name} changed")
        knobs = R.Knobs(**case["knobs"])
        evidence_file = case["evidence"]
        evidence = (
            json.loads(evidence_file.read_text())["evidence"]
            if evidence_file.exists()
            else []
        )
        with tempfile.TemporaryDirectory() as tmp:
            planned, replayed = Path(tmp) / "plan", Path(tmp) / "replay"
            paint(
                fixture,
                case["landcover"],
                planned,
                geometry=case["geometry"],
                evidence=evidence_file if evidence_file.exists() else None,
                knobs=knobs,
            )
            crp = next(planned.glob("*.crp"))
            paint(
                fixture,
                None,
                replayed,
                knobs=knobs,
                plan=case["plan"],
            )
            digest, replay_digest = sha(crp), sha(next(replayed.glob("*.crp")))
            problems, facts = check(crp, evidence)
            if digest != case["expected_crp_sha256"]:
                problems.append(
                    f"planned map {digest} != expected {case['expected_crp_sha256']}"
                )
            if replay_digest != digest:
                problems.append(
                    "replaying frozen plan.npz through the encoders changed the bytes"
                )
            if (planned / "plan.npz").read_bytes() != case["plan"].read_bytes():
                problems.append("resource planning differs from the frozen plan")
            if case["tree_positions_sha256"] is not None:
                plan = np.load(planned / "plan.npz")
                positions = hashlib.sha256(
                    plan["px"].tobytes() + plan["pz"].tobytes()
                ).hexdigest()
                if positions != case["tree_positions_sha256"]:
                    problems.append("tree positions moved in a presentation-only change")
                base = np.load(case["base_plan"])
                for key in ["ore", "oil", "fertility", "forest", "tree"]:
                    if not np.array_equal(base[key], plan[key]):
                        problems.append(
                            f"{key} grid changed in a presentation-only change"
                        )
                if np.array_equal(base["kinds"], plan["kinds"]) == case["tree_species_changed"]:
                    problems.append("tree species flag does not match the frozen plan")
        failed |= bool(problems)
        report.append(
            {"slug": case["slug"], "sha256": digest, "problems": problems, **facts}
        )
    print(json.dumps({"cases": report, "in_game_verified": False}, indent=2))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
