"""The public PL-848 template map in map-factory: every manager decodes."""

from pathlib import Path

import numpy as np
import pytest

from cs1save.save import read_save

TEMPLATE = Path(__file__).resolve().parents[2] / "map-factory" / "templates" / "native-corridors.crp"


@pytest.fixture(scope="module")
def template():
    if not TEMPLATE.exists():
        pytest.skip("map-factory template not present")
    return read_save(TEMPLATE)


def test_every_manager_decodes_or_is_tag_bounded(template):
    # Managers this reader doesn't decode are bounded by their tags.
    assert set(template.data) >= {
        "GameAreaManager",
        "TerrainManager",
        "WaterSimulation",
        "InstanceManager",
        "NetManager",
        "BuildingManager",
        "ZoneManager",
        "TreeManager",
        "EconomyManager",
        "DistrictManager",
        "TransportManager",
    }
    blocks = [template.blocks[name] for name in template.manager_order]
    for (_, end), (start, _) in zip(blocks, blocks[1:]):
        assert end == start


def test_template_contents(template):
    net = template.data["NetManager"]
    assert len(net["node_ids"]) == 288 and len(net["segment_ids"]) == 285
    b = template.data["BuildingManager"]
    assert sorted(set(b["prefab"])) == [
        "HighwayBridgePillar",
        "RailwayElevatedPillar",
        "Road Connection",
        "Train Connection",
    ]
    assert len(template.data["ZoneManager"]["block_ids"]) == 0
    assert template.metadata["type"] == "MapMetaData"
    # segments connect decoded nodes
    nodes = set(net["node_ids"].tolist())
    assert set(net["segment_start_node"].tolist()) <= nodes
    assert set(net["segment_end_node"].tolist()) <= nodes
    raw = template.data["TerrainManager"]["raw_heights"]
    assert raw.shape == (1081, 1081) and raw.max() > 0
    assert np.all(np.abs(net["node_position"][:, [0, 2]]) <= 8640.01)
