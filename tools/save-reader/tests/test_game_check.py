"""The reader against the game's own view of one save.

`fixtures/game-check/testcity.crp.gz` is a city the cs1-harness built on the stock
Green Plains map (scenario test-city, grown for about six game minutes, then paused
and saved by the game). `game.json.gz` is what the running game held at that moment,
written by the harness's `dump_city` op right after the save: every node, segment,
building and zone block by buffer id, and the trees as a count and a digest.
"""

import gzip
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from cs1save.save import read_save

HERE = Path(__file__).parent / "fixtures" / "game-check"


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    path = tmp_path_factory.mktemp("game-check") / "testcity.crp"
    with gzip.open(HERE / "testcity.crp.gz", "rb") as src, open(path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    game = json.loads(gzip.open(HERE / "game.json.gz", "rt").read())
    return read_save(path), game


def by_id(table):
    return {i: k for k, i in enumerate(table["id"])}


def test_same_moment(pair):
    save, game = pair
    assert save.simulation["frame_index"] == game["frame"]
    assert save.data["DistrictManager"]["city"]["population"] == game["population"] == 409


def test_nodes(pair):
    save, game = pair
    net, g = save.data["NetManager"], game["nodes"]
    assert sorted(net["node_ids"].tolist()) == sorted(g["id"])
    idx = by_id(g)
    for k, nid in enumerate(net["node_ids"].tolist()):
        j = idx[nid]
        assert net["node_prefab"][k] == g["prefab"][j]
        assert int(net["node_flags"][k]) == g["flags"][j]
        assert np.allclose(net["node_position"][k], [g["x"][j], g["y"][j], g["z"][j]], atol=1e-4)


def test_segments(pair):
    save, game = pair
    net, g = save.data["NetManager"], game["segments"]
    assert sorted(net["segment_ids"].tolist()) == sorted(g["id"])
    idx = by_id(g)
    for k, sid in enumerate(net["segment_ids"].tolist()):
        j = idx[sid]
        assert net["segment_prefab"][k] == g["prefab"][j]
        assert int(net["segment_flags"][k]) == g["flags"][j]
        assert int(net["segment_start_node"][k]) == g["start_node"][j]
        assert int(net["segment_end_node"][k]) == g["end_node"][j]


def test_buildings(pair):
    save, game = pair
    b, g = save.data["BuildingManager"], game["buildings"]
    assert sorted(b["ids"].tolist()) == sorted(g["id"])
    idx = by_id(g)
    for k, bid in enumerate(b["ids"].tolist()):
        j = idx[bid]
        assert b["prefab"][k] == g["prefab"][j]
        assert int(b["flags"][k]) == g["flags"][j]
        assert np.allclose(b["position"][k], [g["x"][j], g["y"][j], g["z"][j]], atol=1e-4)
        assert abs(float(b["angle"][k]) - g["angle"][j]) < 1e-6
        assert (int(b["level"][k]), int(b["width"][k]), int(b["length"][k])) == (
            g["level"][j],
            g["width"][j],
            g["length"][j],
        )


def test_zone_blocks(pair):
    save, game = pair
    z, g = save.data["ZoneManager"], game["zone_blocks"]
    assert sorted(z["block_ids"].tolist()) == sorted(g["id"])
    idx = by_id(g)
    for k, bid in enumerate(z["block_ids"].tolist()):
        j, rec = idx[bid], z["blocks"][k]
        assert int(z["block_flags"][k]) == g["flags"][j]
        for field in ("valid", "zone1", "zone2"):
            assert int(rec[field]) == int(g[field][j])
        assert np.allclose(rec["position"], [g["x"][j], g["y"][j], g["z"][j]], atol=1e-4)


def test_trees(pair):
    save, game = pair
    t = save.data["TreeManager"]
    names = [t["prefab_names"][i] for i in t["prefab_index"]]
    rows = zip(t["ids"].tolist(), names, t["pos_x"].tolist(), t["pos_z"].tolist())
    digest = hashlib.sha256("\n".join(f"{i},{p},{x},{z}" for i, p, x, z in rows).encode()).hexdigest()
    assert len(t["ids"]) == game["trees"]["count"]
    assert digest == game["trees"]["sha256_id_prefab_posx_posz"]
