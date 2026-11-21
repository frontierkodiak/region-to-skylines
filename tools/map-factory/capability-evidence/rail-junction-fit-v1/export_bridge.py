"""Audit the export bridge: what the study reads from saved `.crp` bytes, and how.

The accepted study's bridge established that every field its model used was
readable from the nine format-12 cohort exports, and left the two stock
controls on the native snapshot because the accepted reader accepts only the
format-12 container. This audit does two things the review asked for:

* it reads the package container with `survey/measure_maps.py:read_any`, which
  covers every package format the game writes (4..12), and decodes each
  NetManager section with the data version that section declares. The two stock
  controls are format 8 with data versions 114007 and 114009; they are decoded
  read-only with those gates.
* it reports every consumed field, the section byte provenance, the exact
  `.crp` SHA-256, the float precision and the tolerance, and it separates the
  fields the exports carry directly from the fields that need an observed
  catalog and from the one field class the native snapshots do not carry at all:
  the authored endpoint tangents, which stay export-derived hypotheses.

Status per package is one of:

* `export_derivable` - every model-consumed non-tangent field agrees between the
  export-derived record and the native snapshot, using the observed catalogs.
* `export_derivable_with_own_catalog` - as above only when the catalog includes
  the package's own snapshot, because the package uses prefab lane templates the
  other packages do not (the stock controls). The tangents and all topology
  still come straight from the export bytes.
* `no_train_domain` - the package has no Train-capable segment, so there is no
  field to compare; this is not a pass.

Run:  .venv/bin/python capability-evidence/rail-junction-fit-v1/export_bridge.py
Check: ... --check
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]

import binding  # noqa: E402
import export_topology as exports  # noqa: E402
import topology  # noqa: E402
from survey import measure_maps  # noqa: E402

FREEZE = "rail-junction-fit-v1"
AUDIT = HERE / "bridge-audit.json"
METADATA_FIELDS = (
    "mapName",
    "environment",
    "publishedFileId",
    "steamAuthor",
    "timeCreated",
    "buildGuid",
)


def metadata(locator):
    container = exports.read_container(locator)
    package, assets = measure_maps.read_any(container["raw"])
    meta_asset = next(
        (asset for asset in assets if asset["kind"] == 100),
        None,
    )
    parsed = measure_maps.parse_metadata(meta_asset["payload"]) if meta_asset else {}
    return (
        {key: parsed.get(key) for key in METADATA_FIELDS},
        package["author_encrypted"] and "present" or "absent",
    )


def fields_summary(counts, failures):
    return {
        field: {
            "checked": counts[field + ":checked"],
            "agree": counts[field + ":agree"],
            "rate": (counts[field + ":agree"] / counts[field + ":checked"])
            if counts[field + ":checked"]
            else None,
        }
        for field in exports.accepted_bridge.MODEL_FIELDS
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = binding.load_manifest()
    accepted = binding.accepted_openings(manifest, verify_observations=False)
    entries = accepted["openings"]["openings"]
    packages = accepted["packages"]
    catalogs_all = exports.catalogs_for(entries, {"packages": packages})

    report = {
        "schema": 1,
        "study": FREEZE,
        "audited_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "accepted_head": manifest["source"]["accepted_head"],
        "accepted_prefix": manifest["source"]["accepted_prefix"],
        "accepted_prefix_hashes": manifest["source"]["accepted_files"],
        "readers": {
            "container": "survey/measure_maps.py:read_any (package formats >= 2, read-only)",
            "version": "survey/measure_maps.py:data_version (DataSerializer header)",
            "section": "network_writer.py:section_start (unique manager tag)",
            "net": "netcodec.py:NetSection (declared version; older layouts decode read-only)",
            "catalogs": "observed prefab lane templates and integer flag names, hash-bound and leave-one-package-out checked",
        },
        "exporter": {
            "revision": None,
            "build": None,
            "note": (
                "the container records a package format and the section a data "
                "version; it carries no exporter build or revision. Those fields "
                "are null on purpose rather than guessed, and the game-side build "
                "receipt is bound with the labels, not here"
            ),
        },
        "precision": {
            "positions": "IEEE-754 binary32 components, compared at 0.01 m (the accepted bridge's tolerance)",
            "tangents": "IEEE-754 binary32 components; horizontal projection is unit to float32; turn angles computed in double",
            "tie_tolerance_degrees": 1e-6,
            "threshold_tolerance_degrees": 1e-6,
            "note": (
                "a unit vector's float32 resolution is about 6e-4 degrees, so the "
                "tolerances are boundary conventions, not measurement precision"
            ),
        },
        "packages": {},
        "totals": {},
        "tangents": {
            "native_attested": False,
            "statement": (
                "the accepted networks.json snapshots do not emit endpoint "
                "tangents; every ruled-on tangent value is read from export bytes, "
                "so it is an export-derived hypothesis and not a completed native bridge"
            ),
        },
    }
    totals = collections.Counter()
    agreement = {"fields": {}, "digests_identical": 0, "packages": len(entries)}
    statuses = {}
    for entry in entries:
        name = entry["package"]
        locator = packages[name]["locator"]
        container = exports.cached_net(locator)
        net = container["net"]
        native = topology.from_native(
            binding.load_json(binding.raw_dir(entry) / "networks.json.gz"),
            entry["opening"],
        )
        built = exports.exported_package(net, catalogs_all)
        counts, failures = exports.accepted_bridge.compare(
            built, native, train_only=True
        )
        totals.update(counts)
        native_digest = exports.accepted_bridge.model_input_digest(native)
        export_digest = exports.accepted_bridge.model_input_digest(built)
        if native_digest == export_digest:
            agreement["digests_identical"] += 1

        # Leave this package's own snapshot out of the catalogs.
        held = exports.catalogs_for(
            entries,
            {"packages": packages},
            snapshot_subset={
                other["opening"]
                for other in entries
                if other["opening"] != entry["opening"]
            },
        )
        built_held = exports.exported_package(net, held)
        held_counts, held_failures = exports.accepted_bridge.compare(
            built_held, native, train_only=True
        )
        metadata_fields, author = metadata(locator)
        table = exports.tangents(net)
        train_segments = [
            segment_id
            for segment_id, segment in native["segments"].items()
            if topology.train_lanes(segment)
        ]
        tangent_missing = [
            segment_id for segment_id in train_segments if segment_id not in table
        ]
        fields = fields_summary(counts, failures)
        checked = sum(value["checked"] for value in fields.values())
        # A checked count of zero is a vacuous field, not a disagreement: the
        # package has no Train-domain record to compare.
        complete = all(value["rate"] in (1.0, None) for value in fields.values())
        own_catalog_required = any(
            value.startswith("prefab:") for value in built_held["missing"]
        )
        if checked == 0:
            status = "no_train_domain"
        elif complete and not own_catalog_required:
            status = "export_derivable"
        elif complete:
            status = "export_derivable_with_own_catalog"
        else:
            status = "native_snapshot_only"
        statuses[name] = status
        report["packages"][name] = {
            "opening": entry["opening"],
            "split": entry["split"],
            "crp": {
                "locator": locator,
                "sha256": container["sha256"],
                "bytes": len(container["raw"]),
                "format": container["format"],
                "package_version": container["package_version"],
                "simulator_asset_sha256": container["payload_sha256"],
                "asset_kinds": container["asset_kinds"],
                "assets": container["assets"],
                "author_present": author == "present",
                "metadata": metadata_fields,
            },
            "section": {
                "data_version": container["lineage"]["data_version"],
                "netmanager_offset": container["lineage"]["netmanager_offset"],
                "netcodec_current_version": container["lineage"][
                    "netcodec_current_version"
                ],
                "current_version_section": container["lineage"][
                    "current_version_section"
                ],
                "nodes": container["lineage"]["nodes"],
                "segments": container["lineage"]["segments"],
                "prefabs": container["lineage"]["prefabs"],
            },
            "native": {
                "networks_sha256": binding.file_digest(
                    binding.raw_dir(entry) / "networks.json.gz"
                ),
                "plan_sha256": binding.file_digest(
                    binding.raw_dir(entry) / "query-freeze.json.gz"
                ),
                "train_segments": len(train_segments),
            },
            "fields": fields,
            "field_failures": failures,
            "model_input_digest": {
                "native_sha256": native_digest["sha256"],
                "export_sha256": export_digest["sha256"],
                "identical": native_digest == export_digest,
                "segments": native_digest["segments"],
                "nodes": native_digest["nodes"],
            },
            "leave_one_package_out": {
                "missing": built_held["missing"],
                "unseen_prefabs": sorted(
                    {
                        value.split(":", 1)[1]
                        for value in built_held["missing"]
                        if value.startswith("prefab:")
                    }
                ),
                "lane_checked": held_counts["lanes:checked"],
                "lane_agree": held_counts["lanes:agree"],
                "invert_checked": held_counts["invert:checked"],
                "invert_agree": held_counts["invert:agree"],
                "outside_checked": held_counts["node_outside:checked"],
                "outside_agree": held_counts["node_outside:agree"],
                "field_failures": held_failures,
            },
            "tangents": {
                "train_segments_covered": len(train_segments) - len(tangent_missing),
                "missing_train_segments": tangent_missing,
                "report": exports.tangent_report(table),
                "versus_chord": exports.tangent_chord_angles(
                    exports.attach(native, table)
                ),
            },
            "status": status,
            "own_catalog_required": own_catalog_required,
        }

    fields = {}
    for field in exports.accepted_bridge.MODEL_FIELDS:
        checked = totals[field + ":checked"]
        agree = totals[field + ":agree"]
        fields[field] = {
            "checked": checked,
            "agree": agree,
            "rate": (agree / checked) if checked else None,
        }
    agreement["fields"] = fields
    report["totals"] = {
        "fields": fields,
        "packages": len(entries),
        "digests_identical": agreement["digests_identical"],
        "statuses": statuses,
        "tangent_train_segments": sum(
            package["tangents"]["train_segments_covered"]
            for package in report["packages"].values()
        ),
        "tangent_missing": sum(
            len(package["tangents"]["missing_train_segments"])
            for package in report["packages"].values()
        ),
    }
    report["status"] = (
        "export_bridge_established"
        if all(value != "native_snapshot_only" for value in statuses.values())
        else "partial"
    )
    report["limits"] = [
        "the prefab lane template and the integer flag-name tables are observed catalogs, not export bytes; both are hash-bound and leave-one-package-out checked",
        "the two stock controls need their own package's prefab template for lanes; their tangents and all segment and node topology come directly from the export bytes",
        "node OneWayIn/OneWayOut flag names are recomputed by the game at load and are never used",
        "the exports carry no query, outcome or path, and this audit reads none",
        "FILE identity is not memory attestation or strict no-mods",
    ]
    if args.check:
        frozen = json.loads(AUDIT.read_text())
        for key in ("packages", "totals", "status", "precision", "exporter"):
            if frozen[key] != report[key]:
                raise SystemExit(f"bridge audit is not reproducible: {key}")
        print(
            json.dumps(
                {"checked": True, "bridge_audit_sha256": binding.file_digest(AUDIT)}
            )
        )
        return
    AUDIT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "statuses": statuses,
                "digests_identical": agreement["digests_identical"],
                "fields": {key: value["rate"] for key, value in fields.items()},
                "tangent_train_segments": report["totals"]["tangent_train_segments"],
                "bridge_audit_sha256": binding.file_digest(AUDIT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
