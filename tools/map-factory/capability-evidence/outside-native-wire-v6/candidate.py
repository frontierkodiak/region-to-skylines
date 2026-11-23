"""New input-only cohort. No observed holdout files or old scorer is executed."""

from pathlib import Path
import subprocess

import accepted_api as api
from wire import Unknown

PIN = "4751c49e0515a8af4c3f753a8bed09f6f55e39b2"
NAMES = frozenset(
    {
        "wire.py",
        "runtime.py",
        "accepted_api.py",
        "loopback_fixture.py",
        "test_wire.py",
        "candidate.py",
        "entry.py",
        "native_session.py",
        "exercise.py",
        "wire_check.py",
        "test_integration.py",
    }
)


def inventory(directory, store):
    old = api.stock_v2
    table = old.exclusion_table()
    seen, rows, decoded, graphs = {}, [], {}, {}
    # Hash first, then sort. Dedup is first locator within content-hash order.
    paths = [(old.sha(p), str(p)) for p in Path(directory).glob("*.crp")]
    for hashed, locator in sorted(paths):
        path = Path(locator)
        excluded = list(table.get(hashed, {}).get("categories", []))
        if path.name == "CO.crp":
            excluded.append("blank_co")
        duplicate = seen.get(hashed)
        if duplicate is not None:
            excluded.append("duplicate_hash")
        seen.setdefault(hashed, locator)
        row = dict(
            sha256=hashed,
            locator=locator,
            file=path.name,
            bytes=path.stat().st_size,
            exclusion=sorted(set(excluded)) or None,
            duplicate_of=duplicate,
            supported=None,
            missing=None,
            cells=None,
            feature_sha256=None,
        )
        if not excluded:
            value, package = old.old.inventory_package(path, old.old.fixed_catalog())
            row.update(
                supported=bool(value["supported"]) and package is not None,
                missing=value["missing"],
            )
            if row["supported"]:
                row["cells"] = old.cell_counts(value)
                row["feature_sha256"] = api.spec.put_json(
                    store, old.old.serial_features(package)
                )
                decoded[hashed] = value
                graphs[hashed] = api.spec.put_json(
                    store,
                    {
                        mode: old.old.model_fields(package, mode)
                        for mode in old.MODE_ORDER
                    },
                )
        rows.append(row)
    if not any("blank_co" in (r["exclusion"] or []) for r in rows):
        raise Unknown("blank CO absent; input inventory incomplete")
    selection = old.select(rows)
    if selection["missing_cells"]:
        raise Unknown("STOP before launch: missing input-only six-cell coverage")
    for chosen in selection["selected"]:
        if (
            api.spec.put(store, Path(chosen["locator"]).read_bytes())
            != chosen["sha256"]
        ):
            raise Unknown("selected package changed during preparation")
    requests = old.holdout_requests(rows, selection, decoded)
    # Distinct new study identifiers; no new observation is read or implied.
    for row in requests:
        row["case_id"] = row["case_id"].replace("stock-v2", "wire-v6")
        row["query_id"] = row["query_id"].replace("stock-v2", "wire-v6")
    return dict(
        inventory=rows,
        exclusions=table,
        selection=selection,
        holdout=requests,
        predictions={r["query_id"]: r["prediction"] for r in requests},
        input_graphs=graphs,
    )


def git(*args):
    return subprocess.check_output(["git", *args], cwd=api.ROOT)


def closure(revision):
    """Independent tree membership, not caller-supplied maps checked against themselves."""
    files = (
        git(
            "ls-tree",
            "-r",
            "--name-only",
            revision,
            "tools/map-factory",
            "tools/cs1-harness",
        )
        .decode()
        .splitlines()
    )
    paths = {p for p in files if p.endswith((".py", ".cs", ".toml", ".lock"))}
    prefix = api.HERE.relative_to(api.ROOT).as_posix() + "/"
    actual = {p.name for p in api.HERE.glob("*.py")}
    if actual != NAMES:
        raise Unknown("undeclared new executable membership")
    if {p for p in paths if p.startswith(prefix)} != {prefix + n for n in NAMES}:
        raise Unknown("source revision omits new executable")
    # Also refuse untracked Python dependencies under both source domains.
    current = {
        str(p.relative_to(api.ROOT))
        for base in (api.ROOT / "tools/map-factory", api.ROOT / "tools/cs1-harness")
        for p in base.rglob("*.py")
        if not any(x.startswith(".") for x in p.relative_to(base).parts)
    }
    if current != {p for p in paths if p.endswith(".py")}:
        raise Unknown("untracked or absent executable dependency")
    return sorted(paths)


def prepare(store, revision, maps):
    revision = git("rev-parse", revision + "^{commit}").decode().strip()
    if git("merge-base", PIN, revision).decode().strip() != PIN:
        raise Unknown("candidate source does not descend from pin")
    source = {}
    for path in closure(revision):
        committed = git("show", revision + ":" + path)
        if (api.ROOT / path).read_bytes() != committed:
            raise Unknown("working source differs from candidate revision: " + path)
        source[path] = api.spec.put(store, committed)
    # Reuse accepted compilation only after the actual full v5 validator checks bytes.
    old_freeze = api.spec.read(api.V5 / "adapter-freeze.json")
    native = api.adapter_spec.validate(old_freeze, store)
    values = inventory(maps, store)
    result = dict(
        version=6,
        purpose="UNRUN_INPUT_ONLY_NOT_LAUNCH_AUTHORITY",
        source_pin=PIN,
        source_revision=revision,
        source_map=source,
        v5=old_freeze,
        build_reused=True,
        limits=api.adapter_spec.LIMITS,
        inputs={key: api.spec.put_json(store, value) for key, value in values.items()},
        protocol=native.value["inputs"]["protocol"],
        controls=native.value["controls"],
        required_parent_acceptance=[
            "source",
            "build",
            "spec",
            "freeze",
            "opening-budget",
        ],
        old_holdout_cells="Unknown",
    )
    return result


def validate(value, store):
    d = api.spec.exact(
        value,
        {
            "version",
            "purpose",
            "source_pin",
            "source_revision",
            "source_map",
            "v5",
            "build_reused",
            "limits",
            "inputs",
            "protocol",
            "controls",
            "required_parent_acceptance",
            "old_holdout_cells",
        },
        "v6 candidate",
    )
    if (
        type(d["version"]) is not int
        or d["version"] != 6
        or d["source_pin"] != PIN
        or d["purpose"] != "UNRUN_INPUT_ONLY_NOT_LAUNCH_AUTHORITY"
    ):
        raise Unknown("candidate type/purpose/pin differs")
    files = api.spec.exact(
        d["source_map"],
        set(closure(d["source_revision"])),
        "v6 executable/dependency roles",
    )
    for path, key in files.items():
        committed = git("show", d["source_revision"] + ":" + path)
        if (
            api.spec.hashed(committed) != key
            or committed != (api.ROOT / path).read_bytes()
            or api.adapter_spec.raw(store, key) != committed
        ):
            raise Unknown("source/retained/revision bytes differ: " + path)
    native = api.adapter_spec.validate(d["v5"], store)
    if (
        d["limits"] != api.adapter_spec.LIMITS
        or d["controls"] != native.value["controls"]
        or d["protocol"] != native.value["inputs"]["protocol"]
        or d["build_reused"] is not True
    ):
        raise Unknown("budget/protocol/control/build differs")
    if (
        d["required_parent_acceptance"]
        != ["source", "build", "spec", "freeze", "opening-budget"]
        or d["old_holdout_cells"] != "Unknown"
    ):
        raise Unknown("acceptance scope differs")
    inputs = api.spec.exact(
        d["inputs"],
        {
            "inventory",
            "exclusions",
            "selection",
            "holdout",
            "predictions",
            "input_graphs",
        },
        "input roles",
    )
    values = {k: store.json(key, "candidate " + k) for k, key in inputs.items()}
    rows = values["inventory"]
    if rows != sorted(rows, key=lambda r: (r["sha256"], r["locator"])):
        raise Unknown("inventory order differs")
    if values["exclusions"] != api.stock_v2.exclusion_table():
        raise Unknown("exclusions differ")
    if (
        values["selection"] != api.stock_v2.select(rows)
        or values["selection"]["missing_cells"]
    ):
        raise Unknown("selection/coverage differs")
    selected = {r["sha256"] for r in values["selection"]["selected"]}
    for chosen in values["selection"]["selected"]:
        retained = api.adapter_spec.raw(store, chosen["sha256"])
        if Path(chosen["locator"]).read_bytes() != retained:
            raise Unknown("selected package bytes changed")
    holdout = values["holdout"]
    if (
        len(holdout) > 18
        or not holdout
        or len({r["query_id"] for r in holdout}) != len(holdout)
    ):
        raise Unknown("holdout request count")
    if values["predictions"] != {r["query_id"]: r["prediction"] for r in holdout}:
        raise Unknown("prediction role differs")
    for row in holdout:
        if row["package_sha256"] not in selected or row["max_length"] != 100000:
            raise Unknown("holdout package/budget differs")
        graph = values["input_graphs"][row["package_sha256"]]
        api.consumer.v1.graph(store, graph, "holdout input graph")
    return native, values
