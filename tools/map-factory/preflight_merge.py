"""Reject a clean textual merge that changes the reviewed writer or its evidence.

Uses Git's trial merge tree without changing a branch or working tree. This is
not a substitute for local tests or review; it detects current-main drift at
the last landing boundary, including the failure found by PL-996.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
FIXTURES = "tools/map-factory/fixtures/"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def blob(ref, path):
    return git("show", f"{ref}:{path}")


def preflight(head, base):
    active = json.loads(blob(head, FIXTURES + "active.json"))
    contract = json.loads(blob(head, FIXTURES + active["current"]))
    trial = subprocess.run(
        ["git", "merge-tree", "--write-tree", head, base],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if trial.returncode:
        raise ValueError(
            "Trial merge conflicts; inspect the actual merge before landing"
        )
    tree = trial.stdout.splitlines()[0]
    mismatches = []
    expected = dict(contract["source_files_sha256"])
    expected[FIXTURES + "active.json"] = hashlib.sha256(
        blob(head, FIXTURES + "active.json")
    ).hexdigest()
    expected[FIXTURES + active["current"]] = hashlib.sha256(
        blob(head, FIXTURES + active["current"])
    ).hexdigest()
    parents = contract.get("previous_contracts", {})
    if "historical_current_contract_sha256" in contract:
        parents = {
            **parents,
            "historical": {
                "file": "current.json",
                "sha256": contract["historical_current_contract_sha256"],
            },
        }
    expected.update({FIXTURES + p["file"]: p["sha256"] for p in parents.values()})
    for binding in (
        contract.get("predecessor"),
        contract.get("proof"),
        *contract.get("baseline_sources", {}).values(),
    ):
        if binding:
            expected[FIXTURES + binding["file"]] = binding["sha256"]
    for path, digest in expected.items():
        if hashlib.sha256(blob(tree, path)).hexdigest() != digest:
            mismatches.append(path)
    return {
        "safe_reviewed_binding": not mismatches,
        "head": git("rev-parse", head).decode().strip(),
        "base": git("rev-parse", base).decode().strip(),
        "trial_tree": tree,
        "checked_files": len(expected),
        "changed_reviewed_bindings": mismatches,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args()
    result = preflight(args.head, args.base)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["safe_reviewed_binding"] else 1)
