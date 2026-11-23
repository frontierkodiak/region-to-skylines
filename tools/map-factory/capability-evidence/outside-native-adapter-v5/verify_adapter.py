"""Reproduce the off-game fresh build, freeze and actual adapter lifecycle."""

import argparse
from pathlib import Path
import subprocess

from api import ROOT, PIN, spec
import adapter_spec
import adapter
import fresh_build


def preservation():
    groups = {}
    for name, count in [
        ("outside-stock-budget-v1", 142),
        ("outside-readiness-v1", 24),
        ("outside-readiness-stock-v2", 26),
        ("outside-freeze-preflight-v4", 15),
    ]:
        prefix = "tools/map-factory/capability-evidence/" + name
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", PIN, prefix], cwd=ROOT, text=True
        ).splitlines()
        if len(paths) != count:
            raise ValueError("historical file count differs: " + name)
        hashes = {}
        for path in paths:
            original = subprocess.check_output(
                ["git", "show", PIN + ":" + path], cwd=ROOT
            )
            if (ROOT / path).read_bytes() != original:
                raise ValueError("historical bytes changed: " + path)
            hashes[path] = spec.hashed(original)
        groups[name] = dict(
            files=count, manifest_sha256=spec.digest(hashes), unchanged=True
        )
    return dict(pin=PIN, groups=groups, old_labels_rescored=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "exercise", "preserve"])
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--dotnet-root", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    store = spec.ArtifactStore(args.store)
    args.run.mkdir(parents=True, exist_ok=True)
    if args.action == "build":
        if args.dotnet_root is None:
            parser.error("--dotnet-root required for fresh build")
        receipt = fresh_build.build(store, args.run / "fresh-build", args.dotnet_root)
        (args.run / "fresh-build.json").write_bytes(spec.canonical(receipt))
        native = adapter_spec.build(store, receipt)
        with (args.run / "adapter-freeze.json").open("xb") as out:
            out.write(native.encoded)
        result = dict(
            spec_sha256=native.sha256,
            binding=native.bindings(),
            fresh_dll=receipt["dll"],
            mvid=receipt["mvid"],
            native_requests=0,
        )
    elif args.action == "exercise":
        if args.freeze is None:
            parser.error("--freeze required")
        native = adapter_spec.validate(spec.read(args.freeze), store)
        # This is explicitly a stub-only grant, never future study authority.
        grant = dict(
            kind="OFFLINE_CONSTRUCTED_ONLY",
            spec_sha256=native.sha256,
            binding=native.bindings(),
        )
        transport = adapter.RecordingTransport()
        bundle, result = adapter.exercise(
            native.descriptor, store, args.run / "processes", grant, transport
        )
        (args.run / "bundle.json").write_bytes(spec.canonical(bundle))
        (args.run / "lifecycle.json").write_bytes(spec.canonical(bundle["lifecycle"]))
        (args.run / "effect-log.json").write_bytes(spec.canonical(transport.calls))
        result["binding"] = native.bindings()
    else:
        result = preservation()
    (args.run / (args.action + "-result.json")).write_bytes(spec.canonical(result))
    print(spec.canonical(result).decode())


if __name__ == "__main__":
    main()
