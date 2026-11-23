"""Load original retained bytes in place, verifying both compressed/raw hashes."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load(name):
    manifest = json.loads((HERE / "bindings.json").read_bytes())
    row = manifest["fixtures"][name]
    data = (ROOT / row["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError(f"fixture changed: {name}")
    raw = gzip.decompress(data) if row["path"].endswith(".gz") else data
    if hashlib.sha256(raw).hexdigest() != row["raw_sha256"]:
        raise ValueError(f"raw fixture changed: {name}")
    return raw


def observation(name):
    return json.loads(load(name))
