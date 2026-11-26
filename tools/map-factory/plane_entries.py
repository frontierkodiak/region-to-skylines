"""Always author plane entries in the shipping reference writer."""

import hashlib
from pathlib import Path
import numpy as np
from crp import read_package, write_package, patch_metadata
import netcodec as nc
from network_writer import apply_highways, section_start, OUTSIDE
from transport_paths import air_path


def ensure_plane_entries(path, geometry, prepared):
    path, prepared = Path(path), Path(prepared)
    package, assets = read_package(path.read_bytes())
    simulation = next(a for a in assets if a["kind"] == 52)
    data = simulation["payload"]
    net = nc.NetSection(data, section_start(data, "NetManager"))
    existing = [
        i
        for i in net.nodes
        if "Airplane" in net.prefabs.names[net.node_prefab[i]]
        and int(net.node_flags[i - 1]) & OUTSIDE
    ]
    if len(existing) >= 2:
        return {
            "entries": len(existing),
            "authored": False,
            "simulation_sha256": hashlib.sha256(data).hexdigest(),
        }
    ground = (
        np.flipud(
            np.fromfile(prepared / "terrain.u16", dtype="<u2").reshape(1081, 1081)
        ).astype(float)
        / 64
    )
    graph, _ = air_path(geometry, ground)
    updated, report = apply_highways(
        data, graph, lambda x, z: 0, preserve_existing=True
    )
    simulation["payload"] = updated
    checksum = hashlib.md5(updated).hexdigest()
    for asset in assets:
        if asset["kind"] == 100:
            asset["payload"] = patch_metadata(
                asset["payload"],
                checksum,
                fields={
                    "incomingPlanePath": ("System.Int32", report["plane_paths"]),
                    "outgoingPlanePath": ("System.Int32", report["plane_paths"]),
                },
            )
    path.write_bytes(write_package(package, assets))
    return {
        "entries": report["plane_paths"],
        "authored": True,
        "simulation_sha256": hashlib.sha256(updated).hexdigest(),
    }
