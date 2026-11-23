"""Offline CLI: verify bindings, diagnose retained controls, or check a v1 bundle."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess

import fixtures
from protocol import ProtocolError, decode, exact
from readiness import check

HERE = fixtures.HERE
ROOT = fixtures.ROOT


def verify():
    binding = json.loads((HERE / "bindings.json").read_bytes())
    for relative, expected in binding["sources"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"source/retained file changed: {relative}")
    for name in binding["fixtures"]:
        fixtures.load(name)
    integrity = fixtures.HERE.parent / "outside-stock-budget-v1/integrity.json"
    files = json.loads(integrity.read_bytes())["files"]
    actual = {
        str(p.relative_to(integrity.parent))
        for p in integrity.parent.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    if actual != set(files) | {"integrity.json"}:
        raise ValueError("old publication file set differs")
    for relative, expected in files.items():
        if (
            hashlib.sha256((integrity.parent / relative).read_bytes()).hexdigest()
            != expected
        ):
            raise ValueError(f"old publication file changed: {relative}")
    # Compare every tracked old file, not merely our guessed source closure.
    changes = subprocess.check_output(
        ["git", "diff", "--name-only", binding["source_commit"], "--"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    prefix = str(HERE.relative_to(ROOT)) + "/"
    if any(not path.startswith(prefix) for path in changes):
        raise ValueError("change outside new readiness prefix")
    manifest = json.loads((HERE / "module.json").read_bytes())
    for name, expected in manifest["files"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"new module binding changed: {name}")
    return {
        "verified": True,
        "old_publication_files": len(files) + 1,
        "source_and_retained_files": len(binding["sources"]),
        "module_files": len(manifest["files"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "retained-controls", "bundle"])
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    try:
        receipt = verify()
        if args.command == "verify":
            print(json.dumps(receipt, sort_keys=True))
            return 0
        if args.command == "retained-controls":
            controls = fixtures.observation("freeze")["controls"]
            observations = {
                c["case_id"]: fixtures.observation(name)
                for c, name in zip(controls, ("asanu", "hanami"))
            }
            result = check(controls, observations, {}, set())
        else:
            if args.input is None:
                raise ProtocolError("--input required")
            bundle = exact(
                decode(args.input.read_bytes()),
                {"version", "controls", "observations", "policy", "prior_sessions"},
                "bundle",
            )
            if type(bundle["version"]) is not int or bundle["version"] != 1:
                raise ProtocolError("unsupported bundle version")
            result = check(
                bundle["controls"],
                bundle["observations"],
                bundle["policy"],
                set(bundle["prior_sessions"]),
            )
        print(json.dumps(asdict(result), sort_keys=True))
        return 0 if result.ready_for_measurement else 2
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(
            json.dumps(
                {
                    "ready_for_measurement": False,
                    "pre_export_qualification": "unknown",
                    "reasons": [str(error)],
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
