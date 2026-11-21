"""Full wet-graph counts, never wet-selected replacement paths or qualification."""

import argparse
from pathlib import Path

import numpy as np
from scipy import ndimage

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid, source_domains
from region import raster


def boundary_connected(wet, boundary, adjacency):
    labels, _ = ndimage.label(
        wet, ndimage.generate_binary_structure(2, 1 if adjacency == 4 else 2)
    )
    roots = np.unique(labels[boundary & wet])
    return np.isin(labels, roots[roots != 0])


def stage(protocol, output):
    if output.exists():
        raise ValueError("Fresh full-graph diagnostic required")
    output.mkdir(parents=True)
    files = [protocol / "physical/geometry.json", protocol / "physical/probes.json"]
    files += [protocol / f"native/grids/ws{i:06d}-water.u16" for i in range(61)]
    write(
        output / "freeze.json",
        {
            "schema": "polli.coastal-wet-connectivity-freeze/1",
            "known_basis": "The previously fixed shortest paths contain dry nodes; that alone cannot rule out other wet routes",
            "policy": "All nodes depth>0.1m;4/8adjacency; literal ocean polygon square-edge seeds. Every source piece retained. Counts only, no wet-selected replacement path/probe, no flow/acceptance claim.",
            "input_protocol": str(protocol),
            "files_sha256": {str(p.relative_to(protocol)): sha(p) for p in files},
            "source_sha256": sha(ROOT / "diagnostics/coastal_wet_connectivity.py"),
        },
    )
    geometry = load(protocol / "physical/geometry.json")
    domains = source_domains(geometry)
    ocean = np.flipud(raster(geometry["sq"], geometry.get("oceans", []), polygons=True))
    edge = np.zeros_like(ocean)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    samples = []
    for i in range(61):
        depth = grid(protocol / f"native/grids/ws{i:06d}-water.u16")
        wet = depth > 6.4
        connection = {a: boundary_connected(wet, ocean & edge, a) for a in (4, 8)}
        samples.append(
            {
                "prefix": f"ws{i:06d}",
                "boundary_wet_nodes": int((wet & ocean & edge).sum()),
                "full_grid_boundary_connected_wet_nodes": {
                    str(a): int(c.sum()) for a, c in connection.items()
                },
                "source_features": [
                    {
                        "id": entry["id"],
                        "name": entry["name"],
                        "scope": entry["scope"],
                        "nodes": entry["native_nodes"],
                        "wet_nodes": int((wet & mask).sum()),
                        "boundary_connected_wet_nodes": {
                            str(a): int((mask & c).sum()) for a, c in connection.items()
                        },
                    }
                    for entry, mask in domains
                ],
            }
        )
    write(
        output / "result.json",
        {
            "freeze_sha256": sha(output / "freeze.json"),
            "samples": samples,
            "limits": "Sampled raster wet connectivity is not hydraulic capacity, known geographic direction, discharge or source-budget proof. No route/probe was chosen from wet outcomes. All old acceptance failures remain.",
        },
    )
    return {
        "freeze_sha256": sha(output / "freeze.json"),
        "result_sha256": sha(output / "result.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(stage(args.protocol, args.output))
