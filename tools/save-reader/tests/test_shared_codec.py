"""One NetManager/BuildingManager codec for maps and saves (PL-982).

The reader decodes these sections with `tools/map-factory/netcodec.py`, the
codec the map writer encodes with. A game save re-encodes to the game's own
bytes, so reading and writing cannot drift apart.
"""

import gzip
from pathlib import Path

import pytest

from cs1save.codec import netcodec
from cs1save.package import read_package
from cs1save.save import begin_tag, read_save

HERE = Path(__file__).parent / "fixtures" / "game-check"


@pytest.fixture(scope="module")
def city(tmp_path_factory):
    path = tmp_path_factory.mktemp("codec") / "testcity.crp"
    path.write_bytes(gzip.decompress((HERE / "testcity.crp.gz").read_bytes()))
    raw = path.read_bytes()
    _, assets = read_package(raw)
    asset = next(a for a in assets if a["kind"] == 52)
    return read_save(path), raw[asset["offset"] : asset["offset"] + asset["size"]]


def test_codec_is_the_map_writers():
    assert Path(netcodec.__file__).resolve() == (Path(__file__).parents[2] / "map-factory" / "netcodec.py").resolve()


@pytest.mark.parametrize("name", ["NetManager", "BuildingManager"])
def test_game_sections_reencode_to_the_games_bytes(city, name):
    save, data = city
    tag, end = save.blocks[name]
    start = tag + len(begin_tag(name))
    section = {"NetManager": netcodec.NetSection, "BuildingManager": netcodec.BuildingSection}[name](data, start)
    assert section.end == end - 2
    assert section.encode() == data[start : end - 2]
    assert sum(section.guide_counts) > 0  # a game, not a map: guides and milestones present
