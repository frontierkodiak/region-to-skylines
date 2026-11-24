"""Query all TreeGOER-listed species in six squares from a named Cabinet snapshot.

Run: uv run truth-data/acquire_treegoer.py
This supersedes the preliminary manually selected genus-allowlist query.
Uses stdin to Cabinet, so the long tree list is not a shell argument.
"""

import csv
import hashlib
import io
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(os.environ["VEGETATION_DATA_DIR"]).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
TRAITS = Path(__file__).resolve().parents[3] / "vegetation-data/tree-taxa.json"


def main():
    trait_bytes = TRAITS.read_bytes()
    traits = json.loads(trait_bytes)
    species = sorted(set(traits["species"]))
    regions = json.loads((ROOT / "squares.json").read_text())["regions"]
    values = ",\n".join(
        "(" + ",".join([repr(r["id"]), *map(str, r["bbox"])]) + ")" for r in regions
    )
    names = ",\n".join("('" + name.replace("'", "''") + "')" for name in species)
    predicates = " OR ".join(
        f"(longitude BETWEEN {r['bbox'][0]} AND {r['bbox'][2]} AND latitude BETWEEN {r['bbox'][1]} AND {r['bbox'][3]})"
        for r in regions
    )
    sql = f"""COPY (
WITH regions(region,west,south,east,north) AS (VALUES {values}),
tree_species(name) AS (VALUES {names}),
tree_taxa AS (
  SELECT t.taxon_id,split_part(t.name,' ',1) AS genus,t.name AS species,ts.name AS treegoer_matched_name
  FROM taxa t JOIN tree_species ts
    ON ts.name=CASE WHEN t.rank='species' THEN t.name ELSE regexp_extract(t.name,'^([^ ]+ [^ ]+)',1) END
  WHERE t.active
), filtered AS (
  SELECT * FROM observations WHERE quality_grade='research'
  AND positional_accuracy IS NOT NULL AND positional_accuracy BETWEEN 0 AND 100
  AND ({predicates})
), selected AS (
  SELECT r.region,CAST(o.observation_uuid AS VARCHAR) AS id,o.longitude AS lon,o.latitude AS lat,
    t.genus,t.species,'inat_cabinet_20261027' AS source,'occurrence' AS kind,
    'treegoer_tree_species_match_not_individual_measurement' AS growth_form,
    o.positional_accuracy,o.observed_on,o.taxon_id,t.treegoer_matched_name,
    count(*) OVER(PARTITION BY r.region) AS region_eligible_records,
    row_number() OVER(PARTITION BY r.region ORDER BY sha256(CAST(o.observation_uuid AS VARCHAR))) AS sample_rank
  FROM filtered o JOIN tree_taxa t USING(taxon_id)
  JOIN regions r ON o.longitude BETWEEN r.west AND r.east AND o.latitude BETWEEN r.south AND r.north
)
SELECT * EXCLUDE(sample_rank) FROM selected WHERE sample_rank<=10000 ORDER BY region,id
) TO '/dev/stdout' (FORMAT CSV,HEADER true);
"""
    (ROOT / "inat_treegoer_six_squares.sql").write_text(sql)
    run = subprocess.run(
        ["cabinet", "query", "--snapshot", "20261027", "--file", "/dev/stdin"],
        input=sql,
        capture_output=True,
        text=True,
        check=False,
    )
    (ROOT / "inat_treegoer_stdout.log").write_text(run.stdout)
    (ROOT / "inat_treegoer_stderr.log").write_text(run.stderr)
    if run.returncode:
        raise RuntimeError(run.stderr[-4000:])
    header = "region,id,lon,lat,genus,species,source,kind,growth_form,positional_accuracy,observed_on,taxon_id,treegoer_matched_name,region_eligible_records"
    reader = csv.DictReader(io.StringIO(run.stdout[run.stdout.index(header) :]))
    expected_regions = {r["id"] for r in regions}
    rows = []
    for row in reader:
        if row["region"] not in expected_regions:
            break
        assert all(value is not None for value in row.values())
        rows.append(row)
    with (ROOT / "inat_treegoer_occurrences.csv").open("w") as file:
        writer = csv.DictWriter(file, fieldnames=header.split(","))
        writer.writeheader()
        writer.writerows(rows)
    by_region = defaultdict(list)
    for row in rows:
        for key in ("lon", "lat"):
            row[key] = float(row[key])
        for key in ("positional_accuracy", "taxon_id", "region_eligible_records"):
            row[key] = int(row[key])
        row["growth_form_source"] = traits["source"]
        by_region[row["region"]].append(row)
    for name in sorted(expected_regions):
        records = by_region[name]
        (ROOT / f"{name}_treegoer_occurrences.json").write_text(
            json.dumps(records, separators=(",", ":"))
        )
        print(
            name,
            len(records),
            Counter(r["genus"] for r in records).most_common(5),
            flush=True,
        )
    (ROOT / "treegoer_occurrences_all.json").write_text(
        json.dumps(rows, separators=(",", ":"))
    )
    snapshot_path = ROOT / "cabinet_snapshot_manifest.json"
    receipt = {
        "method": "Cabinet metadata query over ALL supplied TreeGOER-listed species, not a handpicked genus subset",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "snapshot": "20261027",
        "snapshot_manifest_sha256": hashlib.sha256(
            snapshot_path.read_bytes()
        ).hexdigest(),
        "snapshot_manifest_receipt": snapshot_path.name,
        "query_sha256": hashlib.sha256(sql.encode()).hexdigest(),
        "csv_sha256": hashlib.sha256(
            (ROOT / "inat_treegoer_occurrences.csv").read_bytes()
        ).hexdigest(),
        "tree_list_source": traits["source"],
        "tree_list_license": traits["license"],
        "tree_list_sha256": hashlib.sha256(trait_bytes).hexdigest(),
        "tree_list_species_n": len(species),
        "filters": "Active taxonomy; exact species scientific-name match or first-two-token binomial for infraspecific taxa; research-grade; nonnull positional accuracy<=100m; full exact production squares. Deterministic UUID hash cap10000 per square.",
        "license_status": "TreeGOER list CC-BY-4.0 per supplied provenance. iNaturalist metadata blanket reuse license not established here; no photo rights or commercial-AI-training permission asserted.",
        "limitations": [
            "Occurrence sample frequencies are not tree abundance, nor natural-only evidence. No captive/cultivated flag in this Cabinet snapshot.",
            "Species-list match is not an individual growth-form or height measurement. Taxonomic synonyms missing from the list can produce false negatives.",
            "No cap correction or observer-effort weighting is claimed.",
            "Preliminary handpicked-genus files are retained only as acquisition history; use these full TreeGOER-query files.",
        ],
        "regions": {
            name: {
                "records": len(records),
                "eligible_before_cap": records[0]["region_eligible_records"]
                if records
                else 0,
                "top_genera": Counter(r["genus"] for r in records).most_common(10),
            }
            for name, records in sorted(by_region.items())
        },
    }
    (ROOT / "treegoer_query_receipt.json").write_text(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
