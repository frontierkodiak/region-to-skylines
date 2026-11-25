"""Author the Air successor fixture from retained inputs; no game or score replay.

uv run --project tools/map-factory python tools/map-factory/freeze_authored_air.py
"""

import gzip
import importlib.util
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import netcodec as nc
from authored_air_contract import ROOT, PREFIX, PREDECESSOR, EXTRA, BASELINES, sha
from crp import read_package, patch_metadata
from generate import generate
from network_writer import section_start, OUTSIDE

FOLDER = ROOT / "tools/map-factory/fixtures"


def compare(before, after):
    """Prove the only simulation changes are added plane paths/connections."""
    _, a = read_package(before)
    _, b = read_package(after)
    assert [(x["name"], x["kind"]) for x in a] == [(x["name"], x["kind"]) for x in b]
    old = next(x["payload"] for x in a if x["kind"] == 52)
    new = next(x["payload"] for x in b if x["kind"] == 52)
    ns, bs = section_start(old, "NetManager"), section_start(old, "BuildingManager")
    nt, bt = section_start(new, "NetManager"), section_start(new, "BuildingManager")
    n0, n1 = nc.NetSection(old, ns), nc.NetSection(new, nt)
    b0, b1 = nc.BuildingSection(old, bs), nc.BuildingSection(new, bt)
    assert old[:ns] == new[:nt]
    assert old[n0.end : bs] == new[n1.end : bt]
    assert old[b0.end :] == new[b1.end :]
    for attr in ("lane_flags", "lane_last_reserve"):
        assert np.array_equal(getattr(n0, attr), getattr(n1, attr))
    assert n0.lane_next == n1.lane_next and n0.tail == n1.tail
    assert all(np.array_equal(x, y) for x, y in zip(n0.lane_reserved, n1.lane_reserved))
    for kind, flags, prefabs in [
        ("nodes", "node_flags", "node_prefab"),
        ("segments", "segment_flags", "segment_prefab"),
    ]:
        prior, future = getattr(n0, kind), getattr(n1, kind)
        for key, record in prior.items():
            assert future[key] == record, (kind, key)
            for field in (flags, flags + "2"):
                assert getattr(n0, field)[key - 1] == getattr(n1, field)[key - 1]
            assert (
                n0.prefabs.names[getattr(n0, prefabs)[key]]
                == n1.prefabs.names[getattr(n1, prefabs)[key]]
            )
        for key in future.keys() - prior.keys():
            assert "Airplane" in n1.prefabs.names[getattr(n1, prefabs)[key]]
    for key in b0.ids:
        x, y = b0.ids.index(key), b1.ids.index(key)
        assert b0.prefab(key) == b1.prefab(key)
        assert b0.records[x] == b1.records[y] and b0.race[x] == b1.race[y]
        assert all(
            np.array_equal(c[2][x], d[2][y]) for c, d in zip(b0.columns, b1.columns)
        )
        assert (
            b0.flags[key - 1] == b1.flags[key - 1]
            and b0.flags2[key - 1] == b1.flags2[key - 1]
        )
    for key in set(b1.ids) - set(b0.ids):
        assert b1.prefab(key) == "Airplane Connection"
    entries = sum(
        "Airplane" in n1.prefabs.names[n1.node_prefab[k]]
        and bool(int(n1.node_flags[k - 1]) & OUTSIDE)
        for k in n1.nodes
    )
    assert entries >= 2
    for x, y in zip(a, b):
        if x["kind"] == 52:
            continue
        if x["kind"] == 100 and before != after:
            assert (
                patch_metadata(
                    x["payload"],
                    __import__("hashlib").md5(new).hexdigest(),
                    fields={
                        "incomingPlanePath": ("System.Int32", entries),
                        "outgoingPlanePath": ("System.Int32", entries),
                    },
                )
                == y["payload"]
            )
        else:
            assert x["payload"] == y["payload"], x["name"]
    return {
        "plane_entries": entries,
        "other_managers_equal": True,
        "existing_network_equal": True,
        "added_nodes": len(n1.nodes) - len(n0.nodes),
        "added_segments": len(n1.segments) - len(n0.segments),
        "added_buildings": len(b1.ids) - len(b0.ids),
        "unchanged_managers_sha256": [
            sha(old[:ns]),
            sha(old[n0.end : bs]),
            sha(old[b0.end :]),
        ],
    }


def freeze():
    previous_raw = (FOLDER / PREDECESSOR).read_bytes()
    previous = json.loads(previous_raw)
    spec = importlib.util.spec_from_file_location(
        "pre_air_generate", FOLDER / BASELINES["tools/map-factory/generate.py"]
    )
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    baseline.ROOT = (
        ROOT / "tools/map-factory"
    )  # Exact archived code; current unchanged template paths.
    sources = {
        name: sha((ROOT / name).read_bytes())
        for name in list(previous["source_files_sha256"])
        + ["tools/map-factory/" + n for n in EXTRA]
    }
    predecessor = {"file": PREDECESSOR, "sha256": sha(previous_raw)}
    rows, cases = [], []
    with tempfile.TemporaryDirectory(prefix="air-fixtures-") as temporary:
        scratch = Path(temporary)

        def build_case(old):
            case_rows = []
            slug = old["slug"]

            def effective(name):
                return FOLDER / old["fixture_files"].get(name, slug + "/" + name)

            png = effective("input.png")
            banks = scratch / (slug + "-banks.f32")
            banks.write_bytes(gzip.decompress(effective("banks.f32.gz").read_bytes()))
            case = {"slug": slug}
            for kind in ("reference", "shipping"):
                geometry_name = (
                    old["shipping"]["geometry_file"]
                    if kind == "shipping"
                    else "geometry.json.gz"
                )
                geometry = scratch / (slug + "-" + kind + ".json")
                geometry.write_bytes(
                    gzip.decompress(effective(geometry_name).read_bytes())
                )
                evidence_name = (
                    old["shipping"].get("evidence_file")
                    if kind == "shipping"
                    else "evidence.json"
                )
                kwargs = {
                    "landcover": effective("landcover.u8.gz"),
                    "evidence": effective(evidence_name) if evidence_name else None,
                }
                args = (png, geometry)
                before_dir, after_dir = (
                    scratch / (slug + kind + "-before"),
                    scratch / (slug + kind + "-after"),
                )
                before = baseline.generate(*args, before_dir, banks, **kwargs)
                after = generate(*args, after_dir, banks, **kwargs)
                expected = {
                    key: after["package"][
                        key.removeprefix("expected_crp_")
                        if key != "expected_simulation_sha256"
                        else "simulation_sha256"
                    ]
                    for key in (
                        "expected_crp_sha256",
                        "expected_crp_bytes",
                        "expected_simulation_sha256",
                    )
                }
                before_expected = {key: old[kind][key] for key in expected}
                assert (
                    before["package"]["sha256"]
                    == before_expected["expected_crp_sha256"]
                ), (slug, kind, "baseline no longer reproduces")
                before_bytes, after_bytes = (
                    next(before_dir.glob("*.crp")).read_bytes(),
                    next(after_dir.glob("*.crp")).read_bytes(),
                )
                assert len(before_bytes) == before_expected["expected_crp_bytes"]
                assert (
                    before["package"]["simulation_sha256"]
                    == before_expected["expected_simulation_sha256"]
                )
                for name in ("terrain.u16", "water.u16", "plan.npz", "hydrology.json"):
                    assert (before_dir / name).read_bytes() == (
                        after_dir / name
                    ).read_bytes(), (slug, kind, name)
                prepared = {
                    name: sha((after_dir / name).read_bytes())
                    for name in ("terrain.u16", "water.u16")
                }
                assert prepared == old["reference"]["prepared_sha256"]
                case_rows.append(
                    {
                        "slug": slug,
                        "kind": kind,
                        "before": before_expected,
                        "after": expected,
                        "prepared_sha256": prepared,
                        **compare(before_bytes, after_bytes),
                    }
                )
                case[kind] = expected
                print(slug, kind, expected["expected_crp_bytes"], flush=True)
            return case_rows, case

        with ThreadPoolExecutor(max_workers=4) as pool:
            for case_rows, case in pool.map(build_case, previous["cases"]):
                rows.extend(case_rows)
                cases.append(case)
    proof = {
        "native_tested": False,
        "predecessor": predecessor,
        "source_files_sha256": sources,
        "cases": rows,
    }
    proof_raw = (json.dumps(proof, indent=2) + "\n").encode()
    current = {
        "format": 1,
        "version": "pl1119-authored-air-v1",
        "status": "byte_conformance_only_not_native_tested",
        "scope": "Add plane entries; retain all earlier fixture and native evidence without qualifying the new packages",
        "predecessor": predecessor,
        "source_files_sha256": sources,
        "export_gate_files_sha256": previous["export_gate_files_sha256"],
        "baseline_sources": {
            name: {"file": path, "sha256": sha((FOLDER / path).read_bytes())}
            for name, path in BASELINES.items()
        },
        "proof": {"file": PREFIX + "/proof.json", "sha256": sha(proof_raw)},
        "cases": cases,
    }
    target = FOLDER / PREFIX
    target.mkdir(exist_ok=True)
    (target / "proof.json").write_bytes(proof_raw)
    (target / "current.json").write_text(json.dumps(current, indent=2) + "\n")


if __name__ == "__main__":
    freeze()
