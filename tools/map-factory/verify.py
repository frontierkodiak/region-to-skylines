"""Verify the writer against the native factory's artifact bundle."""

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
from crp import (
    N,
    begin_tag_size,
    decode_u16,
    encode_u16,
    read_package,
    write_map,
    write_package,
)


def verify(folder):
    template = folder / "PL848-Asheville-template.crp"
    layout = folder / "template-layout.json"
    original = template.read_bytes()
    package, assets = read_package(original)
    assert write_package(package, assets) == original
    spec = json.loads(layout.read_text())
    terrain_range = next(
        r for r in spec["ranges"] if r["type"] == "TerrainManager+Data"
    )
    data = next(a["payload"] for a in assets if a["kind"] == 52)
    start = terrain_range["start"] + begin_tag_size(
        data, terrain_range["start"], "TerrainManager"
    )
    raw, _ = decode_u16(data, N, start)
    expected = np.fromfile(folder / "terrain.u16", dtype="<u2")
    assert np.array_equal(raw, expected)
    for values in [
        np.zeros(0, dtype=np.uint16),
        np.zeros(N, dtype=np.uint16),
        np.array([65535, 0, 32767, 32768, 0, 1, 1, 1], dtype=np.uint16),
        expected,
    ]:
        encoded = encode_u16(values)
        decoded, end = decode_u16(encoded, len(values))
        assert np.array_equal(values, decoded) and end == len(encoded)
    with tempfile.TemporaryDirectory(prefix="writer-verify-", dir=folder) as scratch:
        scratch = Path(scratch)
        changed = expected.copy()
        changed[500000] += 64
        changed.tofile(scratch / "changed.u16")
        write_map(
            template,
            layout,
            scratch / "changed.u16",
            folder / "water.u16",
            folder / "hydrology.json",
            scratch / "changed.crp",
        )
        _, changed_assets = read_package((scratch / "changed.crp").read_bytes())
        changed_data = next(a["payload"] for a in changed_assets if a["kind"] == 52)
        changed_decoded, _ = decode_u16(changed_data, N, start)
        assert np.array_equal(changed, changed_decoded)
        spec["template_sha256"] = "0" * 64
        (scratch / "bad-layout.json").write_text(json.dumps(spec))
        try:
            write_map(
                template,
                scratch / "bad-layout.json",
                folder / "terrain.u16",
                folder / "water.u16",
                folder / "hydrology.json",
                scratch / "must-not-exist.crp",
            )
        except ValueError as error:
            assert "fingerprint" in str(error)
        else:
            raise AssertionError("Unbound template was not refused")
        assert not (scratch / "must-not-exist.crp").exists()
    return {
        "native_package_byte_exact_roundtrip": True,
        "native_decoded_terrain_exact_input": True,
        "u16_zero_wrap_literal_runs_roundtrip": True,
        "independent_one_metre_terrain_change_written": True,
        "all_generated_asset_checksums_valid": True,
        "wrong_template_refused_without_output": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2))
