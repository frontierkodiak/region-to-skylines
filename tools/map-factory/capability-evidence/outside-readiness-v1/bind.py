"""Reproducible source/fixture closure generator; only writes this new prefix."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STUDY = HERE.parent / "outside-stock-budget-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def generate():
    frozen = json.loads((STUDY / "freeze.json").read_bytes())
    sources = {p: h for group in frozen["sources"].values() for p, h in group.items()}
    # Superset of the model/helper, CRP-reader and public wire-producer closure.
    # Includes both historic and repaired sources, never changes their semantics.
    for p in STUDY.rglob("*"):
        if p.is_file():
            sources[str(p.relative_to(ROOT))] = sha(p.read_bytes())
    fixtures = {}
    names = {
        "asanu": "raw/stock-1/observation.json.gz",
        "hanami": "raw/stock-2/observation.json.gz",
        "freeze": "freeze.json",
        "schema_failure": "analysis/frozen-scorer-failure.log",
        "schema_correction": "analysis/source-fix.json",
        "audit": "audit.json.gz",
        "original_guard": "pre-native-preparation-v1.zip",
    }
    for name, relative in names.items():
        p = STUDY / relative
        data = p.read_bytes()
        raw = gzip.decompress(data) if p.suffix == ".gz" else data
        fixtures[name] = {
            "path": str(p.relative_to(ROOT)),
            "sha256": sha(data),
            "raw_sha256": sha(raw),
        }
    result = {
        "version": 1,
        "source_commit": "d745b14e3e207ee67f91033811958a2934fb38a4",
        "sources": sources,
        "fixtures": fixtures,
        "boundary": "file identity, not memory or native code attestation",
    }
    (HERE / "bindings.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n"
    )
    files = {
        str(p.relative_to(HERE)): sha(p.read_bytes())
        for p in HERE.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.name != "module.json"
    }
    (HERE / "module.json").write_text(
        json.dumps({"version": 1, "files": files}, sort_keys=True, indent=2) + "\n"
    )


if __name__ == "__main__":
    generate()
