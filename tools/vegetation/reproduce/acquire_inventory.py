"""Acquire public civic inventory fields, never addresses or observer identity.

Run: uv run truth-data/acquire_inventory.py
"""

import hashlib
import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(os.environ["VEGETATION_DATA_DIR"]).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
SOURCES = {
    "boston": {
        "base": "https://services.arcgis.com/sFnw0xNflSi8J0uh/arcgis/rest/services/BPRD_Trees/FeatureServer/0",
        "fields": "ObjectId,id,spp_com,spp_bot,dbh,dbh_range,numberof_st,date_plant,park,x_longitude,y_latitude",
        "order": "ObjectId",
        "license": "Open Data Commons PDDL (official Analyze Boston package license_id=odc-pddl)",
        "catalog": "https://data.boston.gov/dataset/bprd-trees",
    },
    "asheville": {
        "base": "https://gis.ashevillenc.gov/server/rest/services/Environmental/TreeMapView/MapServer/0",
        "fields": "objectid,genus,species,common_name,diameter,height,canopy_height,date_planted,date_removed,is_native,lifecyclestatus",
        "order": "objectid",
        "license": "No explicit reuse license established from inspected service; public access is not a license grant.",
        "catalog": "https://gis.ashevillenc.gov/server/rest/services/Environmental/TreeMapView/MapServer/0",
    },
}


def get(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Polli vegetation evidence pilot"}
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def acquire(name, config):
    schema = get(config["base"] + "?f=pjson")
    (ROOT / f"{name}_schema.json").write_bytes(schema)
    count_query = urllib.parse.urlencode(
        {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    )
    count = json.loads(get(config["base"] + "/query?" + count_query))["count"]

    def page(offset):
        params = {
            "where": "1=1",
            "outFields": config["fields"],
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": 1000,
            "orderByFields": config["order"],
        }
        url = config["base"] + "/query?" + urllib.parse.urlencode(params)
        body = get(url)
        obj = json.loads(body)
        if "error" in obj:
            raise ValueError(obj["error"])
        return obj["features"], {
            "url": url,
            "sha256": hashlib.sha256(body).hexdigest(),
            "records": len(obj["features"]),
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = list(pool.map(page, range(0, count, 1000)))
    features = [feature for records, _ in pages for feature in records]
    assert len(features) == count, (len(features), count)
    path = ROOT / f"{name}_raw.geojson"
    path.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features}, separators=(",", ":")
        )
    )
    receipt = {
        "source": name,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "count_endpoint_records": count,
        "downloaded_records": len(features),
        "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "fields_requested": config["fields"].split(","),
        "schema_sha256": hashlib.sha256(schema).hexdigest(),
        **config,
        "requests": [receipt for _, receipt in pages],
    }
    (ROOT / f"{name}_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(name, count, path.stat().st_size, flush=True)


if __name__ == "__main__":
    for source_name, source in SOURCES.items():
        acquire(source_name, source)
