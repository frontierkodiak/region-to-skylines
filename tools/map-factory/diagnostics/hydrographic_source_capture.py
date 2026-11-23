"""Bounded public Geofabric source read on the EXISTING coastal development square.

Preserve every returned attribute/geometry and exact ID completeness. No old OSM
piece association, bank-width inference, physical change or admission is made.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

from bank_authority import ROOT, load, sha, write
from open_interface_authority import preflight as parent_preflight

SERVICE = "https://services-ap1.arcgis.com/ypkPEy1AmwPKGNNv/arcgis/rest/services/Geofabric_Surface_Hydrology_Network/FeatureServer"
FILES = (
    "diagnostics/hydrographic_source_capture.py",
    "diagnostics/test_hydrographic_source_capture.py",
    "calibration/pl1191-construction-v1/development/phase26-hydrographic-source-policy.md",
)


def geographic(sq, point):
    a, e2 = 6378137, 0.00669437999014
    w = 1 - e2 * np.sin(np.deg2rad(sq["lat"])) ** 2
    m = a * (1 - e2) / w**1.5
    nc = a / np.sqrt(w) * np.cos(np.deg2rad(sq["lat"]))
    u, v = np.asarray(point) * sq["scale"]
    t = np.deg2rad(sq["rotation"])
    x, z = u * np.cos(t) + v * np.sin(t), -u * np.sin(t) + v * np.cos(t)
    return [float(sq["lon"] + np.rad2deg(x / nc)), float(sq["lat"] + np.rad2deg(z / m))]


def rectangle(sq):
    corners = [
        geographic(sq, p)
        for p in [(-8640, -8640), (-8640, 8640), (8640, 8640), (8640, -8640)]
    ]
    values = np.asarray(corners)
    return {
        "xmin": float(values[:, 0].min()),
        "ymin": float(values[:, 1].min()),
        "xmax": float(values[:, 0].max()),
        "ymax": float(values[:, 1].max()),
        "spatialReference": {"wkid": 4326},
    }


def complete_ids(expected, features):
    ids = [f["attributes"]["OBJECTID"] for f in features]
    if any(type(i) is not int or i < 0 for i in list(expected) + ids):
        raise ValueError("Exact integer object IDs required")
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError(
            "Returned IDs missing/duplicate/unexpected; no repaired capture"
        )


def stage(parent, metadata, output):
    parent_preflight(parent)
    if output.exists():
        raise ValueError("Fresh hydrographic source protocol required")
    output.mkdir(parents=True)
    # Existing development input only. No holdout panel read or square replacement.
    geometry = parent / "parent/cases/low-coast-oceania/input/physical/geometry.json"
    shutil.copyfile(geometry, output / "source-geometry.json")
    for name in [
        "service.json",
        "layer-table-7.json",
        "layer-table-10.json",
        "receipt.json",
        "prospective-spec.json",
    ]:
        shutil.copyfile(metadata / name, output / name)
    import json

    box = rectangle(load(geometry)["sq"])
    write(
        output / "query-spec.json",
        {
            "service": SERVICE,
            "layers": [7, 10],
            "rectangle_4326": box,
            "source_frame_sha256": sha(geometry),
            "maximum_ids_per_layer": 10000,
            "ids_per_batch": 200,
            "geometry_filter": {
                "geometry": json.dumps(box, separators=(",", ":")),
                "geometryType": "esriGeometryEnvelope",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
            },
            "all_attributes_and_geometry": True,
            "no_correspondence_or_source_replacement": True,
            "publisher_credit": "Commonwealth of Australia (Bureau of Meteorology) 2022; published Geoscience Australia online-service metadata; CC BY4.0; not identical to old OSM capture",
        },
    )
    deps = dict(load(parent / "freeze.json")["source_files_sha256"])
    for n in FILES:
        deps[n] = sha(ROOT / n)
    write(
        output / "freeze.json",
        {
            "policy": "existing-coast-geofabric-source-v1",
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.iterdir())
                if p.is_file()
            },
            "parent_input_freeze_sha256": sha(parent / "freeze.json"),
            "metadata_known_before_feature_queries": True,
            "no_native_or_holdout": True,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    for base, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, v in f[key].items():
            if sha(base / n) != v:
                raise ValueError(f"Frozen source/query changed: {n}")


def capture(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh source capture required")
    output.mkdir(parents=True)
    spec = load(folder / "query-spec.json")
    records = []
    complete = []

    def fetch(name, layer, params):
        url = (
            spec["service"]
            + f"/{layer}/query?"
            + urllib.parse.urlencode({"f": "json", **params})
        )
        record = {"filename": name + ".json", "url": url, "status": None}
        try:
            try:
                response = urllib.request.urlopen(
                    urllib.request.Request(
                        url, headers={"User-Agent": "PL-1191-development-source/1"}
                    ),
                    timeout=45,
                )
            except urllib.error.HTTPError as e:
                response = e
            with response:
                body = response.read()
                record.update(
                    status=response.status, headers=dict(response.headers.items())
                )
            path = output / record["filename"]
            path.write_bytes(body)
            record["sha256"] = sha(path)
            if record["status"] != 200:
                raise ValueError(f"HTTP{record['status']}; no retry")
            result = load(path)
            if "error" in result or result.get("exceededTransferLimit"):
                raise ValueError(
                    "Service error/truncation; no retry or repaired square"
                )
            return result
        except Exception as error:
            record["error"] = str(error)
            raise
        finally:
            records.append(record)

    try:
        for layer in spec["layers"]:
            result = fetch(
                f"layer-{layer}-ids",
                layer,
                {**spec["geometry_filter"], "where": "1=1", "returnIdsOnly": "true"},
            )
            ids = result.get("objectIds")
            if not isinstance(ids, list) or len(ids) != len(set(ids)):
                raise ValueError("Missing/invalid object ID set, not zero")
            ids = sorted(ids)
            if any(type(i) is not int or i < 0 for i in ids):
                raise ValueError("Invalid object ID type, not repaired")
            if len(ids) > spec["maximum_ids_per_layer"]:
                raise ValueError("Source limit exceeded; not truncated")
            features = []
            for start in range(0, len(ids), spec["ids_per_batch"]):
                chunk = ids[start : start + spec["ids_per_batch"]]
                response = fetch(
                    f"layer-{layer}-batch-{start:06d}",
                    layer,
                    {
                        "objectIds": ",".join(map(str, chunk)),
                        "outFields": "*",
                        "returnGeometry": "true",
                        "outSR": 4326,
                        "orderByFields": "OBJECTID ASC",
                    },
                )
                batch = response.get("features")
                if not isinstance(batch, list):
                    raise ValueError("Missing source features, not empty water")
                reference = response.get("spatialReference", {})
                if batch and reference.get("latestWkid", reference.get("wkid")) != 4326:
                    raise ValueError("Returned geometry CRS not verified as EPSG4326")
                complete_ids(chunk, batch)
                features.extend(batch)
            complete_ids(ids, features)
            write(
                output / f"layer-{layer}-complete.json",
                {
                    "objectIds": ids,
                    "features": features,
                    "spatialReference": {"wkid": 4326},
                },
            )
            complete.append(
                {"layer": layer, "ids": len(ids), "features": len(features)}
            )
    finally:
        write(
            output / "receipt.json",
            {
                "prospective_freeze_sha256": sha(folder / "freeze.json"),
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "requests": records,
                "complete_layers": complete,
                "no_old_source_or_mask_replaced": True,
                "physical_admission": False,
                "atomic_database_snapshot": False,
                "identity_to_old_OSM": None,
                "width_stage_capacity_qualification": None,
            },
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name, args in (
        ("stage", ["parent", "metadata", "output"]),
        ("preflight", ["folder"]),
        ("capture", ["folder", "output"]),
    ):
        q = sub.add_parser(name)
        for a in args:
            q.add_argument(a, type=Path)
    args = vars(p.parse_args())
    globals()[args.pop("command")](**args)
