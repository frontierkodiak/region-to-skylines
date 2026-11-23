"""Off-game preparation and loopback proof. No native execution CLI is supplied."""

import argparse
from pathlib import Path

import accepted_api as api
import candidate
from entry import Request
from exercise import ConstructedAuthority, Factory, run
from wire import encoded


def request_for(frozen):
    native = api.adapter_spec.AdapterSpec(
        api.spec.canonical(frozen["v5"]),
        api.spec.ValidatedSpec(api.spec.canonical(frozen["v5"]["v4"])),
    )
    return Request(
        api.spec.digest(frozen),
        api.spec.canonical(native.bindings()),
        "CONSTRUCTED-PL1321",
        api.spec.canonical(frozen["limits"]),
        "CONSTRUCTED",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "exercise", "exercise-study"])
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--source-revision")
    p.add_argument("--maps", type=Path)
    p.add_argument("--freeze", type=Path)
    a = p.parse_args()
    store = api.spec.ArtifactStore(a.store)
    if a.action == "prepare":
        if not a.source_revision or a.maps is None:
            p.error("prepare requires explicit --source-revision and --maps")
        value = candidate.prepare(store, a.source_revision, a.maps, a.out)
        with a.out.open("xb") as f:
            f.write(encoded(value))
        print(
            encoded(
                dict(
                    freeze_sha256=api.spec.digest(value),
                    source_revision=value["source_revision"],
                    selected=store.json(value["inputs"]["selection"], "selection"),
                    native_openings=0,
                )
            ).decode()
        )
    else:
        if a.freeze is None:
            p.error("exercise requires --freeze")
        frozen = api.spec.read(a.freeze)
        request = request_for(frozen)
        factory = Factory(a.out)
        if a.action == "exercise-study":
            from exercise import study_run

            value = study_run(frozen, store, a.out)
        else:
            value = run(frozen, store, request, ConstructedAuthority(request), factory)
        (a.out / "proof.json").write_bytes(encoded(value))
        summary = (
            value["result"]
            if "result" in value
            else {k: value[k] for k in ("kind", "control_admission", "native_requests")}
        )
        print(encoded(summary).decode())


if __name__ == "__main__":
    main()
