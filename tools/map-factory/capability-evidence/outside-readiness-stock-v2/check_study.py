"""Offline CLI for the v2 cohort: preflight, byte-backed bundle, module binding.

`verify` proves the frozen source/build/inputs and the accepted immutability.
`bundle` runs the version-3 readiness gate over retained bytes.
`rebind` refreshes this prefix's own integrity manifest after a deliberate
source edit; it never regenerates old freezes, predictions or outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import stock_v2 as study

HERE = study.HERE


def module_files():
    return {
        str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(HERE.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name not in ("module.json",)
    }


def rebind():
    manifest = {
        "module": "outside-readiness-stock-v2",
        "version": 3,
        "source": study.SOURCE,
        "target": study.TARGET,
        "created_at": study.now(),
        "files": module_files(),
    }
    study.write(HERE / "module.json", manifest)
    return len(manifest["files"])


def verify():
    result = study.preflight()
    manifest = study.read(HERE / "module.json")
    actual = module_files()
    if actual != manifest["files"]:
        missing = sorted(set(manifest["files"]) - set(actual))
        extra = sorted(set(actual) - set(manifest["files"]))
        raise ValueError(f"module file set differs; missing={missing} extra={extra}")
    for name, hashed in manifest["files"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != hashed:
            raise ValueError(f"module file changed: {name}")
    result["module_files"] = len(manifest["files"])
    result["verified"] = True
    return result


def bundle(path, evidence):
    from evidence import ArtifactStore
    import readiness_v3
    from protocol import ProtocolError, decode, exact
    from schema import strings

    payload = exact(
        decode(Path(path).read_bytes()),
        {"version", "controls", "observations", "policy", "prior_sessions"},
        "bundle",
    )
    if payload["version"] != 2:
        raise ProtocolError("unsupported bundle version")
    result = readiness_v3.check(
        payload["controls"],
        payload["observations"],
        payload["policy"],
        set(strings(payload["prior_sessions"], "prior_sessions", empty=True)),
        ArtifactStore(Path(evidence)),
    )
    return {
        "ready_for_measurement": result.ready_for_measurement,
        "reasons": list(result.reasons),
        "pre_export_qualification": result.pre_export_qualification,
        "missing_native_fact": result.missing_native_fact,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "preflight", "rebind", "bundle"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "rebind":
            print(json.dumps({"files": rebind()}, sort_keys=True))
            return 0
        if args.command == "preflight":
            print(json.dumps(study.preflight(), sort_keys=True))
            return 0
        if args.command == "bundle":
            if args.input is None or args.evidence_root is None:
                raise ValueError("bundle requires --input and --evidence-root")
            outcome = bundle(args.input, args.evidence_root)
            print(json.dumps(outcome, sort_keys=True))
            return 0 if outcome["ready_for_measurement"] else 2
        print(json.dumps(verify(), sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({"verified": False, "reasons": [str(error)]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
