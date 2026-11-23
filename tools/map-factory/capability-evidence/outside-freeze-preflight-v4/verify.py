"""Portable OFF-GAME spec build, retained-byte verification and consumer exercise."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import spec
from spec import ArtifactStore, ProtocolError
import lifecycle
import pipeline


def local_build_context(path):
    """Context availability is not a build verification or a passing fallback."""
    if path is None or not (path / "Cs1Harness.dll").is_file():
        return {
            "local_fresh_build": "unverified",
            "reason": "explicit local build context missing",
        }
    return {
        "local_fresh_build": "unsupported",
        "reason": "this offline tool does not compile or attest a local build",
    }


def immutability():
    groups = {}
    for name, count in (
        ("outside-stock-budget-v1", 142),
        ("outside-readiness-v1", 24),
        ("outside-readiness-stock-v2", 26),
    ):
        prefix = (spec.CAP / name).relative_to(spec.ROOT).as_posix()
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", spec.PIN, prefix],
            cwd=spec.ROOT,
            text=True,
        ).splitlines()
        if len(paths) != count:
            raise ProtocolError("immutable prefix file count differs: " + name)
        manifest = {}
        for path in paths:
            original = subprocess.check_output(
                ["git", "show", f"{spec.PIN}:{path}"], cwd=spec.ROOT
            )
            if (spec.ROOT / path).read_bytes() != original:
                raise ProtocolError("immutable historical byte change: " + path)
            manifest[path] = spec.hashed(original)
        groups[name] = {
            "files": count,
            "manifest_sha256": spec.digest(manifest),
            "unchanged": True,
        }
    return {
        "source_pin": spec.PIN,
        "groups": groups,
        "old_fact_count": 84,
        "old_fact_verification": "entire retained audit bytes unchanged; no labels rescored",
        "PL1313_holdout_cells": "six unobserved Unknown; not changed or scored",
    }


def seed_store(destination, retained, compiler, packages=()):
    """Copy to a new task-owned private store; never mutate the old holding."""
    destination.mkdir(parents=True, exist_ok=False)
    store = ArtifactStore(destination)
    for path in retained.iterdir():
        if path.is_file():
            spec.sha256(path.name, "retained filename")
            if spec.hashed(path.read_bytes()) != path.name:
                raise ProtocolError("corrupt retained seed artifact")
            shutil.copyfile(path, destination / path.name)
    expected = spec.read(spec.OLD / "freeze.json")["build"]["compiler"]["csc_sha256"]
    data = compiler.read_bytes()
    if spec.hashed(data) != expected:
        raise ProtocolError("supplied compiler bytes differ from declared receipt")
    spec.put(store, data)
    for path in packages:
        spec.put(store, path.read_bytes())
    return store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["seed", "build", "preflight", "legacy", "exercise", "immutability"],
    )
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retained", type=Path)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument("--package", type=Path, action="append", default=[])
    parser.add_argument("--local-build-context", type=Path)
    args = parser.parse_args()
    store = ArtifactStore(args.store)
    exit_code = 0
    try:
        if args.command == "seed":
            if args.retained is None or args.compiler is None:
                parser.error("seed requires --retained and --compiler")
            seed_store(args.store, args.retained, args.compiler, args.package)
            result = {"private_store_seeded": True}
        elif args.command == "build":
            result = spec.build(store).value
        elif args.command == "immutability":
            result = immutability()
        elif args.command == "legacy":
            spec.validate(spec.read(spec.OLD / "freeze.json"), store)
            raise AssertionError("legacy unexpectedly passed")
        else:
            if args.freeze is None:
                parser.error("preflight/exercise requires --freeze")
            validated = spec.validate(spec.read(args.freeze), store)
            if args.command == "preflight":
                result = spec.ready(validated.value, store)
                result.update(local_build_context(args.local_build_context))
            else:
                receipt = lifecycle.fixture_receipt()
                records, policy = pipeline.constructed(validated, store, receipt)
                value = pipeline.bundle(validated, records, policy, store)
                result = pipeline.gate(value, validated.value, store)
                result["lifecycle"] = receipt
                result["spec_sha256"] = validated.sha256
    except (ProtocolError, ValueError, OSError, KeyError, TypeError) as error:
        result = {
            "pass": False,
            "stage": "BeforeQueueAccess",
            "reason": str(error),
            "control_admission": "unknown",
            "pre_export_qualification": "unknown",
        }
        exit_code = 2
        if args.command == "legacy":
            result["source_pin"] = spec.PIN
            result["legacy_freeze_sha256"] = spec.hashed(
                (spec.OLD / "freeze.json").read_bytes()
            )
    if args.command == "build" and exit_code == 0:
        with args.output.open("xb") as target:
            target.write(spec.canonical(result))
    else:
        args.output.write_bytes(spec.canonical(result))
    print(json.dumps(result, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
