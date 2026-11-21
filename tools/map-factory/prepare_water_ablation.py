"""Prepare matched water-source interventions with frozen observation inputs."""

import argparse
import json
from pathlib import Path
import shutil

from water_diagnostics import MODES, digest, export


def prepare(source, staged, output, modes):
    """Require exact source replay and preserve the original probe/reference set."""
    hydro = json.loads((source / "hydrology.json").read_text())
    package = hydro["map_id"] + ".crp"
    for name in (package, "terrain.u16", "water.u16", "hydrology.json"):
        if (source / name).read_bytes() != (staged / name).read_bytes():
            raise ValueError(f"Observation baseline differs from source: {name}")
    # Native probes use sibling references. Refuse a new or escaping reference.
    probes = json.loads((staged / "probes.json").read_text())
    if (
        probes["reference_water"] != "water.u16"
        or probes["mapped_water"].get("file") != "mapped-water.u8"
    ):
        raise ValueError("Expected frozen sibling water/mask references")
    frozen = {
        name: (staged / name).read_bytes()
        for name in ("probes.json", "mapped-water.u8")
    }
    if probes["mapped_water"].get("sha256") != digest(frozen["mapped-water.u8"]):
        raise ValueError("Frozen mapped-water mask hash mismatch")
    result = export(source, output, modes)
    for variant in result["variants"]:
        folder = output / variant["directory"]
        for name, data in frozen.items():
            (folder / name).write_bytes(data)
        # Output-off changes no initial water. Sea-only is a separate intervention
        # and still retains the original reference-water file for flood comparison.
        shutil.copyfile(staged / "water.u16", folder / "reference-water.u16")
        original_probes = probes.copy()
        if variant["mode"] == "sea-only":
            original_probes["reference_water"] = "reference-water.u16"
            (folder / "probes.json").write_text(
                json.dumps(original_probes, indent=2) + "\n"
            )
        binding = {
            "schema": 1,
            "mode": variant["mode"],
            "source_package_sha256": digest((staged / package).read_bytes()),
            "package_sha256": digest((folder / package).read_bytes()),
            "original_observation_files_sha256": {
                name: digest(data) for name, data in frozen.items()
            },
            "observation_files_sha256": {
                name: digest((folder / name).read_bytes())
                for name in (*frozen, "reference-water.u16")
            },
            "probe_points_unchanged": True,
            "qualification": "matched development intervention; NOT a water promise or holdout observation",
        }
        (folder / "observation-binding.json").write_text(
            json.dumps(binding, indent=2) + "\n"
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("staged", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=MODES, action="append", required=True)
    args = parser.parse_args()
    print(
        json.dumps(prepare(args.source, args.staged, args.output, args.mode), indent=2)
    )
