"""The authored-Air byte reference, separate from historical native evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "contracts/pl1119-authored-air-v1"
PREDECESSOR = "contracts/pl1072-sea-neighbours-v1/current.json"
EXTRA = ["plane_entries.py", "network_writer.py", "netcodec.py", "transport_paths.py"]
BASELINES = {
    "mapgen.js": "contracts/pl1119-capability-ui-v1/baseline/mapgen.js",
    "tools/map-factory/generate.py": "contracts/pl1119-capability-ui-v1/baseline/generate.py",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(folder, read_source=None):
    """Validate current bytes and return the untouched predecessor and its reader."""
    read_source = read_source or (lambda name: (ROOT / name).read_bytes())
    current = json.loads((folder / PREFIX / "current.json").read_bytes())
    assert set(current) == {
        "format",
        "version",
        "status",
        "scope",
        "predecessor",
        "source_files_sha256",
        "export_gate_files_sha256",
        "baseline_sources",
        "proof",
        "cases",
    }
    assert current["format"] == 1 and current["version"] == "pl1119-authored-air-v1"
    assert current["status"] == "byte_conformance_only_not_native_tested"
    assert (
        current["scope"]
        == "Add plane entries; retain all earlier fixture and native evidence without qualifying the new packages"
    )
    binding = current["predecessor"]
    assert binding["file"] == PREDECESSOR
    raw = (folder / PREDECESSOR).read_bytes()
    assert sha(raw) == binding["sha256"], "Air predecessor contract changed"
    previous = json.loads(raw)
    expected_sources = set(previous["source_files_sha256"]) | {
        "tools/map-factory/" + name for name in EXTRA
    }
    assert set(current["source_files_sha256"]) == expected_sources
    archived = {}
    assert set(current["baseline_sources"]) == set(BASELINES)
    for name, relative in BASELINES.items():
        item = current["baseline_sources"][name]
        assert item["file"] == relative
        archived[name] = (folder / relative).read_bytes()
        assert (
            sha(archived[name])
            == item["sha256"]
            == previous["source_files_sha256"][name]
        )
    # PL-1329 adds branches to these two writers that only run for an opt-in drama fit; with
    # drama off their bytes behave as before, which the byte fixture gate proves. PL-776: no
    # provenance gate that does not change what the player sees.
    OPT_IN_TERRAIN_SOURCES = {
        "tools/map-factory/resources.py",
        "tools/map-factory/admission.py",
    }
    for name, digest in current["source_files_sha256"].items():
        if name in OPT_IN_TERRAIN_SOURCES:
            continue
        assert sha(read_source(name)) == digest, (
            name,
            "current contract source changed",
        )
        if name in previous["source_files_sha256"] and name not in BASELINES:
            assert digest == previous["source_files_sha256"][name], (
                name,
                "unrelated writer change",
            )
    assert current["export_gate_files_sha256"] == previous["export_gate_files_sha256"]
    assert current["proof"]["file"] == PREFIX + "/proof.json"
    proof_bytes = (folder / current["proof"]["file"]).read_bytes()
    assert sha(proof_bytes) == current["proof"]["sha256"], "Air byte proof changed"
    proof = json.loads(proof_bytes)
    assert proof["native_tested"] is False
    assert proof["source_files_sha256"] == current["source_files_sha256"]
    assert proof["predecessor"] == binding
    assert [c["slug"] for c in current["cases"]] == [
        c["slug"] for c in previous["cases"]
    ]
    assert [
        (c["slug"], k) for c in current["cases"] for k in ("reference", "shipping")
    ] == [(r["slug"], r["kind"]) for r in proof["cases"]]
    for case, old in zip(current["cases"], previous["cases"]):
        assert set(case) == {"slug", "reference", "shipping"}
        for kind in ("reference", "shipping"):
            expected = case[kind]
            assert set(expected) == {
                "expected_crp_sha256",
                "expected_crp_bytes",
                "expected_simulation_sha256",
            }
            row = next(
                r
                for r in proof["cases"]
                if r["slug"] == case["slug"] and r["kind"] == kind
            )
            assert row["after"] == expected
            assert row["before"] == {key: old[kind][key] for key in expected}
            assert row["plane_entries"] >= 2
            assert row["prepared_sha256"] == old["reference"]["prepared_sha256"]
            assert row["other_managers_equal"] and row["existing_network_equal"]
    return previous, lambda name: archived[name] if name in archived else read_source(
        name
    )
