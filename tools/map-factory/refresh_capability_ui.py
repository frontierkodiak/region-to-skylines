"""Bind UI-only evolution without rewriting any historical/native contract."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "tools/map-factory/fixtures"
PREFIX = "contracts/pl1119-capability-ui-v1"
GATES = ["app.js", "build.mjs", "index.html", "package.json", "style.css"]
ADDITIONS = [
    "capabilities.json",
    "capability-evidence.js",
    "capability-evidence-worker.js",
    "capability-inputs.js",
    "capability-ledger.mjs",
    "capability-model.js",
    "capability-ui.js",
    "tools/map-factory/capabilities.py",
    "tools/map-factory/integrate_outside_evidence.py",
    "tools/map-factory/integrate_outside_v2.py",
    "tools/map-factory/capability-evidence/runtime-identities/25eb5d7018f379e7dbb25fcd4a7e3ab72ef4155f3d54fca077257d6eefb7d8e0.json",
    "tools/map-factory/capability-evidence/runtime-identities/3499552b48486b2822a80e5ab101af8ad0e1cd70c4512f606c5299d7fe65eb00.json",
    "tools/map-factory/capability-evidence/runtime-identities/b844c6cd44dd32189294b52f03b40fd2e7eb4e8a0e6b51374d3ad29ea584e4c9.json",
    "tools/map-factory/capability-evidence/runtime-identities/b8cc86a4540f96db8628d742afc534caa69679f7c29dac5764ee3c46a14a628d.json",
    "tools/map-factory/capability-evidence/pl1119-v3-predictions.json",
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def refresh():
    active_raw = (FOLDER / "active.json").read_bytes()
    current_raw = (FOLDER / json.loads(active_raw)["current"]).read_bytes()
    current = json.loads(current_raw)
    gates = {}
    for name in GATES:
        relative = f"{PREFIX}/baseline/{name}"
        baseline = FOLDER / relative
        # Only accept the original archived gate, never today's changed source.
        if not baseline.exists():
            raise ValueError(f"Archive the predecessor source first: {relative}")
        if sha(baseline.read_bytes()) != current["export_gate_files_sha256"][name]:
            raise ValueError(f"Historical gate mismatch: {name}")
        gates[name] = {
            "file": relative,
            "current_sha256": sha((ROOT / name).read_bytes()),
        }
    adoption = {
        "schema": 1,
        "scope": "Capability checks and four retained exact-context path certificates; physical writers and historical native qualification unchanged",
        "predecessor_active_sha256": sha(active_raw),
        "predecessor_contract_sha256": sha(current_raw),
        "archived_gates": gates,
        "added_files_sha256": {
            name: sha((ROOT / name).read_bytes()) for name in ADDITIONS
        },
    }
    (FOLDER / PREFIX / "adoption.json").write_text(
        json.dumps(adoption, indent=2) + "\n"
    )


if __name__ == "__main__":
    refresh()
