#!/usr/bin/env python3
import csv
import hashlib
import io
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

root = Path(os.environ["VEGETATION_DATA_DIR"]).resolve()
root.mkdir(parents=True, exist_ok=True)
record = json.load(urlopen("https://zenodo.org/api/records/13132613", timeout=30))
file = next(f for f in record["files"] if f["key"] == "TreeGOER_Taxonomy.txt")
url = file["links"]["self"]
body = urlopen(url, timeout=30).read()
rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig")), delimiter="|"))
names = sorted({r["Species"].strip() for r in rows if r["Species"].strip()})
resolved = sorted({r["scientificFinal"].strip() for r in rows if r["scientificFinal"].strip()})
payload = {"source": "https://doi.org/10.5281/zenodo.13132613", "license": "CC-BY-4.0", "species": names}
out = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
metadata = {
    "title": "TreeGOER 2024.07 taxonomy whitelist",
    "source": url,
    "record": "https://zenodo.org/records/13132613",
    "version": record["metadata"]["version"],
    "license": record["metadata"]["license"]["id"],
    "retrievedAt": datetime.now(UTC).isoformat(),
    "sourceSha256": hashlib.sha256(body).hexdigest(),
    "outputSha256": hashlib.sha256(out).hexdigest(),
    "sourceMd5": file["checksum"],
    "sourceBytes": len(body),
    "outputBytes": len(out),
    "rows": len(rows),
    "speciesNames": len(names),
    "resolvedNames": len(resolved),
    "headers": list(rows[0]),
    "taxonomicStatus": dict(Counter(r["taxonomicStatus"] for r in rows)),
    "paperDoi": "10.1111/gcb.16914",
    "zoteroKey": "BDJPBIW6",
    "nameColumn": "Species",
    "caveats": [
        "The downloadable 2024.07 taxonomy file contains 48,518 rows/names, whereas the 2023 paper and environmental-range dataset describe 48,129 species. Report the artifact's actual count.",
        "Original source species names, not a newly reconciled GBIF accepted-name list. A GBIF record with a later synonym may fail exact matching; this is unknown coverage, not proof of non-tree habit.",
        "Tree species identity does not prove each occurrence is a tree or reflect planted abundance; no occurrence count is an inventory count.",
        "A smaller tree catalog reduces some over-inclusive matches but does not establish an absolute tree/shrub growth-form boundary."
    ]
}
(root / "TreeGOER_Taxonomy.txt").write_bytes(body)
(root / "treegoer-species.json").write_bytes(out)
(root / "treegoer-species-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps(metadata, indent=2))
