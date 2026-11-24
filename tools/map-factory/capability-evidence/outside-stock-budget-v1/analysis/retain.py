"""Retain raw bytes as deterministic gzip members and verify exact reconstruction."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path

import study


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def pack(raw, evaluation, audit):
    report = study.read(evaluation)
    paths = sorted(p for p in raw.rglob("*") if p.is_file())
    actual = {str(p.relative_to(raw)): study.sha(p) for p in paths}
    if actual != report["raw_integrity"]:
        raise ValueError("raw file key set or bytes changed after scoring")
    entries = {}
    for path in paths:
        rel = path.relative_to(raw)
        target = study.HERE / "raw" / Path(str(rel) + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        with target.open("xb") as stream:
            stream.write(gzip.compress(data, mtime=0))
        entries[str(rel)] = {
            "raw_sha256": sha_bytes(data),
            "raw_bytes": len(data),
            "retained": str(target.relative_to(study.HERE)),
            "retained_sha256": study.sha(target),
        }
    outputs = {}
    for name, path in [("evaluation", evaluation), ("audit", audit)]:
        target = study.HERE / (name + ".json.gz")
        data = path.read_bytes()
        with target.open("xb") as stream:
            stream.write(gzip.compress(data, mtime=0))
        outputs[name] = {
            "raw_sha256": sha_bytes(data),
            "retained": target.name,
            "retained_sha256": study.sha(target),
        }
    study.freeze(
        study.HERE / "retention.json",
        {
            "source_sha256": study.sha(Path(__file__)),
            "files": entries,
            "reports": outputs,
        },
    )


def verify(out=None):
    manifest = study.read(study.HERE / "retention.json")
    if manifest["source_sha256"] != study.sha(Path(__file__)):
        raise ValueError("retention source changed")
    if out is not None:
        out.mkdir(parents=True, exist_ok=False)
    for rel, row in manifest["files"].items():
        safe = Path(rel)
        if safe.is_absolute() or ".." in safe.parts:
            raise ValueError("unsafe retained path")
        path = study.HERE / row["retained"]
        if study.sha(path) != row["retained_sha256"]:
            raise ValueError("retained bytes changed")
        data = gzip.decompress(path.read_bytes())
        if sha_bytes(data) != row["raw_sha256"] or len(data) != row["raw_bytes"]:
            raise ValueError("raw bytes do not reconstruct")
        if out is not None:
            target = out / safe
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    for row in manifest["reports"].values():
        path = study.HERE / row["retained"]
        if (
            study.sha(path) != row["retained_sha256"]
            or sha_bytes(gzip.decompress(path.read_bytes())) != row["raw_sha256"]
        ):
            raise ValueError("report reconstruction differs")
    report = study.read(study.HERE / "evaluation.json.gz")
    if report["raw_integrity"] != {
        rel: row["raw_sha256"] for rel, row in manifest["files"].items()
    }:
        raise ValueError("scored raw membership differs")
    print(
        study.encoded(
            {
                "verified": True,
                "raw_files": len(manifest["files"]),
                "reports": len(manifest["reports"]),
            }
        ).decode()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pack")
    p.add_argument("--raw", type=Path, required=True)
    p.add_argument("--evaluation", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    p = sub.add_parser("verify")
    p.add_argument("--unpack", type=Path)
    args = parser.parse_args()
    if args.command == "pack":
        pack(args.raw, args.evaluation, args.audit)
    else:
        verify(args.unpack)
