"""Compile a validated polli.place/0 directory into map-factory inputs and a map.

Run with the real polli-place-model package supplied by uv --with. This module
is a target adapter, not an importer, graph builder, or alternative place model.
"""

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import shapely
from landcover import lonlat
from place_model import SCHEMAS, read_grid, read_manifest, read_table, validate
from place_model.nhd import canonical_id
from pyproj import Transformer
from region import SIZE
from scipy.ndimage import map_coordinates

ROOT = Path(__file__).resolve().parent
EXTENT = (SIZE - 1) * 16.0
LAND_SIZE = 1728


def write_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False) + "\n")


class Frame:
    """Canonical local metres -> source CRS/geography or north-positive game."""

    def __init__(self, manifest):
        self.manifest = manifest
        self.frame = manifest["frame"]
        west, north, east, south = manifest["extent"]
        self.center = np.array([(west + east) / 2, (north + south) / 2])
        # A cell grid's edge is not an elevation sample. Inscribe inside its
        # sample support, rather than extrapolating the outer half cells.
        desc = manifest["layers"]["terrain"]
        bounds = np.asarray(desc["bounds"], float)
        if desc["sampling"] == "cell":
            half_cell = (bounds[2:] - bounds[:2]) / [desc["cols"], desc["rows"]] / 2
            bounds[:2] += half_cell
            bounds[2:] -= half_cell
        self.side = float(
            2 * min(*(self.center - bounds[:2]), *(bounds[2:] - self.center))
        )
        if self.side <= 0:
            raise ValueError(
                "Terrain sample support cannot cover an extent-centred square"
            )
        self.crop = np.r_[self.center - self.side / 2, self.center + self.side / 2]
        self.to_wgs84 = Transformer.from_crs(
            self.frame["source_crs"], 4326, always_xy=True
        )
        center_lon, center_lat = self.geographic(*self.center)
        self.sq = {
            "slug": manifest["id"],
            "name": manifest["title"],
            "lon": center_lon,
            "lat": center_lat,
            "rotation": 0,
            "scale": self.side / EXTENT,
        }

    def geographic(self, x, z):
        unit = self.frame["horizontal_unit_metres"]
        east, north = self.frame["origin"]
        return self.to_wgs84.transform(
            east + np.asarray(x) / unit, north - np.asarray(z) / unit
        )

    def game(self, x, z):
        return (
            (np.asarray(x) - self.center[0]) * EXTENT / self.side,
            (self.center[1] - np.asarray(z)) * EXTENT / self.side,
        )

    def points(self, coords):
        x, z = np.asarray(coords)[:, :2].T
        # Compatibility lon/lat is the exact inverse of prepare.pixel, not a
        # second geographic projection. Real crop geography uses the CRS above.
        lon, lat = lonlat(self.sq, *self.game(x, z))
        return np.column_stack([lon, lat]).tolist()

    def report(self):
        w, n, e, s = self.crop
        corners = np.array([[w, n], [e, n], [e, s], [w, s], [w, n]])
        longitude, latitude = self.geographic(*corners.T)
        return {
            "schema": "polli.place/0",
            "id": self.manifest["id"],
            "access": self.manifest["access"],
            "frame": self.frame,
            "sources": self.manifest["sources"],
            "extent_local_metres": self.manifest["extent"],
            "crop_local_metres": self.crop.tolist(),
            "crop_corners_wgs84": np.column_stack([longitude, latitude]).tolist(),
            "source_side_metres": self.side,
            "game_side_metres": EXTENT,
            "game_metres_per_source_metre": EXTENT / self.side,
            "source_metres_per_game_metre": self.side / EXTENT,
            "terrain_sampling": self.manifest["layers"]["terrain"]["sampling"],
            "target_axes": ["east", "up", "north"],
            "target_geometry_coordinates": "compatibility lon/lat: inverse prepare.pixel; not survey geography",
            "vertical_datum": self.frame["vertical_datum"],
            "elevations": "absolute source metres; presentation elevation_origin_metres is NOT subtracted",
            "roads": "all source IDs, full lines and connector linear references retained, including outside crop; no native real-road serialization (PL-1066)",
            "water": "source kind/height/properties retained; existing carving and hydrology policy determines target levels, not source inferred DEM water heights",
            "in_game_verified": False,
        }


def sample_grid(values, desc, crop, size, *, cells=False, categorical=False):
    """Resample declared vertex/cell grids without sampling uncovered terrain."""
    w, n, e, s = crop
    fraction = (np.arange(size) + 0.5) / size if cells else np.linspace(0, 1, size)
    x, z = np.meshgrid(w + fraction * (e - w), n + fraction * (s - n))
    bounds = desc["bounds"]
    dimensions = np.array([desc["cols"], desc["rows"]])
    span = np.array(bounds[2:]) - bounds[:2]
    if (span <= 0).any() or min(dimensions) < 2:
        raise ValueError(
            "Target resampling requires at least two rows/columns and positive grid bounds"
        )
    indices = [x, z]
    for axis in range(2):
        count = dimensions[axis] - (desc["sampling"] == "vertex")
        indices[axis] = (indices[axis] - bounds[axis]) / span[axis] * count
        if desc["sampling"] == "cell":
            indices[axis] -= 0.5
        lo, hi = float(indices[axis].min()), float(indices[axis].max())
        margin = 0.5 if categorical and desc["sampling"] == "cell" else 0
        if lo < -margin - 1e-8 or hi > dimensions[axis] - 1 + margin + 1e-8:
            raise ValueError("Requested samples exceed declared grid sample coverage")
    return map_coordinates(
        values, [indices[1], indices[0]], order=0 if categorical else 1, mode="nearest"
    )


def source_properties(place, manifest, name):
    if name not in manifest["layers"]:
        return {}
    return {
        r["id"]: json.loads(r["properties"])
        for r in read_table(place, name).to_pylist()
    }


def feature(row, properties):
    return {
        **{k: v for k, v in row.items() if k != "geometry"},
        "sourceFeature": {"id": row["id"], "properties": properties},
    }


def water_visibility(row, properties):
    """Translate explicit source tunnel evidence; a negative level alone is not it."""
    tags = dict(properties.get("source_tags") or [])
    tunnel = properties.get("tunnel", tags.get("tunnel"))
    brunnel = row.get("brunnel", properties.get("brunnel"))
    location = properties.get("location", tags.get("location"))
    underground = (
        brunnel == "tunnel"
        or row.get("tunnel") is True
        or tunnel is True
        or tunnel in ("yes", "culvert", "building_passage")
        or location == "underground"
        or row["kind"] == "underground"
    )
    return "tunnel" if underground else brunnel


def compile_geometry(place, manifest, frame):
    if "transportation_semantics" not in manifest["layers"]:
        raise ValueError(
            "Place lacks transportation_semantics; rebuild it with the shared model's transportation-semantics command"
        )
    semantics = {
        row["id"]: row
        for row in read_table(place, "transportation_semantics").to_pylist()
    }
    road_properties = source_properties(place, manifest, "source_segment")
    water_properties = source_properties(place, manifest, "source_water")
    roads = []
    for row in read_table(place, "transportation_segments").to_pylist():
        semantic = semantics[row["id"]]
        target_class = semantic["class"]
        if semantic["mode"] == "rail" and target_class == "standard_gauge":
            target_class = "rail"
        roads.append(
            {
                **feature(row, road_properties.get(row["id"], {})),
                "canonical_class": row["class"],
                "transportation_semantics": semantic,
                "class": target_class,
                "pts": frame.points(shapely.from_wkb(row["geometry"]).coords),
            }
        )
    connectors = []
    for row in read_table(place, "transportation_connectors").to_pylist():
        x, z = frame.game(row["x"], row["z"])
        connectors.append({**row, "x": float(x), "z": float(z)})
    geometry = {
        "sq": frame.sq,
        "roads": roads,
        "roadConnectors": connectors,
        **{
            k: []
            for k in [
                "rivers",
                "streams",
                "riverAreas",
                "lakes",
                "oceans",
                "undergroundWaterways",
                "unmodeledHydrography",
            ]
        },
        "placeInput": frame.report(),
    }
    for row in read_table(place, "hydrography").to_pylist():
        props = water_properties.get(row["id"], {})
        entry = feature(row, props)
        entry["brunnel"] = water_visibility(row, props)
        # surface_water checks brunnel against sourceFeature.properties if set.
        if "brunnel" in props and props["brunnel"] != entry["brunnel"]:
            raise ValueError(f"Conflicting water visibility for {row['id']}")
        names = props.get("names") or {}
        entry["name"] = props.get("name") or names.get("primary") or row["id"]
        geom = shapely.from_wkb(row["geometry"])
        parts = list(geom.geoms) if geom.geom_type.startswith("Multi") else [geom]
        for part_index, part in enumerate(parts):
            item = {**entry, "part": part_index}
            kind = row["kind"]
            if part.geom_type == "LineString":
                item["pts"] = frame.points(part.coords)
                if kind not in {
                    "river",
                    "stream",
                    "canal",
                    "ditch",
                    "drain",
                    "underground",
                }:
                    raise ValueError(
                        f"Hydrography {row['id']}: undeclared line role {kind!r}; needs canonical watercourse kind"
                    )
                item["class"] = "river" if kind == "river" else "stream"
                field = (
                    "undergroundWaterways"
                    if item["brunnel"] == "tunnel"
                    else "rivers"
                    if kind == "river"
                    else "streams"
                )
            elif part.geom_type == "Polygon":
                item["rings"] = [
                    frame.points(r.coords) for r in [part.exterior, *part.interiors]
                ]
                if item["brunnel"] == "tunnel" or kind in {"swimming_pool", "shoal"}:
                    field = "unmodeledHydrography"
                    item["exclusionReason"] = (
                        "No natural surface-water codec for underground polygons, swimming pools or shoal landforms"
                    )
                elif kind == "ocean":
                    field = "oceans"
                elif kind in {"lake", "pond", "reservoir", "basin"}:
                    field = "lakes"
                elif kind in {"river", "canal", "water", "surface", "bay"}:
                    # An unspecified surface footprint is not a lake and does
                    # not license reconstructing a river centreline/flow graph.
                    field = "riverAreas"
                else:
                    raise ValueError(
                        f"Hydrography {row['id']}: undeclared polygon role {kind!r}; needs canonical waterbody kind"
                    )
            else:
                raise ValueError(
                    f"Hydrography {row['id']}: unsupported {part.geom_type}; needs explicit line/area semantics"
                )
            geometry[field].append(item)
    if "hydrography_flowpaths" in manifest["layers"]:
        body_ids = {
            row["id"] for row in read_table(place, "hydrography_flowbodies").to_pylist()
        }
        path_properties = {
            canonical_id("flowline", ident): props
            for ident, props in source_properties(
                place, manifest, "source_nhd_flowline"
            ).items()
        }
        for row in read_table(place, "hydrography_flowpaths").to_pylist():
            # Validation owns body role/FK/direction. Preserve the full source
            # path and order; do not infer connections between path endpoints.
            if row["body_id"] not in body_ids:
                raise ValueError("Canonical flowpath lacks its river body")
            geom = shapely.from_wkb(row["geometry"])
            parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
            for part_index, part in enumerate(parts):
                geometry["rivers"].append(
                    {
                        **feature(row, path_properties.get(row["id"], {})),
                        "name": row["name"] or row["body_id"],
                        "kind": "river",
                        "class": "river",
                        "part": part_index,
                        "pts": frame.points(part.coords),
                    }
                )
    geometry["placeInput"]["water_limitations"] = [
        "Generic water/surface/bay polygons retain area only; no lake flattening, inferred centerline, hydraulic connectivity or sustained river supply.",
        "Underground polygons and swimming pools are retained as unmodeledHydrography, not natural surface sources.",
        "Scoped road flags and level rules are source properties, not whole-line grade instructions; native serialization belongs to PL-1066.",
        "Canonical river flowpaths retain body ID and source direction, not measured water stage or an inferred hydraulic network. Existing target hydrology still controls levels and supply.",
    ]
    return geometry


def preprocess(place, output, *, terrain_policy="legacy"):
    """Validate first, then return input PNG, geometry JSON, banks and landcover paths."""
    place, output = Path(place), Path(output)
    if terrain_policy not in {"legacy", "source-faithful-v2"}:
        raise ValueError("Unknown terrain policy")
    if not {"transportation_semantics", "hydrography_flowpaths"} <= SCHEMAS.keys():
        raise ValueError(
            "This reader needs polli-place-model >=0.3 with transportation semantics and river flowpaths"
        )
    validation = validate(place)
    manifest = read_manifest(place)
    frame = Frame(manifest)
    terrain = sample_grid(
        read_grid(place, "terrain"), manifest["layers"]["terrain"], frame.crop, SIZE
    )
    land = sample_grid(
        read_grid(place, "landcover"),
        manifest["layers"]["landcover"],
        frame.crop,
        LAND_SIZE,
        cells=True,
        categorical=True,
    )
    if (
        manifest["layers"]["landcover"]["dtype"] != "uint8"
        or not np.isin(land, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]).all()
    ):
        raise ValueError(
            "Landcover needs declared ESA WorldCover uint8 codes for the existing resource codec"
        )
    geometry = compile_geometry(place, manifest, frame)
    geometry["placeInput"]["validation"] = validation
    geometry["placeInput"]["manifest_sha256"] = hashlib.sha256(
        (place / "place.json").read_bytes()
    ).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="place-codecs-") as temporary:
        work = Path(temporary)
        terrain.astype("<f8").tofile(work / "elevation.f64")
        write_json(work / "geometry.json", geometry)
        subprocess.run(
            ["node", str(ROOT / "place_input.mjs"), str(work), terrain_policy],
            check=True,
        )
        for name in ["input.png", "geometry.json", "banks.f32"]:
            shutil.copyfile(work / name, output / name)
    (output / "landcover.u8.gz").write_bytes(
        gzip.compress(land.astype("u1").tobytes(), mtime=0)
    )
    return tuple(
        output / name
        for name in ["input.png", "geometry.json", "banks.f32", "landcover.u8.gz"]
    )


def export(
    place, output, *, inputs_only=False, allow_water_risk=False, terrain_policy="legacy"
):
    """Use the existing generator and water-risk decision; never install a map."""
    from generate import generate
    from water_risk import assess

    output = Path(output)
    # Refuse mixing fresh inputs with a previously exported package/receipt.
    if output.exists() and any(output.iterdir()):
        raise ValueError("OUTPUT must be empty; choose a new directory")
    png, geometry, banks, landcover = preprocess(
        place, output / "inputs", terrain_policy=terrain_policy
    )
    report = {
        "place_input": json.loads(geometry.read_text())["placeInput"],
        "inputs_only": inputs_only,
        "in_game_verified": False,
    }
    if inputs_only:
        write_json(output / "place-input.json", report)
        return report, 0
    with tempfile.TemporaryDirectory(prefix="place-generate-") as temporary:
        work = Path(temporary)
        receipt = generate(png, geometry, work, banks=banks, landcover=landcover)
        risk = assess(
            *(
                np.fromfile(work / f"{name}.u16", "<u2").reshape(SIZE, SIZE)
                for name in ["terrain", "water"]
            ),
            json.loads((work / "hydrology.json").read_text()),
        )
        write_json(work / "water-risk.json", risk)
        decision = json.loads(
            subprocess.check_output(
                [
                    "node",
                    str(ROOT / "place_input.mjs"),
                    "--water-risk",
                    str(work / "water-risk.json"),
                ],
                text=True,
            )
        )
        accepted = decision["action"] == "download" or (
            decision["action"] == "review" and allow_water_risk
        )
        crp = (
            (output / "generated" / Path(receipt["package"]["output"]).name).resolve()
            if accepted
            else None
        )
        receipt["package"]["output"] = str(crp) if crp else None
        report.update(
            generation=receipt,
            water_risk=risk,
            water_risk_decision=decision,
            exported=accepted,
        )
        if accepted:
            # The generator ran in quarantine until its water check completed.
            # Final receipts must not point at that now-ephemeral directory.
            write_json(work / "generation.json", receipt)
            resources = json.loads((work / "resources.json").read_text())
            resources["package"]["output"] = str(crp)
            write_json(work / "resources.json", resources)
            shutil.copytree(work, output / "generated")
    write_json(output / "place-input.json", report)
    return report, 0 if accepted else 5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("place", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--inputs-only",
        action="store_true",
        help="Compile codecs without generating a CRP",
    )
    parser.add_argument(
        "--terrain-policy",
        choices=["legacy", "source-faithful-v2"],
        default="legacy",
        help="Opt-in terrain experiment; legacy remains the shipping byte contract",
    )
    parser.add_argument(
        "--allow-water-risk",
        action="store_true",
        help="Only after accepting this square's reported water risks; cannot override unavailable/invalid checks",
    )
    args = parser.parse_args()
    try:
        report, code = export(**vars(args))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"place_input: {exc}\n")
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
