"""Post-capture container recheck. Never changes the pre-query support decisions."""

import collections
from pathlib import Path

import study

frozen = study.read(study.HERE / "freeze.json")
rows = []
for row in frozen["inventory"]:
    path = Path(row["locator"])
    if study.sha(path) != row["sha256"]:
        raise ValueError("installed CRP differs from pre-query inventory")
    package, assets = study.measure_maps.read_any(path.read_bytes())
    rows.append(
        {
            "file": row["file"],
            "sha256": row["sha256"],
            "crp_format": package["format"],
            "asset_count": len(assets),
            "pre_query_exclusion": row["exclusion"],
            "pre_query_supported": row.get("supported"),
            "pre_query_missing": row.get("missing"),
        }
    )
value = {
    "verified_at": study.now(),
    "source_sha256": study.sha(Path(__file__)),
    "reader_sha256": study.sha(study.MAP / "survey/measure_maps.py"),
    "formats": dict(collections.Counter(r["crp_format"] for r in rows)),
    "packages": rows,
    "scope": "read_any header-only recheck of unchanged bytes after capture; all 92 eligible packages already passed through read_any before NetManager decoding in preparation; 23 NetManager decode errors remain unsupported, not repaired",
}
(study.HERE / "header-coverage.json").write_bytes(study.encoded(value))
print(value["formats"])
