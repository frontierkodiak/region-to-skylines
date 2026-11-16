"""Real player saves, kept out of the repository.

Set CS1SAVE_PRIVATE_SAVES to save paths separated by the OS path separator
(two saves of different cities). Skipped when it is unset.
"""

import os
from pathlib import Path

import pytest

from cs1save.save import read_save

PATHS = [p for p in os.environ.get("CS1SAVE_PRIVATE_SAVES", "").split(os.pathsep) if p]


@pytest.fixture(scope="module", params=PATHS or [None], ids=lambda p: Path(p).stem if p else "unset")
def save(request):
    if not request.param:
        pytest.skip("CS1SAVE_PRIVATE_SAVES not set")
    path = Path(request.param)
    if not path.exists():
        pytest.skip(f"{path} missing")
    return read_save(path)


def test_whole_stream_accounted_for(save):
    decoded = set(save.data)
    assert {"NetManager", "BuildingManager", "ZoneManager", "TreeManager", "DistrictManager"} <= decoded
    order = save.manager_order
    for a, b in zip(order, order[1:]):
        assert save.blocks[a][1] == save.blocks[b][0]


def test_population_agrees_with_metadata(save):
    population = int(save.metadata["population"].replace(",", ""))
    assert save.data["DistrictManager"]["city"]["population"] == population


def test_network_and_buildings_are_consistent(save):
    net = save.data["NetManager"]
    nodes = set(net["node_ids"].tolist())
    assert set(net["segment_start_node"].tolist()) <= nodes
    assert set(net["segment_end_node"].tolist()) <= nodes
    assert all(net["segment_prefab"]) and all(net["node_prefab"])
    b = save.data["BuildingManager"]
    assert all(b["prefab"]) and len(b["prefab"]) == len(b["ids"])
    # outside-connection buildings sit just past the 8,640 m map edge
    inside = [abs(p[0]) <= 8640.01 and abs(p[2]) <= 8640.01 for p in b["position"].tolist()]
    assert all(ok or name.endswith("Connection") for ok, name in zip(inside, b["prefab"]))
    assert (abs(b["position"][:, [0, 2]]) <= 8700).all()
    # each segment id is listed by both of its nodes
    by_node = dict(zip(net["node_ids"].tolist(), net["node_segments"]))
    for sid, a, c in zip(
        net["segment_ids"].tolist(), net["segment_start_node"].tolist(), net["segment_end_node"].tolist()
    ):
        assert sid in by_node[a] and sid in by_node[c]
