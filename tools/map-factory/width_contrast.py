"""Build ONE terrain-only 24m/40m diagnostic, never a default map policy.

Copy the source's raw simulation suffix verbatim: initial water, source controls,
networks, resources and saved camera remain byte-identical. Only encoded terrain
arrays and the simulation checksum reference change. Do not rerun the writer,
which would otherwise re-anchor source heights on the changed bed.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np

from crp import N, decode_u16, encode_u16, read_package, string, write_package
from template import manager_tag

ROOT = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build(source, output):
    receipt = json.loads((source / "generation.json").read_text())
    hydro = json.loads((source / "hydrology.json").read_text())
    original = (source / (hydro["map_id"] + ".crp")).read_bytes()
    assert sha(original) == receipt["package"]["sha256"]
    output.mkdir(parents=True, exist_ok=False)
    subprocess.run(
        ["node", str(ROOT / "diagnostic-width-delta.mjs"), str(source), str(output)],
        check=True,
    )
    package, assets = read_package(original)
    simulation = next(a for a in assets if a["kind"] == 52)
    data = simulation["payload"]
    tag = manager_tag("TerrainManager")
    start = data.index(tag) + len(tag)
    before, end = decode_u16(data, N, start)
    old_delta, tail = decode_u16(data, int(np.count_nonzero(before)), end)
    assert not old_delta.any()
    np.testing.assert_array_equal(
        before, np.fromfile(source / "terrain.u16", dtype="<u2")
    )
    banks = np.flipud(
        np.fromfile(source / "banks.f32", dtype="<f4").reshape(1081, 1081)
    ).ravel()
    difference = np.flipud(
        np.fromfile(output / "width-delta.f32", dtype="<f4").reshape(1081, 1081)
    ).ravel()
    # Restoring banks must never lower ground or raise it above the held DEM.
    room = np.maximum(0, np.floor(banks * 64 + 0.5) - before.astype(float))
    raised = np.minimum(room, np.floor(difference * 64 + 0.5))
    after = (before.astype(float) + raised).clip(0, 65535).astype("<u2")
    assert np.all(after >= before)
    encoded = encode_u16(after) + encode_u16(
        np.zeros(np.count_nonzero(after), dtype=np.uint16)
    )
    changed = data[:start] + encoded + data[tail:]
    assert changed[start + len(encoded) :] == data[tail:]
    simulation["payload"] = changed
    old_ref = string(hashlib.md5(data).hexdigest())
    new_ref = string(hashlib.md5(changed).hexdigest())
    for asset in assets:
        if asset["kind"] == 100:
            assert asset["payload"].count(old_ref) == 1
            asset["payload"] = asset["payload"].replace(old_ref, new_ref)
    raw = write_package(package, assets)
    _, check = read_package(raw)
    payload = next(a["payload"] for a in check if a["kind"] == 52)
    decoded, offset = decode_u16(payload, N, start)
    delta, offset = decode_u16(payload, int(np.count_nonzero(decoded)), offset)
    np.testing.assert_array_equal(decoded, after)
    assert not delta.any() and payload[offset:] == data[tail:]
    preserved = {}
    for name in [
        "water.u16",
        "hydrology.json",
        "geometry.json",
        "banks.f32",
        "plan.npz",
    ]:
        shutil.copyfile(source / name, output / name)
        preserved[name] = sha((source / name).read_bytes())
        assert sha((output / name).read_bytes()) == preserved[name]
    after.tofile(output / "terrain.u16")
    (output / (hydro["map_id"] + ".crp")).write_bytes(raw)
    recipe = json.loads((output / "width-recipe.json").read_text())
    recipe.update(
        {
            "base_crp_sha256": sha(original),
            "crp_sha256": sha(raw),
            "preserved_files_sha256": preserved,
            "unchanged_simulation_suffix_sha256": sha(data[tail:]),
            "changed_terrain_cells": int(np.count_nonzero(after != before)),
            "changed_terrain_bytes": sum(
                a != b for a, b in zip(after.tobytes(), before.astype("<u2").tobytes())
            ),
            "max_raise_m": float((after.astype(float) - before).max() / 64),
            "lowered_cells": int(np.count_nonzero(after < before)),
        }
    )
    (output / "width-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    receipt.update(
        {
            "diagnostic": "terrain-only 24m versus 40m browser contribution",
            "release_candidate": False,
            "in_game_verified": False,
            "preparation_not_recomputed": True,
            "package": {
                **receipt["package"],
                "sha256": sha(raw),
                "bytes": len(raw),
                "simulation_sha256": sha(changed),
            },
        }
    )
    (output / "generation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(recipe, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve())
