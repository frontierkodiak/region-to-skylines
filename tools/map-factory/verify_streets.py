"""Read a written street package and verify its graph through the shared codec.

This verifies serialized records, not loading, lane reconstruction or gameplay.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

import netcodec as nc
from crp import read_package
from network_writer import section_start


def verify(prepared, source):
    hydro = json.loads((prepared / "hydrology.json").read_text())
    generation = json.loads((prepared / "generation.json").read_text())
    crp = prepared / (hydro["map_id"] + ".crp")
    assert (
        hashlib.sha256(crp.read_bytes()).hexdigest() == generation["package"]["sha256"]
    )
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == hydro["highway_report"]["source_sha256"]
    )
    _, assets = read_package(crp.read_bytes())
    data = next(a["payload"] for a in assets if a["kind"] == 52)
    net = nc.NetSection(data, section_start(data, "NetManager"))
    buildings = nc.BuildingSection(data, section_start(data, "BuildingManager"))
    for name, section in (("NetManager", net), ("BuildingManager", buildings)):
        assert section.encode() == data[section_start(data, name) : section.end]
    graph = hydro["highways"]
    ids = generation["package"]["highways"]["segment_ids"]
    node_ids, prefabs = {}, Counter()

    def f32(values):
        return [float(np.float32(v)) for v in values]

    for e, ident in zip(graph["edges"], ids, strict=True):
        record = net.segments[ident]
        for key, field in (("a", "start_node"), ("b", "end_node")):
            expected = node_ids.setdefault(e[key], record[field])
            assert expected == record[field], (
                "A shared graph node split in serialization"
            )
            assert net.nodes[expected]["position"] == f32(graph["nodes"][e[key]]["xyz"])
            assert ident in net.nodes[expected]["segments"]
        assert record["start_direction"] == f32(e["start_dir"])
        assert record["end_direction"] == f32(e["end_dir"])
        assert record["lanes"] == 0
        prefabs[net.prefabs.names[net.segment_prefab[ident]]] += 1
    assert len(node_ids) == len(graph["nodes"])
    assert len(set(node_ids.values())) == len(node_ids), "Distinct graph nodes merged"
    for ident in node_ids.values():
        building = net.nodes[ident]["building"]
        assert not building or building in buildings.ids
    represented = {way for e in graph["edges"] for way in e.get("osm_ways", [])}
    assert len(represented) == hydro["highway_report"]["represented_osm_ways"]
    return {
        "crp_sha256": generation["package"]["sha256"],
        "nodes": len(node_ids),
        "segments": len(ids),
        "represented_osm_ways": len(represented),
        "prefabs": dict(sorted(prefabs.items())),
        "graph_records_exact": True,
        "manager_sections_byte_exact": True,
        "native_qualified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.prepared, args.source), indent=2))
