"""Shared frame and paths for the PL-900 LoD2 pilot.

Working CRS is EPSG:6542 (NAD83(2011) / North Carolina, metres): the state plane the
county publishes in, in metres, so Roofer gets true-scale metric input. The local frame
is the pixel-asheville one: x east, z south, metres from the scene origin downtown.
Heights are NAVD88 metres.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FTUS = 0.3048006096012192
# pixel-asheville / north-v2 region: EPSG:2264 bounds for local x in [-3000, 3000],
# z in [-5000, 3000] (asheville-geometry/regions/north-v2/region.json).
_W, _S = 934130.9644820734, 680537.4966984562
E0 = _W * FTUS + 3000.0  # EPSG:6542 easting of local x = 0
N0 = _S * FTUS + 3000.0  # EPSG:6542 northing of local z = 0
WORK_EPSG = 6542
CLASSES = "rescue"  # how building points are prepared (reconstruct.py); PL-900 froze "promote"
FIT_EPOCH = "2017"  # folder name of the cloud the reconstruction is fitted to
# Another place (second_city.py): LOD2_FRAME="<easting>,<northing>,<epsg>,<epoch>" moves the frame.
if os.environ.get("LOD2_FRAME"):
    _e, _n, _epsg, FIT_EPOCH = os.environ["LOD2_FRAME"].split(",")
    E0, N0, WORK_EPSG = float(_e), float(_n), int(_epsg)

EXP = Path(os.environ.get("LOD2_EXP", Path.home() / "experiments" / "PL-900-lod2-pilot"))
EPT_2017 = "https://usgs-lidar-public.s3.amazonaws.com/NC_Phase5_Buncombe_2017/ept.json"
FOOTPRINTS = (
    "https://gis.ashevillenc.gov/server/rest/services/Property/"
    "BuncombeCountyBuildingFootprints2024/FeatureServer/0"
)
ORTHO_2025 = (
    "https://services.nconemap.gov/secure/rest/services/Imagery/"
    "Orthoimagery_Helene_2025/ImageServer"
)


def to_local(e: float, n: float) -> tuple[float, float]:
    """EPSG:6542 metres -> local (x east, z south)."""
    return e - E0, -(n - N0)


def to_work(x: float, z: float) -> tuple[float, float]:
    return x + E0, N0 - z


def read_json(path: Path):
    return json.loads(Path(path).read_text())


def write_json(path: Path, obj, indent: int | None = 1) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=indent))
