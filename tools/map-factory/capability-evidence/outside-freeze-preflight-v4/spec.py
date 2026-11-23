"""One byte-validated future spec; no queue, launcher, or observed outcomes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CAP = HERE.parent
ROOT = CAP.parents[2]
OLD = CAP / "outside-readiness-stock-v2"
PIN = "4eca4d291cc133513e8bac6484185d3a3b6e80ae"
PREFIX = HERE.relative_to(ROOT).as_posix()
OWN = frozenset(
    PREFIX + "/" + n
    for n in (
        "spec.py",
        "consumer.py",
        "pipeline.py",
        "lifecycle.py",
        "verify.py",
    )
)
sys.path[:0] = [str(OLD), str(CAP / "outside-readiness-v1")]
import schema_v3  # noqa: E402
import schema  # noqa: E402
from evidence import ArtifactStore, sha256  # noqa: E402
from protocol import ProtocolError, exact, decode  # noqa: E402


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hashed(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return decode(Path(path).read_bytes())


def put(store, data):
    key = hashed(data)
    path = store.root / key
    if path.exists() and path.read_bytes() != data:
        raise ProtocolError("retained byte collision/corruption")
    if not path.exists():
        path.write_bytes(data)
    return key


def put_json(store, value):
    return put(store, canonical(value))


def closure_keys():
    return schema_v3.SOURCE_KEYS_V3 | OWN


def provenance_keys():
    # Schema-defined legacy build/measurement closure, not caller-selected keys.
    return frozenset(read(OLD / "freeze.json")["source_files"]) | OWN


def source_map(keys, root=ROOT):
    return {n: hashed((root / n).read_bytes()) for n in sorted(keys)}


def role(files):
    return {"files": files, "sha256": digest(files)}


def check_role(value, keys, root, store, name):
    row = exact(value, {"files", "sha256"}, name)
    files = exact(row["files"], set(keys), name + " exact keys")
    pinned = read(OLD / "freeze.json")["source_files"]
    for path, key in files.items():
        sha256(key, name)
        if path in pinned and pinned[path] != key:
            raise ProtocolError(name + ": accepted source binding changed: " + path)
        if hashed((root / path).read_bytes()) != key:
            raise ProtocolError(name + ": source byte change: " + path)
        # A declared Python __init__.py can legitimately be zero bytes. Source
        # equality still hashes actual retained bytes; no missing-file fallback.
        retained = (store.root / key).read_bytes()
        if hashed(retained) != key:
            raise ProtocolError(name + ": corrupt retained source: " + path)
    if row["sha256"] != digest(files):
        raise ProtocolError(name + ": role digest differs")
    schema.bound_json(store, row["sha256"], files, name)


def reject_legacy(freeze):
    """The first check runs before looking up any local build or private byte."""
    files = exact(
        freeze["source_files"],
        set(schema_v3.SOURCE_KEYS_V3),
        "legacy freeze consumer closure (before build lookup)",
    )
    if freeze["source_sha256"] != digest(files):
        raise ProtocolError("legacy freeze closure digest differs")


def staged_sources(build, root=ROOT):
    """Pure replay of the declared copy/transform; never writes a build stage."""
    import build_v2

    base = root / "tools/cs1-harness/mod"
    values = {p.name: p.read_bytes() for p in sorted(base.glob("*.cs"))}
    if {n: hashed(v) for n, v in values.items()} != build["original_sources"]:
        raise ProtocolError("original C# source bytes differ")
    text = values["NetworkOps.cs"].decode()
    for before, after in build_v2.NETWORK_PATCHES.items():
        if text.count(before) != 1:
            raise ProtocolError("C# transform anchor differs")
        text = text.replace(before, after)
    before = build_v2.BUILD_INDEX_REGISTRATION
    if text.count(before) != 1:
        raise ProtocolError("C# registration anchor differs")
    text = text.replace(before, before + "\n" + build_v2.BUILD_INDEX_REGISTER_LINE)
    before = "        static Dictionary<string, object> Result("
    if text.count(before) != 1:
        raise ProtocolError("C# method anchor differs")
    text = text.replace(before, build_v2.BUILD_INDEX_OP + before)
    values["NetworkOps.cs"] = text.encode()
    if {n: hashed(v) for n, v in values.items()} != build["staged_sources"]:
        raise ProtocolError("transformed C# bytes differ")
    return values


def build_artifacts(build):
    return {
        "dll": build["dll"]["sha256"],
        "compiler": build["compiler"]["csc_sha256"],
        "game_executable": build["game_executable_sha256"],
        **{"reference:" + n: v for n, v in build["reference_assemblies"].items()},
        **{"staged:" + n: v for n, v in build["staged_sources"].items()},
    }


INPUT_FILES = {
    "catalog": CAP / "outside-stock-budget-v1/prior-stock-catalogs.json",
    **{
        n: OLD / (n + suffix)
        for n, suffix in (
            ("inventory", ".json"),
            ("exclusions", ".json"),
            ("selection", ".json"),
            ("features", ".json.gz"),
            ("requests", ".json"),
            ("predictions", ".json"),
        )
    },
}


def input_artifacts(old, controls):
    return {
        **{n: hashed(p.read_bytes()) for n, p in INPUT_FILES.items()},
        "protocol": digest(old["protocol"]),
        **{"package:" + c["case_id"]: c["sha256"] for c in old["controls"]},
        **{"graph:" + c["case_id"]: c["exact_graph_sha256"] for c in controls},
        **{"requests:" + c["case_id"]: c["request_sha256"] for c in controls},
        **{"predictions:" + c["case_id"]: c["prediction_sha256"] for c in controls},
        **{
            "holdout_package:" + r["case_id"]: r["package_sha256"]
            for r in old["holdout"]
        },
    }


@dataclass(frozen=True)
class ValidatedSpec:
    """Immutable canonical bytes, not a mutable dict escaping validation."""

    encoded: bytes

    @property
    def value(self):
        return json.loads(self.encoded)

    @property
    def sha256(self):
        return hashed(self.encoded)

    def bindings(self):
        value = self.value
        return {
            "spec_sha256": self.sha256,
            "measurement_provenance_sha256": value["sources"]["measurement_build"][
                "sha256"
            ],
            "source_sha256": value["sources"]["readiness_helpers"]["sha256"],
            "protocol_sha256": value["inputs"]["protocol"],
            "dll_sha256": value["build_artifacts"]["dll"],
        }


def validate(value, store: ArtifactStore, root=ROOT):
    if type(value) is dict and "source_files" in value:
        reject_legacy(value)
        raise ProtocolError("legacy freeze is not a v4 future spec")
    v = exact(
        value,
        {
            "version",
            "source_pin",
            "purpose",
            "sources",
            "inputs",
            "build_receipt",
            "build_artifacts",
            "controls",
            "prior_sessions",
            "expected_policy",
            "stop_policy",
        },
        "future spec",
    )
    if type(v["version"]) is not int or v["version"] != 4 or v["source_pin"] != PIN:
        raise ProtocolError("future spec version/source pin differs")
    if v["purpose"] != "OFFLINE_FUTURE_REHEARSAL_NOT_LAUNCH_AUTHORITY":
        raise ProtocolError("future spec purpose differs")
    roles = exact(
        v["sources"], {"measurement_build", "readiness_helpers"}, "source roles"
    )
    # Contract first, then provenance, then build locators. Superset is NOT valid.
    check_role(
        roles["readiness_helpers"], closure_keys(), root, store, "readiness_helpers"
    )
    check_role(
        roles["measurement_build"], provenance_keys(), root, store, "measurement_build"
    )
    old = read(OLD / "freeze.json")
    if v["build_receipt"] != hashed(canonical(old["build"])):
        raise ProtocolError("retained build receipt differs")
    schema.bound_json(store, v["build_receipt"], old["build"], "build receipt")
    artifacts = exact(
        v["build_artifacts"], set(build_artifacts(old["build"])), "build roles"
    )
    if artifacts != build_artifacts(old["build"]):
        raise ProtocolError("build role binding differs")
    for name, key in artifacts.items():
        store.read(key, "private build artifact " + name)
    import build_v2

    if (
        build_v2.module_version_id(store.root / artifacts["dll"])
        != old["build"]["dll"]["mvid"]
    ):
        raise ProtocolError("retained DLL MVID differs")
    for name, data in staged_sources(old["build"], root).items():
        if artifacts["staged:" + name] != hashed(data):
            raise ProtocolError("C# recipe binding differs")
    templates = read(OLD / "bundle.json")["controls"]
    expected_inputs = input_artifacts(old, templates)
    exact(v["inputs"], set(expected_inputs), "input roles")
    if v["inputs"] != expected_inputs:
        raise ProtocolError("input role binding differs")
    for name, key in v["inputs"].items():
        store.read(key, "input artifact " + name)
    if type(v["controls"]) is not list or len(v["controls"]) != len(templates):
        raise ProtocolError("control input set differs")
    helper = roles["readiness_helpers"]
    for actual, template in zip(v["controls"], templates, strict=True):
        expected = dict(
            template, source_files=helper["files"], source_sha256=helper["sha256"]
        )
        expected["consumed_fields"] = consumed(
            store, expected, old["protocol"], retain=False
        )
        if canonical(actual) != canonical(expected):
            raise ProtocolError("control input/consumed source construction differs")
        for row in actual["requests"]:
            schema.request_plan(row, "future control request")
    if v["prior_sessions"] != old["prior_sessions"] + [
        o["session_id"] for o in read(OLD / "bundle.json")["observations"].values()
    ]:
        raise ProtocolError("prior session exclusions differ")
    for name in ("expected_policy", "stop_policy"):
        if type(v[name]) is not dict or canonical(v[name]) != canonical(old[name]):
            raise ProtocolError(name + " differs")
    candidate = ValidatedSpec(canonical(v))
    import consumer

    for control in v["controls"]:
        consumer.validate_frozen(control, store, candidate)
    return candidate


def consumed(store, control, protocol, *, retain):
    graph = store.json(control["exact_graph_sha256"], "fixed control input graph")
    values = schema.consumed_values(
        graph, control["source_files"], control["requests"], protocol
    )
    result = {}
    for field, value in values.items():
        row = {
            "field": field,
            "graph_sha256": control["exact_graph_sha256"],
            "source_sha256": control["source_sha256"],
            "values": value,
        }
        key = put_json(store, row) if retain else digest(row)
        if not retain:
            schema.bound_json(store, key, row, "consumed input " + field)
        result[field] = key
    return result


def build(store):
    """Real builder over repository and retained private bytes, never outcomes."""
    old = read(OLD / "freeze.json")
    roles = {
        "measurement_build": role(source_map(provenance_keys())),
        "readiness_helpers": role(source_map(closure_keys())),
    }
    for descriptor in roles.values():
        for name in descriptor["files"]:
            put(store, (ROOT / name).read_bytes())
        put_json(store, descriptor["files"])
    receipt = put_json(store, old["build"])
    for data in staged_sources(old["build"]).values():
        put(store, data)
    for path in INPUT_FILES.values():
        put(store, path.read_bytes())
    put_json(store, old["protocol"])
    templates = read(OLD / "bundle.json")["controls"]
    controls = []
    for template in templates:
        c = dict(
            template,
            source_files=roles["readiness_helpers"]["files"],
            source_sha256=roles["readiness_helpers"]["sha256"],
        )
        c["consumed_fields"] = consumed(store, c, old["protocol"], retain=True)
        controls.append(c)
    value = {
        "version": 4,
        "source_pin": PIN,
        "purpose": "OFFLINE_FUTURE_REHEARSAL_NOT_LAUNCH_AUTHORITY",
        "sources": roles,
        "inputs": input_artifacts(old, templates),
        "build_receipt": receipt,
        "build_artifacts": build_artifacts(old["build"]),
        "controls": controls,
        "prior_sessions": old["prior_sessions"]
        + [o["session_id"] for o in read(OLD / "bundle.json")["observations"].values()],
        "expected_policy": old["expected_policy"],
        "stop_policy": old["stop_policy"],
    }
    return validate(value, store)


def ready(value, store, root=ROOT):
    spec = validate(value, store, root)
    return {
        "stage": "ReadyToLaunchControls",
        "offline_compatible": True,
        "launch_authorized": False,
        "control_admission": "unknown",
        "pre_export_qualification": "unknown",
        "spec_sha256": spec.sha256,
    }
