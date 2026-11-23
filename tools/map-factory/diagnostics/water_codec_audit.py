"""Frozen read-only six-case package audit and synthetic serialization fixtures."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crp import decode_u16, read_package, write_package  # noqa: E402
from water_value_codec import (  # noqa: E402
    DOMAIN_NAMES,
    TAG,
    WaterValues,
    decode_chunk,
    domains,
    encode_chunk,
    encode_geographic_change,
    grow_depth,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = "value-preserving-initial-water-codec-v1"
FIXTURES = "calibration/pl1191-construction-v1/development/phase32-codec-fixtures.json"
FILES = (
    "diagnostics/water_value_codec.py",
    "diagnostics/water_codec_audit.py",
    "diagnostics/test_water_value_codec.py",
    FIXTURES,
    "calibration/pl1191-construction-v1/development/phase32-codec-policy.md",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(p):
    return json.loads(p.read_text())


def write(p, value):
    p.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def check_files(root, files):
    for name, digest in files.items():
        if sha((root / name).read_bytes()) != digest:
            raise ValueError(f"Changed bound source/input: {name}")


def stage(parent, results, output):
    if output.exists():
        raise ValueError("Fresh protocol required")
    f = load(parent / "freeze.json")
    check_files(parent, f["files_sha256"])
    check_files(ROOT, f["source_files_sha256"])
    r = load(results / "receipt.json")
    if r["input_freeze_sha256"] != sha((parent / "freeze.json").read_bytes()):
        raise ValueError("Wrong joint results")
    check_files(results, r["files_sha256"])
    output.mkdir(parents=True)
    shutil.copytree(parent, output / "joint-protocol")
    shutil.copytree(results, output / "joint-results")
    shutil.copyfile(ROOT / FIXTURES, output / "fixtures.json")
    dependencies = dict(f["source_files_sha256"])
    dependencies.update({n: sha((ROOT / n).read_bytes()) for n in FILES})
    packages = {}
    for name in f["cases"]:
        found = [
            p for p in (output / "joint-protocol").rglob("*.crp") if name in p.parts
        ]
        if len(found) > 1:
            raise ValueError(f"Ambiguous physical package: {name}")
        packages[name] = str(found[0].relative_to(output)) if found else None
    if sum(p is not None for p in packages.values()) != 4:
        raise ValueError("Expected four physical inputs and two original NULL cases")
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": f["cases"],
            "packages": packages,
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p.read_bytes())
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "prior_joint_results_known": True,
            "new_codec_audit_not_yet_evaluated": True,
            "geographic_change_or_game": False,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong codec protocol")
    check_files(ROOT, f["source_files_sha256"])
    check_files(folder, f["files_sha256"])
    return f


def equal_values(a, b):
    return (
        np.array_equal(a.depth, b.depth)
        and all(np.array_equal(x, y) for x, y in zip(a.compact, b.compact, strict=True))
        and a.controls == b.controls
        and a.trailer == b.trailer
        and a.tail == b.tail
    )


def fixture_state(spec):
    depth = np.zeros(spec["shape"], dtype=np.uint16)
    for r, c, value in spec["initial_depth"]:
        depth[r, c] = value
    compact = tuple(
        np.array(
            [((i + 1) * 1009 + int(k) * 37) % 65536 for k in keys], dtype=np.uint16
        )
        for i, keys in enumerate(domains(depth))
    )
    records = tuple(
        struct.pack(">6fHH", *c["xyz"], *c["xyz"], 1, c["target_q"])
        + b"".join(v.to_bytes(3, "big") for v in c["raw_slots"])
        for c in spec["control_records"]
    )
    t = spec["trailer"]
    return WaterValues(
        depth,
        compact,
        records,
        struct.pack(">HfbbI", 0, t["sea"], 0, 0, t["frame"]),
        bytes.fromhex(t["tail_hex"]),
    )


def declarations(before, after):
    return tuple(
        {int(k): ((i + 1) * 5003 + int(k) * 53) % 65536 for k in np.setdiff1d(new, old)}
        for i, (old, new) in enumerate(
            zip(domains(before), domains(after), strict=True)
        )
    )


def synthetic(spec, output):
    state = fixture_state(spec)
    raw = encode_chunk(state)
    (output / "synthetic-original.bin").write_bytes(raw)
    decoded, consumed = decode_chunk(raw, tuple(spec["shape"]))
    if consumed != len(raw) or not equal_values(state, decoded):
        raise ValueError("Synthetic original does not fully round-trip")
    cases = []
    for case in spec["growth_cases"]:
        depth = state.depth.copy()
        for r, c, value in case["set_depth"]:
            depth[r, c] = value
        declared = declarations(state.depth, depth)
        changed = grow_depth(state, depth, declared)
        packed = encode_chunk(changed)
        roundtrip, consumed = decode_chunk(packed, tuple(spec["shape"]))
        if consumed != len(packed) or not equal_values(changed, roundtrip):
            raise ValueError("Synthetic changed values failed full round-trip")
        # Independent literal domain predicate and expected key/value table.
        checks = []
        h, w = depth.shape
        for i in range(3):
            expected = {}
            for r in range(h):
                for c in range(w):
                    wet = depth[r, c] > 0
                    if i == 1 and c + 1 < w:
                        wet |= depth[r, c + 1] > 0
                    if i == 2 and r + 1 < h:
                        wet |= depth[r + 1, c] > 0
                    if wet:
                        k = r * w + c
                        old = dict(
                            zip(
                                map(int, domains(state.depth)[i]),
                                map(int, state.compact[i]),
                            )
                        )
                        expected[k] = old[k] if k in old else declared[i][k]
            actual = dict(
                zip(map(int, domains(depth)[i]), map(int, roundtrip.compact[i]))
            )
            if actual != expected:
                raise ValueError("Independent synthetic domain/value check failed")
            checks.append(
                {
                    "name": DOMAIN_NAMES[i],
                    "keys_and_values": list(actual.items()),
                    "new_values": declared[i],
                }
            )
        (output / f"synthetic-{case['name']}.bin").write_bytes(packed)
        cases.append(
            {
                "name": case["name"],
                "domain_values": checks,
                "all_values_controls_trailer_tail_equal": True,
                "bytes": len(packed),
                "sha256": sha(packed),
            }
        )
    # Legal alternative depth representation: literal 1, delta+0 =>2, repeat =>3.
    alternate_state = WaterValues(
        np.array([[1, 2, 3]], dtype=np.uint16),
        tuple(
            np.array([100 + i, 32768 + i, 65535 - i], dtype=np.uint16) for i in range(3)
        ),
        state.controls,
        state.trailer,
        state.tail,
    )
    canonical = encode_chunk(alternate_state)
    from crp import encode_u16

    alternate = (
        TAG
        + bytes.fromhex("000001400080")
        + canonical[len(TAG) + len(encode_u16(alternate_state.depth)) :]
    )
    a, consumed = decode_chunk(alternate, (1, 3))
    if (
        consumed != len(alternate)
        or not equal_values(a, alternate_state)
        or alternate == canonical
    ):
        raise ValueError("Alternative representation proof failed")
    (output / "synthetic-alternate.bin").write_bytes(alternate)
    (output / "synthetic-alternate-canonical.bin").write_bytes(canonical)
    try:
        encode_geographic_change({"selected": False})
    except ValueError:
        refused = True
    else:
        raise ValueError("Unselected geographic change was not refused")
    return {
        "cases": cases,
        "alternate_bytes_equal": False,
        "alternate_values_equal": True,
        "unselected_geographic_change_refused": refused,
    }


def audit_package(path, output):
    data = path.read_bytes()
    package, assets = read_package(data)
    sims = [a for a in assets if a["kind"] == 52]
    if len(sims) != 1 or sims[0]["payload"].count(TAG) != 1:
        raise ValueError("Unique simulation and water manager required")
    original = sims[0]["payload"]
    start = original.index(TAG)
    state, consumed = decode_chunk(original[start:])
    # Cross-check all four arrays using the unchanged legal local decoder.
    offset = start + len(TAG)
    for values in (state.depth.ravel(), *state.compact):
        reference, offset = decode_u16(original, len(values), offset)
        if not np.array_equal(values, reference):
            raise ValueError("Existing decoder disagrees on raw array values")
    if original[offset : offset + 2] != struct.pack(">H", len(state.controls)):
        raise ValueError("Source count offset mismatch")
    if original[offset + 2 : offset + 2 + len(state.controls) * 43] != b"".join(
        state.controls
    ):
        raise ValueError("Raw control table mismatch")
    packed = encode_chunk(state)
    reread, end = decode_chunk(packed)
    if end != len(packed) or not equal_values(state, reread):
        raise ValueError("Full manager value round-trip failed")
    replacement = original[:start] + packed + original[start + consumed :]
    copied = [dict(a) for a in assets]
    sim_index = next(i for i, a in enumerate(assets) if a is sims[0])
    copied[sim_index]["payload"] = replacement
    reconstructed = write_package(package, copied)
    p2, a2 = read_package(reconstructed)
    if package != p2 or len(assets) != len(a2):
        raise ValueError("Package metadata changed")
    for i, (a, b) in enumerate(zip(assets, a2, strict=True)):
        if a["name"] != b["name"] or a["kind"] != b["kind"]:
            raise ValueError("Asset identity/order changed")
        if i != sim_index and a["payload"] != b["payload"]:
            raise ValueError("Non-water asset changed")
    if (
        replacement[:start] != original[:start]
        or replacement[start + len(packed) :] != original[start + consumed :]
    ):
        raise ValueError("Non-water simulation bytes changed")
    output.mkdir()
    (output / "reencoded-manager.bin").write_bytes(packed)
    (output / "raw43-controls.bin").write_bytes(b"".join(state.controls))
    return {
        "status": "read_only_values_verified",
        "package_sha256": sha(data),
        "manager_original_sha256": sha(original[start : start + consumed]),
        "manager_reencoded_sha256": sha(packed),
        "manager_bytes_equal": packed == original[start : start + consumed],
        "package_reencoded_in_memory_bytes_equal": reconstructed == data,
        "all_depth_and_compact_values_equal": True,
        "compact": [
            {
                "domain": name,
                "elements": len(a),
                "nonzero_values": int(np.count_nonzero(a)),
                "raw_le_u16_sha256": sha(a.astype("<u2").tobytes()),
            }
            for name, a in zip(DOMAIN_NAMES, state.compact, strict=True)
        ],
        "depth_raw_le_u16_sha256": sha(state.depth.astype("<u2").tobytes()),
        "controls_count": len(state.controls),
        "raw43_concatenated_sha256": sha(b"".join(state.controls)),
        "all_controls_order_header_trailer_tail_nonwater_equal": True,
        "trailer_hex": state.trailer.hex(),
        "tail_hex": state.tail.hex(),
        "old_source_count_offset_in_simulation": offset,
        "reencoded_source_count_offset_in_simulation": start
        + len(TAG)
        + sum(
            len(__import__("crp").encode_u16(a)) for a in (state.depth, *state.compact)
        ),
        "geographic_CRPor_new_water_grid_written": False,
    }


def evaluate(folder, output):
    f = preflight(folder)
    if output.exists():
        raise ValueError("Fresh audit output required")
    output.mkdir(parents=True)
    write(output / "synthetic.json", synthetic(load(folder / "fixtures.json"), output))
    for name in f["cases"]:
        print(name, flush=True)
        p = f["packages"][name]
        result = (
            audit_package(folder / p, output / name)
            if p
            else {
                "status": "unknown_original_base_refusal",
                "physical": None,
                "operations": None,
            }
        )
        write(output / f"{name}.json", result)
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": sha((folder / "freeze.json").read_bytes()),
            "files_sha256": {
                str(p.relative_to(output)): sha(p.read_bytes())
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "geographic_change_or_game": False,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    a = s.add_parser("stage")
    for key in ("parent", "results", "output"):
        a.add_argument(key, type=Path)
    a = s.add_parser("preflight")
    a.add_argument("folder", type=Path)
    a = s.add_parser("evaluate")
    a.add_argument("folder", type=Path)
    a.add_argument("output", type=Path)
    a = p.parse_args()
    if a.command == "stage":
        stage(a.parent, a.results, a.output)
    elif a.command == "preflight":
        preflight(a.folder)
    else:
        evaluate(a.folder, a.output)


if __name__ == "__main__":
    main()
