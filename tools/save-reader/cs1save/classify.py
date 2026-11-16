"""Classify network and building prefabs.

A save stores prefab names, not their ItemClass. The packaged catalog
(data/prefabs-1.21.1-f9.json, dumped from the running game by cs1-harness
`dump_prefabs`: base game and the DLC blade's copy loads) gives the game's own
service, sub-service and level, marked `"source": "game"`. The name rules below
cover prefabs it doesn't know, such as mod networks and Workshop assets, and
mark them `"source": "name"`.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_CATALOG = {"net": {}, "building": {}}

ELEVATIONS = [(" Elevated", "elevated"), (" Bridge", "bridge"), (" Slope", "slope"), (" Tunnel", "tunnel")]

NET_RULES = [
    # category, level, pattern (searched in the name without its elevation suffix)
    (
        "virtual",
        None,
        r"\bLine$|Airplane (Connection )?Path|Ship (Connection )?Path|^Cargo Connection$|Pedestrian Connection",
    ),
    ("rail", None, r"^Train (Track|Station Track|Cargo Track|Connection Track)"),
    ("metro", None, r"^Metro"),
    ("highway", None, r"Highway|HighwayRamp"),
    ("road", "large", r"^Large |Oneway4L|Six-Lane|Eight-Lane"),
    ("road", "medium", r"^Medium |Small 4 Lane Road|Oneway3L|Four-Lane"),
    (
        "road",
        "small",
        r"^Basic Road|BasicRoadMdn|^Small Road|^Small Avenue|^Oneway Road|One-Lane|PlainStreet|^Gravel Road|Harbor Road|Two-Lane",
    ),
    ("path", None, r"Pedestrian|[Pp]ath\b|[Ww]alkway"),
    ("water", None, r"^Canal|Flood Wall|Ship Dock|Quay"),
    ("airport", None, r"^Airplane (Runway|Taxiway|Stop)"),
    ("utility", None, r"Pipe|Power Line|Heating"),
    ("fence", None, r"Fence|Wall|Barricade|Barrier|Railing"),
]

BUILDING_RULES = [
    ("pillar", r"Pillar"),
    ("connection", r"Connection$"),
    (
        "decoration",
        r"^(Rock|Boulder|Cliff|Cave) |^Castle Ruins|^Pier Ruins|^Ship Wreck|^Abandoned (Lighthouse|Factory|Building)|Wildlife Spawn|ChirpX Empty Area",
    ),
    ("industry", r"^(Forestry|Oil|Ore|Agricultural|Farming)|Factory|OreCrusher|cargoyard|agricultural_building"),
    ("police", r"[Pp]olice"),
    ("fire", r"Fire[ _]Station|firehouse"),
    ("health", r"Hospital|[Hh]ospital|Health|Eldercare|medical|Clinic"),
    ("deathcare", r"Crematory|Cemetery"),
    ("education", r"School|school|University|Library|Campus"),
    ("electricity", r"Power Plant|Combustion Plant|Wind Turbine|Solar|Dam$|Nuclear"),
    ("water_service", r"^Water |Water Tower|Sewage"),
    ("garbage", r"Landfill|Incinerat|Recycl"),
    (
        "transport",
        r"Depot|Metro (Entrance|Station)|Overground Metro Station|Train Station|^Harbor$|Cargo (Harbor|Center)|^Airport$|Airport Apron|Bus Station|Transport Tower|Taxi|Tram",
    ),
    (
        "monument",
        r"ChirpX|Statue|Arc de Triomphe|Brandenburg|Colossal Offices|ParadoxPlaza|Fountain of|Modern Art|ScienceCenter|Trash Mall|Friendly Neighborhood|Transport Park|amsterdam_palace|gherkin|london_eye|Botanical|Tropical Garden|JapaneseGarden|Lazaret|arena|cinema|shopping_center|Lazaret|City Hall|Birthday|Balloon",
    ),
    ("park", r"Park|Plaza|Playground|Garden|Court|MerryGoRound|bouncer_castle|Decoration|dog-park|Basketball"),
    ("growable", r"^[HL]\d[ _]|^Future Store|^Game Store"),
]


CATALOG = Path(__file__).parent / "data" / "prefabs-1.21.1-f9.json"


def load_catalog(path):
    """Use a prefab catalog dumped from the running game (cs1-harness dump)."""
    data = json.loads(open(path).read())
    for kind in ("net", "building"):
        _CATALOG[kind] = {p["name"]: p for p in data.get(kind + "s", [])}
    net.cache_clear()
    building.cache_clear()


def _strip_elevation(name):
    for suffix, label in ELEVATIONS:
        if name.endswith(suffix) or suffix + " " in name:
            return name.replace(suffix, ""), label
    return name, "ground"


@lru_cache(maxsize=None)
def net(name):
    base, elevation = _strip_elevation(_display(name))
    entry = _CATALOG["net"].get(name)
    for category, level, pattern in NET_RULES:
        if re.search(pattern, base):
            out = {"category": category, "level": level, "elevation": elevation, "source": "name"}
            break
    else:
        out = {"category": "other", "level": None, "elevation": elevation, "source": "name"}
    if entry:
        out.update(_net_from_catalog(entry, out))
    return out


@lru_cache(maxsize=None)
def building(name):
    display = _display(name)
    entry = _CATALOG["building"].get(name)
    for service, pattern in BUILDING_RULES:
        if re.search(pattern, display):
            out = {"service": service, "zone": None, "source": "name"}
            break
    else:
        out = {"service": "other", "zone": None, "source": "name"}
    if entry:
        out.update(_building_from_catalog(entry))
    return out


def _display(name):
    """Workshop assets are '<id>.<name>_Data'; keep the readable part."""
    m = re.match(r"^\d+\.(.*?)(_Data)?$", name)
    return m.group(1) if m else name


SERVICE_NAMES = {
    "Residential": "growable",
    "Commercial": "growable",
    "Industrial": "growable",
    "Office": "growable",
    "PoliceDepartment": "police",
    "FireDepartment": "fire",
    "HealthCare": "health",
    "Education": "education",
    "Electricity": "electricity",
    "Water": "water_service",
    "Garbage": "garbage",
    "PublicTransport": "transport",
    "Beautification": "park",
    "Monument": "monument",
    "Road": "road",
    "Tourism": "park",
    "Disaster": "disaster",
    "Natural": "decoration",
    "PlayerIndustry": "industry",
    "PlayerEducation": "education",
    "Museums": "monument",
    "VarsitySports": "park",
    "Fishing": "industry",
    "Hotel": "growable",
}
ZONED = {
    "ResidentialLow": "ResidentialLow",
    "ResidentialHigh": "ResidentialHigh",
    "ResidentialLowEco": "ResidentialLow",
    "ResidentialHighEco": "ResidentialHigh",
    "ResidentialWallToWall": "ResidentialHigh",
    "CommercialLow": "CommercialLow",
    "CommercialHigh": "CommercialHigh",
    "CommercialLeisure": "CommercialLow",
    "CommercialTourist": "CommercialLow",
    "CommercialEco": "CommercialLow",
    "CommercialWallToWall": "CommercialHigh",
    "IndustrialGeneric": "Industrial",
    "IndustrialForestry": "Industrial",
    "IndustrialFarming": "Industrial",
    "IndustrialOil": "Industrial",
    "IndustrialOre": "Industrial",
    "OfficeGeneric": "Office",
    "OfficeHightech": "Office",
    "OfficeWallToWall": "Office",
    "OfficeFinancial": "Office",
}


def _building_from_catalog(entry):
    service = entry.get("service")
    sub = entry.get("sub_service")
    ai = entry.get("ai") or ""
    out = {"source": "game", "class": entry.get("class"), "ai": ai, "zone": None}
    out["service"] = SERVICE_NAMES.get(service, (service or "other").lower())
    if ai == "DecorationBuildingAI":
        out["service"] = "decoration"
    elif ai == "OutsideConnectionAI":
        out["service"] = "connection"
    elif ai == "TollBoothAI":
        out["service"] = "transport"
    elif service == "Road" or "Pillar" in entry.get("name", ""):
        out["service"] = "pillar"  # road, rail and metro bridge and ramp pillars
    if service in ("Residential", "Commercial", "Industrial", "Office"):
        out["zone"] = ZONED.get(sub, service)
    return out


ROAD_LEVELS = {"Level1": "small", "Level2": "small", "Level3": "medium", "Level4": "large"}


def _net_from_catalog(entry, by_name):
    service = entry.get("service")
    sub = entry.get("sub_service")
    level = entry.get("level")
    out = {"source": "game", "class": entry.get("class"), "ai": entry.get("ai")}
    if by_name["category"] == "virtual" or (entry.get("ai") or "").endswith("LineAI"):
        out["category"], out["level"] = "virtual", None
    elif service == "Road":
        if level == "Level5" or "Highway" in (entry.get("class") or ""):
            out["category"], out["level"] = "highway", None
        else:
            out["category"], out["level"] = "road", ROAD_LEVELS.get(level, by_name["level"])
    elif service == "PublicTransport":
        rail = {"PublicTransportTrain": "rail", "PublicTransportMetro": "metro"}
        out["category"] = rail.get(sub, by_name["category"])
    elif service == "Beautification":
        out["category"] = "fence" if by_name["category"] == "fence" else "path"
    return out


if CATALOG.exists():
    load_catalog(CATALOG)
