"""Versioned composition: v4 inputs/helpers plus complete fresh adapter/build closure."""

from dataclasses import dataclass
import copy
import json

from api import HERE, ROOT, PIN, spec, pipeline
import fresh_build

NAMES = frozenset(
    {
        "api.py",
        "fresh_build.py",
        "adapter_spec.py",
        "adapter.py",
        "driver.py",
        "verify_adapter.py",
        "test_adapter.py",
    }
)
KEYS = {
    "version",
    "source_pin",
    "purpose",
    "v4",
    "adapter_sources",
    "fresh_build",
    "inventory",
    "api",
    "limits",
}
LIMITS = dict(
    openings=5,
    controls=12,
    holdout=18,
    requests=30,
    query_seconds=30,
    load_seconds=600,
    opening_seconds=900,
    total_seconds=4500,
    first_failure="STOP Unknown",
    retry=False,
)
API = {
    "collector": "pipeline.collector_binding",
    "policy": "pipeline.runtime_policy",
    "bundle": "pipeline.bundle",
    "facts": "consumer.opening",
    "retention": "spec.put / ArtifactStore",
    "finalizer": "lifecycle.finalize",
}


def own_keys():
    return {str((HERE / n).relative_to(ROOT)) for n in NAMES}


def raw(store, key):
    spec.sha256(key, "retained key")
    data = (store.root / key).read_bytes()
    if spec.hashed(data) != key:
        raise ValueError("retained bytes differ")
    return data


@dataclass(frozen=True)
class AdapterSpec:
    encoded: bytes
    baseline: spec.ValidatedSpec

    @property
    def descriptor(self):
        return json.loads(self.encoded)

    @property
    def value(self):
        # v4 consumer's immutable input/helper view. Never rewrite its source roles.
        return self.baseline.value

    @property
    def sha256(self):
        return spec.hashed(self.encoded)

    def bindings(self):
        d = self.descriptor
        return dict(
            self.baseline.bindings(),
            spec_sha256=self.sha256,
            dll_sha256=d["fresh_build"]["dll"],
            adapter_source_sha256=d["adapter_sources"]["sha256"],
            fresh_build_sha256=spec.digest(d["fresh_build"]),
            input_sha256=spec.digest(self.value["inputs"]),
            request_sha256=spec.digest([c["requests"] for c in self.value["controls"]]),
            api_sha256=spec.digest(d["api"]),
        )


def inventory_for(receipt):
    old = spec.read(spec.OLD / "bundle.json")["policy"]
    inventory = {
        k: copy.deepcopy(v)
        for k, v in old.items()
        if k not in {"source_sha256", "protocol_sha256", "dll_sha256"}
    }
    inventory["files"][inventory["dll_path"]] = receipt["dll"]
    inventory["assemblies"]["Cs1Harness"].update(
        sha256=receipt["dll"], mvid=receipt["mvid"]
    )
    return inventory


def build(store, receipt):
    baseline = spec.build(store)
    files = spec.source_map(own_keys())
    for name in files:
        spec.put(store, (ROOT / name).read_bytes())
    spec.put_json(store, files)
    descriptor = dict(
        version=5,
        source_pin=PIN,
        purpose="UNRUN_ADAPTER_NOT_LAUNCH_AUTHORITY",
        v4=baseline.value,
        adapter_sources=spec.role(files),
        fresh_build=receipt,
        inventory=inventory_for(receipt),
        api=API,
        limits=LIMITS,
    )
    return validate(descriptor, store)


def validate(value, store, root=ROOT):
    d = spec.exact(value, KEYS, "adapter descriptor")
    if (
        type(d["version"]) is not int
        or d["version"] != 5
        or d["source_pin"] != PIN
        or d["purpose"] != "UNRUN_ADAPTER_NOT_LAUNCH_AUTHORITY"
        or spec.canonical(d["api"]) != spec.canonical(API)
        or spec.canonical(d["limits"]) != spec.canonical(LIMITS)
    ):
        raise ValueError("adapter version/API/limits differ")
    baseline = spec.validate(d["v4"], store, root)
    role = spec.exact(d["adapter_sources"], {"files", "sha256"}, "adapter source role")
    files = spec.exact(role["files"], own_keys(), "complete adapter source closure")
    # Also refuse an unbound new executable in the new prefix.
    if {p.name for p in HERE.glob("*.py")} != NAMES:
        raise ValueError("undeclared adapter executable")
    for name, key in files.items():
        if (
            spec.hashed((root / name).read_bytes()) != key
            or raw(store, key) != (root / name).read_bytes()
        ):
            raise ValueError("adapter source byte mismatch: " + name)
    if role["sha256"] != spec.digest(files) or raw(
        store, role["sha256"]
    ) != spec.canonical(files):
        raise ValueError("adapter source role digest differs")
    fresh_build.validate(d["fresh_build"], store)
    # The actual retained receipt, not just a caller's dictionary.
    if raw(store, spec.digest(d["fresh_build"])) != spec.canonical(d["fresh_build"]):
        raise ValueError("fresh receipt differs")
    if spec.canonical(d["inventory"]) != spec.canonical(
        inventory_for(d["fresh_build"])
    ):
        raise ValueError("complete runtime inventory differs")
    result = AdapterSpec(spec.canonical(d), baseline)
    pipeline.validate_policy(
        result, pipeline.runtime_policy(result, d["inventory"]), store
    )
    return result
