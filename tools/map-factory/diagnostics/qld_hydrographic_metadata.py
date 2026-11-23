"""Frozen public Queensland production metadata read; no features or map writes."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import urllib.error
import urllib.request

from bank_authority import ROOT, load, sha, write
from hydrographic_source_capture import preflight as old_preflight

SERVICE = "https://spatial-gis.information.qld.gov.au/arcgis/rest/services/Basemaps/FoundationData/MapServer"
URLS = {
    "service.json": SERVICE + "?f=pjson",
    "layer-62.json": SERVICE + "/62?f=pjson",
    "layer-63.json": SERVICE + "/63?f=pjson",
    "resource.html": "https://www.data.qld.gov.au/dataset/hydrographic-features-queensland-series/resource/c2410653-13fb-4032-865e-3a7317b26a2a",
    "schema.html": "https://qldglobe.information.qld.gov.au/help-info/Queensland-topographic-data-schema.html",
    "regulatory-limits.html": "https://www.business.qld.gov.au/industries/mining-energy-water/water/maps-data/watercourse-map",
}
FILES = (
    "diagnostics/qld_hydrographic_metadata.py",
    "diagnostics/test_qld_hydrographic_metadata.py",
    "calibration/pl1191-construction-v1/development/phase27-qld-metadata-policy.md",
)


def layer_contract(root, line, area):
    """Discovery IDs never suffice: verify production names, geometry and fields."""
    listed = {v["id"]: v["name"] for v in root["layers"]}
    for record, number, name, geometry in (
        (line, 62, "Watercourse lines", "esriGeometryPolyline"),
        (area, 63, "Waterbody areas", "esriGeometryPolygon"),
    ):
        if (
            record.get("id") != number
            or record.get("name") != name
            or listed.get(number) != name
            or record.get("geometryType") != geometry
            or not record.get("fields")
            or "Query" not in record.get("capabilities", "")
        ):
            raise ValueError(
                "Production layer contract differs; no endpoint substitution"
            )
        oid = [
            x["name"] for x in record["fields"] if x.get("type") == "esriFieldTypeOID"
        ]
        if len(oid) != 1:
            raise ValueError("Exactly one declared object ID field required")
    return True


def stage(parent, output):
    old_preflight(parent)
    if output.exists():
        raise ValueError("Fresh metadata protocol required")
    output.mkdir(parents=True)
    shutil.copyfile(parent / "source-geometry.json", output / "source-geometry.json")
    shutil.copyfile(parent / "freeze.json", output / "old-source-freeze.json")
    write(
        output / "metadata-spec.json",
        {
            "urls": URLS,
            "production_service": SERVICE,
            "source_frame_sha256": sha(output / "source-geometry.json"),
            "metadata_only": True,
            "same_development_square": True,
            "discovery_ids_not_authority": True,
            "automatic_retries": 0,
        },
    )
    deps = dict(load(parent / "freeze.json")["source_files_sha256"])
    # Retain the complete phase26 source set, including its separate overlay.
    for n in (
        "diagnostics/hydrographic_source_coverage.py",
        "diagnostics/test_hydrographic_source_coverage.py",
        "calibration/pl1191-construction-v1/development/phase26-source-coverage-policy.md",
    ) + FILES:
        deps[n] = sha(ROOT / n)
    write(
        output / "freeze.json",
        {
            "policy": "qld-production-metadata-v1",
            "source_files_sha256": deps,
            "files_sha256": {
                p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
            },
            "queries_not_yet_read": True,
            "prior_discovery_known": True,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    for base, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, value in f[key].items():
            if sha(base / n) != value:
                raise ValueError(f"Changed bound source/input: {n}")


def capture(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh metadata capture required")
    output.mkdir(parents=True)
    records = []
    try:
        for name, url in load(folder / "metadata-spec.json")["urls"].items():
            record = {"filename": name, "url": url, "status": None}
            records.append(record)
            try:
                try:
                    response = urllib.request.urlopen(
                        urllib.request.Request(
                            url, headers={"User-Agent": "PL-1191-public-source/1"}
                        ),
                        timeout=45,
                    )
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    body = response.read()
                    record.update(
                        status=response.status,
                        final_url=response.geturl(),
                        headers=dict(response.headers.items()),
                    )
                p = output / name
                p.write_bytes(body)
                record["sha256"] = sha(p)
                if record["status"] != 200:
                    raise ValueError(f"HTTP{record['status']}; no retry")
                if name.endswith(".json") and "error" in load(p):
                    raise ValueError("Service metadata error; no substitution")
            except Exception as error:
                record["error"] = str(error)
                raise
    finally:
        write(
            output / "receipt.json",
            {
                "prospective_freeze_sha256": sha(folder / "freeze.json"),
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "requests": records,
                "complete": len(records) == len(URLS)
                and all(r.get("status") == 200 and "error" not in r for r in records),
                "physical_or_source_replacement": False,
            },
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name, fields in (
        ("stage", ["parent", "output"]),
        ("preflight", ["folder"]),
        ("capture", ["folder", "output"]),
    ):
        q = sub.add_parser(name)
        for field in fields:
            q.add_argument(field, type=Path)
    args = vars(p.parse_args())
    globals()[args.pop("command")](**args)
