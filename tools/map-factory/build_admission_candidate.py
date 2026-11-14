"""Build all five held-input admission candidates, without modifying fixtures.

Retain source geometry, probes and layout. Native qualification is a separate
operation; no initial wetness count here is an acceptance criterion.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from generate import generate, ROOT
from minor_stream_candidate import SLUGS, inspect_package


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build(output):
    historical = json.loads((ROOT / "fixtures/manifest.json").read_text())
    report = {
        "writer_sha256": sha((ROOT / "region.py").read_bytes()),
        "status": "unqualified",
        "cases": [],
    }
    for slug in SLUGS:
        fixture = ROOT / "fixtures" / slug
        case = next(c for c in historical["cases"] if c["slug"] == slug)
        for name, digest in case["files_sha256"].items():
            assert sha((fixture / name).read_bytes()) == digest, (slug, name)
        source = output / "inputs" / slug
        source.mkdir(parents=True, exist_ok=True)
        for name, frozen in [
            ("banks.f32", "banks.f32.gz"),
            ("source-geometry.json", "shipping-geometry.json.gz"),
        ]:
            (source / name).write_bytes(
                gzip.decompress((fixture / frozen).read_bytes())
            )
        result = generate(
            fixture / "input.png",
            source / "source-geometry.json",
            source,
            source / "banks.f32",
            landcover=fixture / "landcover.u8.gz",
            evidence=fixture / "shipping-evidence.json"
            if (fixture / "shipping-evidence.json").exists()
            else None,
        )
        inspect_package(source)
        hydro = json.loads((source / "hydrology.json").read_text())
        old = json.loads(gzip.decompress((fixture / "hydrology.json.gz").read_bytes()))
        assert old["start_tile"] == hydro["start_tile"], slug
        assert old["samples"].keys() == hydro["samples"].keys(), slug
        assert old["node_positions"].keys() == hydro["node_positions"].keys(), slug
        assert all(
            v[::2] == hydro["node_positions"][k][::2]
            for k, v in old["node_positions"].items()
        ), slug
        item = {
            "slug": slug,
            "crp_sha256": result["package"]["sha256"],
            "crp_bytes": result["package"]["bytes"],
            "start_tile": hydro["start_tile"],
            "horizontal_network_unchanged": True,
            "admission": hydro.get("channel_admission"),
            "grids": {},
        }
        for name in ["terrain.u16", "water.u16"]:
            raw = (source / name).read_bytes()
            before = gzip.decompress((fixture / (name + ".gz")).read_bytes())
            item["grids"][name] = {
                "after_sha256": sha(raw),
                "before_sha256": sha(before),
                "changed_vertices": int(
                    np.count_nonzero(
                        np.frombuffer(raw, "<u2") != np.frombuffer(before, "<u2")
                    )
                ),
            }
        report["cases"].append(item)
        (output / "fixtures").mkdir(exist_ok=True)
        (output / "fixtures/manifest.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(
            json.dumps({k: item[k] for k in ["slug", "crp_sha256", "start_tile"]}),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
