"""Opt-in frozen mapped-water evidence. This never constructs or widens a mask."""

import hashlib
import json
import pathlib
import re

import numpy as np

FORMAT = "cs1-water-mask-u8-v1"
FROZEN_FILE = "mapped-water.u8"
GRID_N = 1081


def read_mask(path: pathlib.Path, spec: dict) -> tuple[np.ndarray, bytes]:
    if (
        not isinstance(spec, dict)
        or spec.get("format") != FORMAT
        or not isinstance(spec.get("file"), str)
        or not spec["file"]
        or pathlib.Path(spec["file"]).name != spec["file"]
        or spec["file"] in {".", ".."}
        or not isinstance(spec.get("sha256"), str)
        or not re.fullmatch("[0-9a-f]{64}", spec["sha256"])
    ):
        raise ValueError("invalid mapped_water contract")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
        raise ValueError("mapped_water SHA256 mismatch")
    if len(raw) != GRID_N * GRID_N:
        raise ValueError("mapped_water must contain exactly 1081x1081 uint8 cells")
    mask = np.frombuffer(raw, dtype=np.uint8).reshape(GRID_N, GRID_N)
    if not np.isin(mask, [0, 1]).all():
        raise ValueError("mapped_water cells must be binary 0/1")
    return mask.astype(bool), raw


def freeze(probes: pathlib.Path, out: pathlib.Path):
    """Validate before any session starts; freeze precisely the validated bytes."""
    meta = json.loads(probes.read_text())
    if isinstance(meta, dict) and "mapped_water" in meta:
        spec = meta["mapped_water"]
        # Validate the filename before using it to resolve a source file.
        filename = spec.get("file") if isinstance(spec, dict) else None
        if not isinstance(filename, str) or pathlib.Path(filename).name != filename:
            raise ValueError("invalid mapped_water file")
        _, raw = read_mask(probes.parent / filename, spec)
        (out / FROZEN_FILE).write_bytes(raw)
