"""Merge authenticated read-only UGC facts without publishing author descriptions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def closure(iid, records):
    pending = list(records[iid]["children"])
    seen, unresolved = set(), set()
    while pending:
        child = pending.pop()
        if child in seen:
            continue
        seen.add(child)
        row = records.get(child)
        if row is None or row["result"] != 1:
            unresolved.add(child)
        else:
            pending.extend(row["children"])
    return sorted(seen, key=int), sorted(unresolved, key=int)


def normalize(previous, raw, out):
    catalog = json.loads(previous.read_text())
    records, receipts = {}, []
    for path in sorted(raw.glob("batch-*.jsonl")):
        receipts.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for line in path.read_text().splitlines():
            record = json.loads(line)
            records[record["id"]] = record
    receipt = json.loads((raw / "receipt.json").read_text())
    checked = receipt["finished_utc"]
    by_id = {row["id"]: row for row in catalog["items"]}
    for iid, item in by_id.items():
        row = records.get(iid)
        if not row or row["result"] != 1:
            item["steamworks_result"] = row.get("result") if row else None
            continue
        item["title"] = row["title"]
        item["tags"] = [tag.strip() for tag in row["tags"].split(",") if tag.strip()]
        for field in ("subscribers", "favourites", "visibility", "banned"):
            item[field] = row[field]
        item["updated_unix"] = row["updated"]
        item["created_unix"] = row["created"]
        item["file_bytes"] = row["file_bytes"]
        if item.get("author_id") and item["author_id"] != row["owner"]:
            item["author"] = None
        item["author_id"] = row["owner"]
        item["author_url"] = f"https://steamcommunity.com/profiles/{row['owner']}"
        item["rating"] = {"votes_up": row["votes_up"], "votes_down": row["votes_down"], "score": row["score"]}
        item["rating_votes"] = row["votes_up"] + row["votes_down"]
        item["public_star_rating_retrieved_utc"] = catalog["retrieved_utc"]
        item["availability"] = "public" if row["visibility"] == 0 and not row["banned"] else "not_public"
        item["public_page_status"] = item.get("dependency_status")
        item["dependencies"] = row["children"]
        item["dependency_status"] = "steamworks_children_checked"
        descendants, unresolved = closure(iid, records)
        item["dependency_closure"] = descendants
        item["unresolved_dependencies"] = unresolved
        item["dependency_closure_review"] = not unresolved
        item["required_mods"] = [
            child
            for child in descendants
            if records.get(child, {}).get("result") == 1 and "Mod" in records[child]["tags"].split(",")
        ]
        item["dependency_checked_utc"] = checked
        item["dependency_basis"] = (
            "Valve ISteamUGC GetQueryUGCChildren; transitive details queried; not a claim that a public HTML page was read"
        )
        item["description_sha256"] = hashlib.sha256(row["description"].encode()).hexdigest()
    catalog["retrieved_utc"] = checked
    catalog["dependency_items"] = {
        iid: {
            "title": row["title"],
            "tags": row["tags"].split(","),
            "result": row["result"],
            "children": row["children"],
        }
        for iid, row in records.items()
    }
    catalog["steamworks_refresh"] = {
        "checked_utc": checked,
        "queried": len(records),
        "result_counts": {
            str(code): sum(r["result"] == code for r in records.values())
            for code in sorted({r["result"] for r in records.values()})
        },
        "method": receipt["method"],
        "private_raw_response_digests": receipts,
        "dependency_witnesses": {"704607028": [], "808637188": ["767233815"]},
        "permission_source": "Caleb's standing Steam-download permission on PL-1326, 2026-11-25",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(catalog, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    normalize(args.previous, args.raw, args.out)
