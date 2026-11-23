"""Bounded Queensland production hydrography query, not a physical water plan."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import urllib.error
import urllib.parse
import urllib.request

from bank_authority import ROOT, load, sha, write
from hydrographic_source_capture import rectangle
from qld_hydrographic_metadata import (
    SERVICE,
    layer_contract,
    preflight as metadata_preflight,
)

FILES = (
    "diagnostics/qld_hydrographic_capture.py",
    "diagnostics/test_qld_hydrographic_capture.py",
    "calibration/pl1191-construction-v1/development/phase27-qld-feature-policy.md",
)


def complete_ids(expected, features, field):
    ids = [f["attributes"][field] for f in features]
    if any(type(i) is not int or i < 0 for i in list(expected) + ids):
        raise ValueError("Exact integer object IDs required")
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError(
            "Returned IDs missing/duplicate/unexpected; no repaired capture"
        )


def stage(parent, metadata, output):
    metadata_preflight(parent)
    receipt = load(metadata / "receipt.json")
    if receipt["prospective_freeze_sha256"] != sha(parent / "freeze.json"):
        raise ValueError("Metadata capture lineage mismatch")
    records = {r["filename"]: r for r in receipt["requests"]}
    for name in ("service.json", "layer-62.json", "layer-63.json"):
        r = records[name]
        if r["status"] != 200 or sha(metadata / name) != r["sha256"]:
            raise ValueError("Changed/incomplete production layer metadata")
    root, line, area = [
        load(metadata / n) for n in ("service.json", "layer-62.json", "layer-63.json")
    ]
    layer_contract(root, line, area)
    if output.exists():
        raise ValueError("Fresh Queensland source protocol required")
    output.mkdir(parents=True)
    shutil.copytree(metadata, output / "metadata")
    shutil.copyfile(parent / "source-geometry.json", output / "source-geometry.json")
    box = rectangle(load(parent / "source-geometry.json")["sq"])
    write(
        output / "query-spec.json",
        {
            "service": SERVICE,
            "layers": [62, 63],
            "id_fields": {
                str(x["id"]): next(
                    f["name"] for f in x["fields"] if f["type"] == "esriFieldTypeOID"
                )
                for x in (line, area)
            },
            "geometry_types": {str(x["id"]): x["geometryType"] for x in (line, area)},
            "rectangle_4326": box,
            "source_frame_sha256": sha(parent / "source-geometry.json"),
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
            "publisher_credit": area.get("copyrightText"),
            "catalogue_license_page_challenged_unconfirmed_in_this_capture": True,
            "cartographic_scale_dependent_not_surveyed_bank": True,
            "GDA94_to_WGS84_service_transformation_accuracy_unqualified": True,
        },
    )
    deps = dict(load(parent / "freeze.json")["source_files_sha256"])
    for n in FILES:
        deps[n] = sha(ROOT / n)
    write(
        output / "freeze.json",
        {
            "policy": "existing-coast-qld-production-source-v1",
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "parent_input_freeze_sha256": sha(parent / "freeze.json"),
            "partial_catalogue_metadata_preserved": True,
            "feature_queries_not_yet_read": True,
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
            if result.get("objectIdFieldName") != spec["id_fields"][str(layer)]:
                raise ValueError(
                    "Returned object ID schema differs from production metadata"
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
                        "orderByFields": spec["id_fields"][str(layer)] + " ASC",
                    },
                )
                if response.get("geometryType") != spec["geometry_types"][str(layer)]:
                    raise ValueError(
                        "Returned geometry type differs from production metadata"
                    )
                batch = response.get("features")
                if not isinstance(batch, list):
                    raise ValueError("Missing source features, not empty water")
                reference = response.get("spatialReference", {})
                if batch and reference.get("latestWkid", reference.get("wkid")) != 4326:
                    raise ValueError("Returned geometry CRS not verified as EPSG4326")
                complete_ids(chunk, batch, spec["id_fields"][str(layer)])
                features.extend(batch)
            complete_ids(ids, features, spec["id_fields"][str(layer)])
            write(
                output / f"layer-{layer}-complete.json",
                {
                    "objectIds": ids,
                    "features": features,
                    "spatialReference": {"wkid": 4326},
                    "objectIdField": spec["id_fields"][str(layer)],
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
